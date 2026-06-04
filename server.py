# server.py
import a2s
import socket
import time
import config
import utils
# import subprocess # NICHT MEHR NÖTIG
# import re # NICHT MEHR NÖTIG

class ServerHandler:
    def __init__(self, app):
        self.app = app
        self.refresh_job = None 

    def measure_ping(self, server_address, timeout=1.0, attempts=4):
        """
        Misst den Quake-Live-Ping über ein getchallenge out-of-band Paket
        direkt auf dem Spiel-Port - dieselbe Methode wie qlping.
        Gibt den besten Wert mehrerer Messungen zurück, oder 999 wenn der
        Server nicht antwortet.
        """
        OOB = b'\xff\xff\xff\xff'
        payload = OOB + b'getchallenge'
        best = 999

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            sock.connect(server_address)
            for _ in range(attempts):
                try:
                    start = time.perf_counter()
                    sock.send(payload)
                    sock.recv(2048)
                    end = time.perf_counter()
                    ms = max(1, int((end - start) * 1000))
                    best = min(best, ms)
                except socket.timeout:
                    continue
            sock.close()
        except (OSError, socket.gaierror):
            return 999

        return best

    def fetch_server_info(self):
        ui = self.app.ui
        try:
            # First try to get basic server info
            info = a2s.info(self.app.SERVER_ADDRESS, timeout=5.0)
            
            # If we got here, server is reachable - now measure ping
            ping_ms = self.measure_ping(self.app.SERVER_ADDRESS, timeout=3.0) 
            
            # Get player info
            try:
                players = a2s.players(self.app.SERVER_ADDRESS, timeout=5.0)
            except Exception:
                players = []
            
            # Update UI with successful connection
            ui.error_message_var.set("")
            ui.server_name_var.set(utils.truncate_text(info.server_name, config.MAX_SERVER_MAP_NAME_CHARS))
            ui.map_name_var.set(utils.truncate_text(info.map_name, config.MAX_SERVER_MAP_NAME_CHARS))
            ui.player_count_var.set(f"{len(players)}/{info.max_players}")
            ui.ip_label_var.set(f"{self.app.SERVER_ADDRESS[0]}:{self.app.SERVER_ADDRESS[1]}")
            
            ui.ping_var.set(f"{ping_ms}ms")
            
            # Ping-Farbe auf Standard-Vordergrundfarbe setzen
            if hasattr(ui, 'ping_label') and ui.ping_label.winfo_exists():
                if ui.current_color_scheme:
                    ui.ping_label.configure(fg=ui.current_color_scheme["fg"])

            ui.game_type_var.set(getattr(info, 'game', 'N/A'))
            
            ui.update_map_preview(info.map_name)
            ui.update_player_list(players)
            
            # Verzögerter Aufruf der Größenanpassung (behält die UI-Höhen-Korrektur bei)
            if self.app.root and self.app.root.winfo_exists():
                self.app.root.after(0, ui.auto_adjust_window_geometry)
            
            self.app.root.title(f"{config.APP_NAME} – {len(players)}/{info.max_players}")
            if self.app.tray_icon and hasattr(self.app.tray_icon, 'update_menu'):
                self.app.tray_icon.title = f"Players: {len(players)}/{info.max_players}"
                
        except (socket.timeout, ConnectionRefusedError, socket.gaierror) as e:
            self.handle_connection_error("Connection failed.")
        except Exception as e:
            self.handle_connection_error("Error.")
        finally:
            if self.app.root and self.app.root.winfo_exists() and not self.app.shutting_down:
                self.refresh_job = self.app.root.after(
                    max(1000, self.app.REFRESH_INTERVAL * 1000), self.fetch_server_info
                )

    def handle_connection_error(self, msg):
        ui = self.app.ui
        ui.error_message_var.set(msg)
        ui.ping_var.set("N/A")
        ui.server_name_var.set("Connection failed")
        ui.map_name_var.set("N/A")
        ui.ip_label_var.set("N/A")
        ui.game_type_var.set("N/A") 
        ui.set_placeholder_or_clear_preview()
        ui.update_player_list([])

    def stop_refresh(self):
        """
        Stoppt den laufenden Tkinter-Timer, der von main.py:cleanup aufgerufen wird.
        """
        try:
            if self.refresh_job is not None:
                self.app.root.after_cancel(self.refresh_job)
                self.refresh_job = None
        except Exception:
            pass


    def manual_refresh(self):
        import threading
        ui = self.app.ui
        if self.refresh_job:
            try:
                self.app.root.after_cancel(self.refresh_job)
            except Exception:
                pass

        # Platzhalter anzeigen, während im Hintergrund abgefragt wird
        ui.server_name_var.set("Refreshing...")
        ui.player_count_var.set("...")
        ui.map_name_var.set("...")
        ui.ip_label_var.set("...")
        ui.ping_var.set("...")
        ui.game_type_var.set("...")

        # Startet die Abfrage in einem Thread, damit das UI nicht einfriert.
        # KEIN zusätzlicher direkter Aufruf danach (das fror die UI ein).
        threading.Thread(target=self.fetch_server_info, daemon=True).start()
