import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
import os
import re
from PIL import Image, ImageTk
import utils
import config

class UIManager:
    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.options_window = None
        self.current_color_scheme = None
        self.q3_logo_placeholder_photo = None
        self.is_default_jpg_loaded = False
        self.last_players = []
        
        self.server_name_var = tk.StringVar(value="Loading...")
        self.map_name_var = tk.StringVar(value="...")
        self.player_count_var = tk.StringVar(value="-")
        self.ip_label_var = tk.StringVar(value="...")
        self.ping_var = tk.StringVar(value="...")
        self.game_type_var = tk.StringVar(value="...")
        self.error_message_var = tk.StringVar()
        
        # Einstellungen Variablen
        self.show_hotkeys_var = tk.BooleanVar(value=self.app.app_config.get("show_hotkeys", True))
        self.start_minimized_var = tk.BooleanVar(value=self.app.app_config.get("start_minimized", False))
        self.start_with_system_var = tk.BooleanVar(value=self.app.app_config.get("start_with_system", False))
        
        # KORREKTUR: Einzelne StringVar für das Layout
        self.player_list_position_var = tk.StringVar(value=self.app.app_config.get("player_list_position", "right"))

    def setup_ui(self):
        self.load_placeholder_image()
        
        self.main_container = tk.Frame(self.root)
        self.main_container.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.info_pane = tk.Frame(self.main_container)
        self.player_pane = tk.Frame(self.main_container)
        self.separator = ttk.Separator(self.main_container, orient='vertical')

        self._arrange_panes()

        self._create_header(self.info_pane)
        self._create_info_frame(self.info_pane)
        self.button_container = self._create_new_button_bar(self.info_pane)
        self._create_player_list_frame(self.player_pane)

        self.apply_color_scheme(self.app.app_config["color_scheme"])
        # Initialer Aufruf der Größenanpassung
        self.root.after(100, self.auto_adjust_window_geometry)

    def _arrange_panes(self):
        for col in range(3): self.main_container.grid_columnconfigure(col, weight=0)
        for row in range(3): self.main_container.grid_rowconfigure(row, weight=0)
        
        self.info_pane.grid_forget()
        self.separator.grid_forget()
        self.player_pane.grid_forget()

        # KORREKTUR: Prüfen, ob die gestapelte Ansicht gewünscht ist
        if self.player_list_position_var.get() == "bottom":
            
            self.main_container.grid_columnconfigure(0, weight=1) 
            self.main_container.grid_rowconfigure(2, weight=1) 

            self.info_pane.grid(row=0, column=0, sticky="new")
            
            self.separator.config(orient='horizontal')
            self.separator.grid(row=1, column=0, sticky="ew", pady=5, padx=0)
            
            self.player_pane.grid(row=2, column=0, sticky="nsew")

        else: # "right" oder Standard
            info_pane_minsize = 350
            self.separator.config(orient='vertical')
            self.main_container.grid_rowconfigure(0, weight=1) 
            
            # Da "right" der Standardwert ist, platzieren wir Info links und Player rechts
            self.main_container.grid_columnconfigure(0, weight=0, minsize=info_pane_minsize)
            self.main_container.grid_columnconfigure(2, weight=1)
            info_pane_col, player_pane_col = (0, 2)
            
            # Sie könnten hier eine weitere Option für "left" hinzufügen, wenn gewünscht.
            
            self.info_pane.grid(row=0, column=info_pane_col, sticky="new")
            self.separator.grid(row=0, column=1, sticky="ns", padx=5)
            self.player_pane.grid(row=0, column=player_pane_col, sticky="nsew")

        self.root.after(10, self.auto_adjust_window_geometry)


    def _create_header(self, parent):
        self.header_frame = tk.Frame(parent)
        self.header_frame.pack(fill="x", pady=(5,0))
        
        self.header_frame.grid_columnconfigure(0, weight=0)
        self.header_frame.grid_columnconfigure(1, weight=1) 
        self.header_frame.grid_columnconfigure(2, weight=0) 
        
        self.hotkeys_container = tk.Frame(self.header_frame, width=30)
        self.hotkeys_container.grid(row=0, column=0, sticky="nsw", padx=(0, 5)) 
        self.hotkeys_container.pack_propagate(False) 
        
        self.hotkeys_button_frame = tk.Frame(self.hotkeys_container) 
        self.hotkeys_button_frame.pack(side="top", fill="y", anchor="e") 
        
        for i in range(1, 7):
            btn = self._create_hotkey_button(self.hotkeys_button_frame, str(i), lambda i=i: self.app.switch_to_favorite(i))
            btn.pack(side="top", anchor="e", pady=2)
            
        self.preview_label = tk.Label(self.header_frame, borderwidth=2, relief="solid", cursor="hand2")
        self.preview_label.grid(row=0, column=1, padx=5, sticky="") 
        self.preview_label.bind("<Button-1>", lambda e: self.app.server_handler.manual_refresh())
        
        tk.Frame(self.header_frame, width=30).grid(row=0, column=2, sticky="nse")
        
        self.toggle_hotkeys() 

    def _create_info_frame(self, parent):
        self.info_outer_frame = tk.Frame(parent)
        self.info_outer_frame.pack(fill="x", padx=0, pady=(20,10))
        info_frame = tk.Frame(self.info_outer_frame)
        info_frame.pack(anchor="w")
        
        info_labels_config = [("Server:", self.server_name_var), ("IP:", self.ip_label_var), ("Ping:", self.ping_var), ("Map:", self.map_name_var), ("Players:", self.player_count_var), ("Gamemode:", self.game_type_var)]
        for i, (text, var) in enumerate(info_labels_config):
            tk.Label(info_frame, text=text, font=("Arial", 10, "bold")).grid(row=i, column=0, sticky="e", padx=(0,5), pady=0)
            lbl = tk.Label(info_frame, textvariable=var, font=("Arial", 10), wraplength=250, justify=tk.LEFT)
            lbl.grid(row=i, column=1, sticky="w", pady=0)
            if text == "IP:":
                lbl.config(cursor="hand2"); lbl.bind("<Button-1>", self._copy_ip)
            if text == "Ping:":
                self.ping_label = lbl

    def _create_new_button_bar(self, parent):
        bar = tk.Frame(parent, height=45)
        bar.pack(side="top", fill="x", pady=(5, 10))
        bar.pack_propagate(False)
        bar.grid_columnconfigure((0, 1), weight=1)
        self._create_standard_button(bar, "OPTIONS", self.open_options_window).grid(row=0, column=0, sticky="nsew", padx=(0,5))
        self._create_standard_button(bar, "CONNECT", self.app.connect_to_server).grid(row=0, column=1, sticky="nsew", padx=(5,0))
        return bar

    def _on_mouse_wheel(self, event):
        if self.player_canvas.yview() == (0.0, 1.0): return "break"
        if event.num == 5 or event.delta < 0: self.player_canvas.yview_scroll(1, "units")
        elif event.num == 4 or event.delta > 0: self.player_canvas.yview_scroll(-1, "units")
        return "break"
            
    def _bind_mouse_wheel_recursive(self, widget):
        widget.bind("<MouseWheel>", self._on_mouse_wheel) 
        widget.bind("<Button-4>", self._on_mouse_wheel)    
        widget.bind("<Button-5>", self._on_mouse_wheel)    
        for child in widget.winfo_children(): self._bind_mouse_wheel_recursive(child)

    def _create_player_list_frame(self, parent):
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        self.player_canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.player_canvas.yview)
        
        self.scrollable_frame = tk.Frame(self.player_canvas)
        
        canvas_window = self.player_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        
        def configure_canvas(event): self.player_canvas.itemconfig(canvas_window, width=event.width)
        self.player_canvas.bind("<Configure>", configure_canvas)

        def configure_scrollable_frame(event): self.player_canvas.configure(scrollregion=self.player_canvas.bbox("all"))
        self.scrollable_frame.bind("<Configure>", configure_scrollable_frame)

        self.player_canvas.configure(yscrollcommand=scrollbar.set)
        self.player_canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self._bind_mouse_wheel_recursive(self.player_canvas)


    def update_player_list(self, players):
        # Zuletzt empfangene Spielerliste merken, damit ein Schema-Wechsel
        # die Liste in den neuen Farben neu zeichnen kann.
        self.last_players = players
        for widget in self.scrollable_frame.winfo_children(): widget.destroy()
        if not self.current_color_scheme: return
        bg_color = self.current_color_scheme["bg"]; fg_color = self.current_color_scheme["fg"]
        self.scrollable_frame.configure(bg=bg_color)

        spectators = sorted([p for p in players if p.score < 0 or p.name in config.BOT_NAMES], key=lambda p: p.duration, reverse=True)
        playing = sorted([p for p in players if p.score >= 0 and p.name not in config.BOT_NAMES], key=lambda p: p.score, reverse=True)
        
        tk.Label(self.scrollable_frame, text="Players", font=("Arial", 11, "bold"), bg=bg_color, fg=fg_color).pack(pady=(0,5))
        tk.Frame(self.scrollable_frame, height=1, bg="black").pack(fill="x", padx=5, pady=(0, 5))

        if not playing and not spectators:
            tk.Label(self.scrollable_frame, text="-- No Players --", font=("Arial", 10, "italic"), bg=bg_color, fg=fg_color).pack(pady=5)
        else:
            for player in playing: 
                self._create_player_list_row(self.scrollable_frame, player, is_spectator=False)
            
            if spectators:
                tk.Frame(self.scrollable_frame, height=3, bg="gray").pack(fill="x", padx=5, pady=(5, 5)) 
                for player in spectators: 
                    self._create_player_list_row(self.scrollable_frame, player, is_spectator=True)
        
        self.root.update_idletasks() 
        self._bind_mouse_wheel_recursive(self.scrollable_frame) 
        self.player_canvas.configure(scrollregion=self.player_canvas.bbox("all"))
        self.player_canvas.yview_moveto(0)

    def _create_player_list_row(self, parent, player, is_spectator):
        bg_color = self.current_color_scheme["bg"]
        row_frame = tk.Frame(parent, bg=bg_color); row_frame.pack(fill="x", expand=True)
        row_frame.grid_columnconfigure(0, weight=1)
        name_widget = self.render_colored_name(row_frame, utils.truncate_text(player.name or "(anon)", config.MAX_PLAYER_NAME_CHARS))
        name_widget.grid(row=0, column=0, sticky="w", padx=2)
        
        row_frame.grid_columnconfigure(2, minsize=60)
        
        tk.Frame(row_frame, width=1, bg="black").grid(row=0, column=1, sticky="ns", padx=5) 
        
        time_label = tk.Label(row_frame, text=utils.format_seconds(player.duration), fg="gray", font=("Arial", 10), bg=bg_color)
        time_label.grid(row=0, column=2, padx=2)
            
        tk.Frame(parent, height=1, bg="black").pack(fill="x", padx=5, pady=2)

    def auto_adjust_window_geometry(self):
        self.root.update_idletasks()
        
        # KORREKTUR: Layout-Abfrage mit neuer Variablen
        if self.player_list_position_var.get() == "bottom":
            final_width = max(self.info_pane.winfo_reqwidth() + 20, 450)
            final_height = self.info_pane.winfo_reqheight() + self.separator.winfo_reqheight() + 300 
        else:
            final_width = self.root.winfo_width() 
            final_height = self.info_pane.winfo_reqheight() + 20 
        
        self.root.geometry(f"{final_width}x{final_height}")

    def apply_color_scheme(self, scheme_name):
        if scheme_name not in config.COLOR_SCHEMES: return
        self.current_color_scheme = config.COLOR_SCHEMES[scheme_name]
        self.root.configure(bg=self.current_color_scheme["bg"])
        self._apply_colors_recursive(self.root)
        # Spielerliste mit den neuen Farben neu zeichnen. Die Namen-Textfelder
        # uebernehmen ihre Hintergrundfarbe beim Erstellen, daher reicht
        # Umkonfigurieren nicht - die Liste muss neu aufgebaut werden.
        if hasattr(self, 'scrollable_frame') and self.scrollable_frame.winfo_exists():
            self.update_player_list(self.last_players)

    def _apply_colors_recursive(self, widget, scheme=None):
        active_scheme = scheme if scheme else self.current_color_scheme
        if not active_scheme: return
        # WICHTIG: Das Options-Fenster niemals einfaerben. Es ist ein Toplevel
        # und taucht als Kind von self.root in der Hierarchie auf, soll aber sein
        # neutrales graues Standard-Design behalten.
        if self.options_window is not None and (widget is self.options_window):
            return
        try:
            widget_class = widget.winfo_class()
            config_map = {
                'Frame': {'bg': active_scheme["bg"]}, 'Toplevel': {'bg': active_scheme["bg"]}, 'Canvas': {'bg': active_scheme["bg"]},
                'Label': {'bg': active_scheme["bg"], 'fg': active_scheme["fg"]},
                'Button': {'bg': active_scheme["button_bg"], 'fg': active_scheme["button_fg"], 'activebackground': active_scheme["button_active"], 'highlightbackground': active_scheme["bg"], 'highlightthickness': 0},
                'Text': {'bg': active_scheme["bg"], 'fg': active_scheme["fg"], 'highlightbackground': active_scheme["bg"]},
                'Checkbutton': {'bg': active_scheme["bg"], 'fg': active_scheme["fg"], 'activebackground': active_scheme["bg"], 'activeforeground': active_scheme["fg"], 'selectcolor': active_scheme["info_bg"], 'highlightbackground': active_scheme["bg"], 'highlightthickness': 0},
                'Radiobutton': {'bg': active_scheme["bg"], 'fg': active_scheme["fg"], 'activebackground': active_scheme["bg"], 'activeforeground': active_scheme["fg"], 'selectcolor': active_scheme["info_bg"], 'highlightbackground': active_scheme["bg"], 'highlightthickness': 0},
                'LabelFrame': {'bg': active_scheme["bg"], 'fg': active_scheme["fg"], 'highlightbackground': active_scheme["bg"], 'highlightthickness': 0}, 'Entry': {'bg': active_scheme["info_bg"], 'fg': active_scheme["fg"]},
            }
            if widget_class in config_map: widget.configure(**config_map[widget_class])
            if hasattr(self, 'refresh_button') and widget == self.refresh_button: widget.configure(fg=active_scheme["fg"])
            if hasattr(widget, 'is_hotkey_button'): widget.configure(bg=active_scheme["bg"], fg=active_scheme["accent"], activebackground=active_scheme["bg"], activeforeground=active_scheme["secondary"])
            if isinstance(widget, ttk.Separator): style = ttk.Style(); style.configure("Vertical.TSeparator", background="black"); style.configure("Horizontal.TSeparator", background="black")
        except tk.TclError: pass
        for child in widget.winfo_children(): self._apply_colors_recursive(child, scheme=scheme)

    def render_colored_name(self, parent, name_str):
        default_color = self.current_color_scheme.get("fg", "#ffffff")
        # Quake-Live-Farbpalette ^0 - ^9
        color_map = {
            "0": default_color,   # schwarz -> nutze fg, damit auf dunklem bg sichtbar
            "1": "#ff0000",       # rot
            "2": "#00ff00",       # gruen
            "3": "#ffff00",       # gelb
            "4": "#0000ff",       # blau
            "5": "#00ffff",       # cyan
            "6": "#ff00ff",       # magenta
            "7": default_color,   # weiss -> fg
            "8": "#ff8000",       # orange
            "9": "#808080",       # grau
        }
        text_widget = tk.Text(parent, height=1, borderwidth=0, highlightthickness=0, bg=parent.cget("bg"),
                            highlightbackground=parent.cget("bg"), wrap="none", font=("Arial", 10, "bold"), padx=0, pady=0)
        for code, color_name in color_map.items():
            text_widget.tag_configure(f"color_{code}", foreground=color_name)

        clean_name = name_str.replace('\x00', '')
        current_tag = "color_7"
        i = 0
        n = len(clean_name)
        buffer = ""

        def flush():
            nonlocal buffer
            if buffer:
                text_widget.insert("end", buffer, (current_tag,))
                buffer = ""

        while i < n:
            ch = clean_name[i]
            if ch == '^' and i + 1 < n:
                nxt = clean_name[i + 1]
                if nxt == '^':
                    # ^^ -> literales Caret
                    buffer += '^'
                    i += 2
                    continue
                elif nxt.isdigit():
                    # Farbcode: erst gepufferten Text mit alter Farbe schreiben
                    flush()
                    current_tag = f"color_{nxt}"
                    i += 2
                    continue
            buffer += ch
            i += 1

        flush()
        text_widget.configure(state="disabled")
        return text_widget

    def load_placeholder_image(self):
        try:
            default_path = os.path.join(config.MAPSHOTS_DIR, "default.jpg")
            if os.path.exists(default_path):
                with Image.open(default_path) as img:
                    img_resized = img.resize((256, 192), Image.Resampling.LANCZOS)
                    self.q3_logo_placeholder_photo = ImageTk.PhotoImage(img_resized)
                    self.is_default_jpg_loaded = True 
            else:
                img_gray = Image.new("RGB", (256, 192), color="#333333")
                self.q3_logo_placeholder_photo = ImageTk.PhotoImage(img_gray)
                self.is_default_jpg_loaded = False 
        except Exception as e: 
            print(f"Warning: Could not load placeholder image: {e}")
            self.q3_logo_placeholder_photo = None
            self.is_default_jpg_loaded = False

    def update_map_preview(self, mapname_param):
        if not hasattr(self, 'preview_label'): return
        sanitized_map_name = utils.sanitize_filename(mapname_param)
        for ext in ["png", "jpg", "jpeg"]:
            path_to_check = os.path.join(config.MAPSHOTS_DIR, f"{sanitized_map_name}.{ext}")
            if os.path.exists(path_to_check):
                try:
                    with Image.open(path_to_check) as img:
                        img_resized = img.resize((256, 192), Image.Resampling.LANCZOS)
                        photo_to_display = ImageTk.PhotoImage(img_resized)
                        self.preview_label.config(text="", image=photo_to_display, compound="none"); self.preview_label.image = photo_to_display
                    if self.root.winfo_exists(): self.root.update_idletasks()
                    return
                except Exception as e: print(f"Warning: Local image '{path_to_check}' could not be loaded: {e}")
        
        self.set_placeholder_or_clear_preview()
    
    def set_placeholder_or_clear_preview(self):
        if not (hasattr(self, 'preview_label') and self.preview_label.winfo_exists()): return
        
        fg_color = self.current_color_scheme.get("fg", "#ffffff")
        
        if self.q3_logo_placeholder_photo:
            self.preview_label.config(image=self.q3_logo_placeholder_photo); self.preview_label.image = self.q3_logo_placeholder_photo
            
            if self.is_default_jpg_loaded:
                self.preview_label.config(text="", compound="none")
            else:
                self.preview_label.config(
                    text="Mapshot N/A\n(default.jpg missing)", 
                    fg=fg_color, 
                    bg="#333333", 
                    compound="center" 
                )
        else:
            self.preview_label.config(text="Mapshot N/A (Error)", image="", compound="none"); self.preview_label.image = None
            
        if self.root.winfo_exists(): self.root.update_idletasks()
            
    def _create_standard_button(self, parent, text, command):
        return tk.Button(parent, text=text, command=command, font=("Arial", 10, "bold"), relief="flat", padx=10, pady=5)

    def _create_hotkey_button(self, parent, text, command):
        btn = tk.Button(parent, text=text, command=command, font=("Arial", 9, "bold"), relief="solid", borderwidth=1, padx=3, pady=1)
        btn.is_hotkey_button = True
        return btn

    def toggle_hotkeys(self):
        should_show = self.show_hotkeys_var.get()
        if hasattr(self, 'hotkeys_button_frame'):
            if should_show: 
                self.hotkeys_button_frame.pack(side="top", fill="y", anchor="e")
            else: 
                self.hotkeys_button_frame.pack_forget()

    def _copy_ip(self, event=None):
        self.root.clipboard_clear(); self.root.clipboard_append(self.ip_label_var.get())
        original_ip = self.ip_label_var.get()
        self.ip_label_var.set("Copied!"); self.root.after(1000, lambda: self.ip_label_var.set(original_ip))
    
    def open_options_window(self):
        if self.options_window and self.options_window.winfo_exists():
            self.options_window.lift(); return
        
        self.options_window = tk.Toplevel(self.root)
        self.options_window.title("Options"); self.options_window.transient(self.root); self.options_window.resizable(False, False)
        
        options_width, options_height = 500, 560 
        self.root.update_idletasks()
        main_x, main_y = self.root.winfo_x(), self.root.winfo_y()
        main_width, main_height = self.root.winfo_width(), self.root.winfo_height()
        pos_x = main_x + (main_width // 2) - (options_width // 2)
        pos_y = main_y + (main_height // 2) - (options_height // 2)
        self.options_window.geometry(f"{options_width}x{options_height}+{pos_x}+{pos_y}")

        try: self.options_window.iconbitmap(utils.resource_path("quake3.ico"))
        except tk.TclError: print("Warning: Could not load options window icon.")
        
        main_frame = tk.Frame(self.options_window, padx=10, pady=10); main_frame.pack(fill="both", expand=True)

        fav_entries = {}
        
        def save_and_close():
            try:
                # 1. Hauptserver kommt aus dem ersten Favoriten-Feld
                ip_port_str = fav_entries["1"].get().strip()
                ip, port = utils.parse_address(ip_port_str) # parsed die Eingabe
                self.app.main_server_address_setting = (ip, port)
                self.app.SERVER_ADDRESS = self.app.main_server_address_setting
                self.app.REFRESH_INTERVAL = int(entry_interval.get().strip())

                # Favorit 1 ist immer der Hauptserver
                self.app.favorites["1"] = ip_port_str

                # 2. Speicherung der Favoriten 2-6
                for i in range(2, 7):
                    self.app.favorites[str(i)] = fav_entries[str(i)].get().strip()
                
                # 3. Speicherung der App-Konfiguration (Farbe, Hotkeys, Layout, etc.)
                self.app.app_config["color_scheme"] = color_var.get()
                self.app.app_config["show_hotkeys"] = self.show_hotkeys_var.get()
                self.app.app_config["start_minimized"] = self.start_minimized_var.get()
                self.app.app_config["start_with_system"] = self.start_with_system_var.get()
                
                # KORREKTUR: Speichert die neue String-Variable
                self.app.app_config["player_list_position"] = self.player_list_position_var.get()

                utils.save_app_config(self.app)
                utils.save_favorites(self.app.favorites)
                
                self._arrange_panes()
                self.app.server_handler.manual_refresh()
                self.options_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Invalid settings: {e}", parent=self.options_window)
        
        tk.Button(main_frame, text="Save & Close", command=save_and_close).pack(side="bottom", pady=5)

        notebook = ttk.Notebook(main_frame); notebook.pack(fill="both", expand=True, pady=(0, 5)) 
        
        # --- TAB 1: General ---
        general_tab = tk.Frame(notebook, padx=10, pady=10); notebook.add(general_tab, text="General")

        # Update-Intervall (gehoert nicht zu den Favoriten)
        interval_frame = tk.LabelFrame(general_tab, text="General Settings", padx=10, pady=10); interval_frame.pack(fill="x", pady=5)
        tk.Label(interval_frame, text="Update interval (seconds)").pack(anchor="w")
        entry_interval = tk.Entry(interval_frame, width=10); entry_interval.insert(0, str(self.app.REFRESH_INTERVAL)); entry_interval.pack(anchor="w", pady=(0,5))

        # Server-Favoriten 1-6 als gleichwertige Liste.
        # Favorit 1 ist gleichzeitig der Hauptserver, der angezeigt wird.
        fav_outer = tk.LabelFrame(general_tab, text="Server Favorites (1 = main server)", padx=10, pady=10); fav_outer.pack(fill="x", pady=5)
        current_ip_port_str = f"{self.app.main_server_address_setting[0]}:{self.app.main_server_address_setting[1]}"
        for i in range(1, 7):
            fav_frame = tk.Frame(fav_outer)
            fav_frame.pack(fill="x", pady=2)
            tk.Label(fav_frame, text=f"Favorite {i} (IP:Port):", width=16, anchor="w").pack(side="left")
            entry = tk.Entry(fav_frame)
            if i == 1:
                entry.insert(0, current_ip_port_str)
            else:
                entry.insert(0, self.app.favorites.get(str(i), ""))
            entry.pack(side="left", fill="x", expand=True)
            fav_entries[str(i)] = entry

        app_frame = tk.LabelFrame(general_tab, text="Application Settings", padx=10, pady=10); app_frame.pack(fill="x", pady=5)
        tk.Checkbutton(app_frame, text="Start minimized to tray", variable=self.start_minimized_var).pack(anchor="w")
        tk.Checkbutton(app_frame, text="Start with system", variable=self.start_with_system_var).pack(anchor="w")

        # --- TAB 2: Appearance ---
        appearance_tab = tk.Frame(notebook, padx=10, pady=10); notebook.add(appearance_tab, text="Appearance")
        tk.Checkbutton(appearance_tab, text="Show Favorite Hotkeys", variable=self.show_hotkeys_var, command=self.toggle_hotkeys).pack(anchor="w")
        
        layout_frame = tk.LabelFrame(appearance_tab, text="Layout", padx=10, pady=10); layout_frame.pack(fill='x', pady=5)
        
        # KORREKTUR: Radiobuttons verwenden die EINE String-Variable
        tk.Radiobutton(layout_frame, 
                       text="Player list on the right (Side-by-Side)", 
                       variable=self.player_list_position_var, 
                       value="right").pack(anchor="w")

        tk.Radiobutton(layout_frame, 
                       text="Player list below server info (Stacked)", 
                       variable=self.player_list_position_var, 
                       value="bottom").pack(anchor="w")
                       
        tk.Label(layout_frame, text="(Requires restart to apply layout changes fully)", font=("Arial", 8, "italic")).pack(anchor="w", padx=5, pady=(5,0))


        color_frame = tk.LabelFrame(appearance_tab, text="Color Scheme", padx=10, pady=10); color_frame.pack(fill="x", pady=5)
        color_var = tk.StringVar(value=self.app.app_config.get("color_scheme", "Dark1"))

        def on_color_change():
            # Nur das Hauptfenster umfaerben (Live-Vorschau).
            # Das Options-Fenster behaelt bewusst sein festes graues Design.
            self.apply_color_scheme(color_var.get())

        for i, name in enumerate(config.COLOR_SCHEMES.keys()):
            tk.Radiobutton(color_frame, text=name, variable=color_var, value=name, command=on_color_change).grid(row=i//4, column=i%4, sticky="w")

        # Options-Fenster bewusst NICHT einfaerben: es behaelt das neutrale
        # Standard-Design (grauer Hintergrund, schwarze Schrift), unabhaengig
        # vom Schema des Hauptfensters.