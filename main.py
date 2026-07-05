import tkinter as tk
from tkinter import messagebox
import os
import pystray
from PIL import Image, ImageTk 
import threading

# Importe deiner lokalen Dateien
import config
import utils
from ui import UIManager
from server import ServerHandler

class QLViewApp:
    def __init__(self):
        # 1. Konfiguration laden und Variablen setzen
        self.app_config = utils.load_app_config()
        self.favorites = utils.load_favorites()
        
        default_address_str = f"{config.DEFAULT_SERVER_ADDRESS[0]}:{config.DEFAULT_SERVER_ADDRESS[1]}"
        self.main_server_address_setting = utils.parse_address(self.app_config.get("main_server_address", default_address_str))
        
        self.SERVER_ADDRESS = self.main_server_address_setting
        self.REFRESH_INTERVAL = self.app_config.get("refresh_interval", config.DEFAULT_REFRESH_INTERVAL)
        self.shutting_down = False

        # 2. Tkinter Fenster erstellen
        self.root = tk.Tk()
        self.root.title(config.APP_NAME)
        self.root.resizable(False, False)
        
        try:
            icon_path = utils.resource_path("quake3.ico")
            self.window_icon_photo = ImageTk.PhotoImage(Image.open(icon_path)) 
            self.root.iconphoto(False, self.window_icon_photo)
        except Exception as e:
            print(f"Warning: Could not set window icon: {e}")

        # 3. Komponenten initialisieren
        self.ui = UIManager(self)
        
        # ServerHandler MUSS VOR setup_tray_icon initialisiert werden
        self.server_handler = ServerHandler(self) 
        
        self.tray_icon = None
        self.setup_tray_icon()
        
        # 4. UI aufbauen und erste Aktualisierung starten
        self.ui.setup_ui()
        self.server_handler.fetch_server_info()
        
        # 5. Wichtige Bindings (Minimierung und Schließen)
        self.root.bind('<Unmap>', self.hide_window_on_minimize)
        self.root.protocol("WM_DELETE_WINDOW", self.cleanup)
        
        # 6. Startverhalten: KORREKTUR MIT VERZÖGERUNG
        if self.app_config.get("start_minimized", False):
            # Verzögere das Ausblenden um 100ms
            self.root.after(100, self.root.withdraw)

    def run(self):
        try:
            self.root.mainloop()
        finally:
            self.cleanup() 

    def hide_window_on_minimize(self, event):
        if event.widget == self.root:
            self.root.withdraw()

    # --- TRAY ICON LOGIK ---

    def setup_tray_icon(self):
        try:
            icon_path = utils.resource_path("quake3.ico")
            icon_image = Image.open(icon_path)

            # WICHTIG: pystray-Menü-Callbacks laufen im Tray-Thread, NICHT im
            # Tkinter-Hauptthread. Direkte Tk-Aufrufe von dort (withdraw,
            # deiconify, StringVar.set, messagebox, after_cancel) sind nicht
            # thread-sicher und können sporadische Hänger/Abstürze verursachen.
            # Deshalb wird jede Aktion über root.after(0, ...) in den Hauptthread
            # eingereiht.
            def on_main(func):
                return lambda icon=None, item=None: self.root.after(0, func)

            self.tray_icon = pystray.Icon(
                'Quake Server Viewer', 
                icon=icon_image, 
                title=config.APP_NAME,
                menu=pystray.Menu(
                    pystray.MenuItem('Show/Hide', on_main(self.toggle_window_main), default=True), 
                    pystray.MenuItem('Refresh', on_main(self.server_handler.manual_refresh)),
                    pystray.MenuItem('Connect', on_main(self.connect_to_server)),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem('Exit', on_main(self.cleanup))
                )
            )
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
            
        except Exception as e:
            print(f"Error setting up tray icon: {e}")
            self.tray_icon = None

    def toggle_window_main(self):
        # Läuft im Hauptthread (über root.after eingereiht).
        if self.root.winfo_viewable():
            self.root.withdraw()
        else:
            self.show_window_from_tray()

    def show_window_from_tray(self, icon=None, item=None):
        if self.root.winfo_exists():
            self.root.deiconify() 
            self.root.lift()
            self.root.focus_force()

    # --- WICHTIGE HINTERGRUND-METHODEN (CLEANUP) ---
    
    def cleanup(self):
        if self.shutting_down:
            return 
        
        self.shutting_down = True
        
        # 1. Timer stoppen
        if hasattr(self, 'server_handler') and self.server_handler:
            self.server_handler.stop_refresh() 

        # 2. Tray-Icon stoppen
        if self.tray_icon:
            self.tray_icon.stop()
            
        # 3. Das Tkinter-Fenster sicher zerstören
        try:
            if self.root.winfo_exists():
                self.root.destroy()
        except tk.TclError:
            pass
            
        # 4. Erzwingt die Beendigung des Prozesses, um alle Threads zu schließen
        os._exit(0)

    # --- AKTIONSMETHODEN ---

    def switch_to_favorite(self, fav_num):
        address_str = self.favorites.get(str(fav_num))
        if address_str:
            try:
                new_address = utils.parse_address(address_str)
                self.SERVER_ADDRESS = new_address
                if fav_num == 1:
                    self.main_server_address_setting = new_address
                    self.app_config["main_server_address"] = f"{new_address[0]}:{new_address[1]}"
                    utils.save_app_config(self)
                
                self.server_handler.manual_refresh()
                self.show_window_from_tray()
                
            except ValueError as e:
                messagebox.showerror("Error", f"Invalid address format for Favorite {fav_num}: {e}")
                
    def connect_to_server(self, icon=None, item=None):
        if not self.SERVER_ADDRESS or self.SERVER_ADDRESS[0] == "":
             messagebox.showerror("Connection Error", "No server address is set.")
             return

        connect_cmd = config.CONNECT_COMMAND.format(ip=self.SERVER_ADDRESS[0], port=self.SERVER_ADDRESS[1])
        try:
            os.startfile(connect_cmd)
        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to execute connect command: {e}")

# Wenn main.py direkt ausgeführt wird, starte die App
if __name__ == "__main__":
    app = QLViewApp()
    app.run()