import tkinter as tk
from tkinter import ttk, messagebox
import os
import webbrowser
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
        self.elo_info_var = tk.StringVar(value="...")
        self.error_message_var = tk.StringVar()
        # Bausteine der ELO-Zeile (eigene ELO + Server-Durchschnitt).
        self._own_elo_val = None
        self._server_elo_summary = None

        # ELO-Zustand: zuletzt empfangene Name->Rating-Zuordnung, damit ein
        # Schema-Wechsel (Neuzeichnen mit alter Liste) die ELOs behält.
        self.last_elo_by_name = {}
        self.last_steamid_by_name = {}
        self.last_team_by_name = {}
        self.last_server_info = {}
        
        # Einstellungen Variablen
        self.own_steamid_var = tk.StringVar(value=self.app.app_config.get("own_steamid", ""))
        self.own_gametype_var = tk.StringVar(value=self.app.app_config.get("own_gametype", "ca"))
        self.own_rating_var = tk.StringVar(value=self.app.app_config.get("own_rating", "B"))
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
        for col in range(3): self.main_container.grid_columnconfigure(col, weight=0, minsize=0)
        for row in range(3): self.main_container.grid_rowconfigure(row, weight=0, minsize=0)
        
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
        
        self.header_frame.grid_columnconfigure(0, weight=1, uniform="hdr")
        self.header_frame.grid_columnconfigure(1, weight=0) 
        self.header_frame.grid_columnconfigure(2, weight=1, uniform="hdr") 
        
        self.hotkeys_container = tk.Frame(self.header_frame, width=30)
        self.hotkeys_container.grid(row=0, column=0, sticky="nse", padx=(0, 5)) 
        self.hotkeys_container.pack_propagate(False) 
        
        self.hotkeys_button_frame = tk.Frame(self.hotkeys_container) 
        self.hotkeys_button_frame.pack(side="top", fill="y", anchor="e") 
        
        for i in range(1, 8):
            btn = self._create_hotkey_button(self.hotkeys_button_frame, str(i), lambda i=i: self.app.switch_to_favorite(i))
            btn.pack(side="top", anchor="e", pady=2)
            
        self.preview_label = tk.Label(self.header_frame, borderwidth=2, relief="solid", cursor="hand2")
        self.preview_label.grid(row=0, column=1, padx=5, sticky="") 
        self.preview_label.bind("<Button-1>", lambda e: self.app.server_handler.manual_refresh())

        # Rechts neben dem Bild der Spielstand (rot:blau aus qlstats). Sitzt in
        # der rechten uniform-Spalte (sticky w), damit das Bild mittig bleibt.
        self.stats_container = tk.Frame(self.header_frame)
        self.stats_container.grid(row=0, column=2, sticky="nsw", padx=(5, 0))
        self.score_var = tk.StringVar(value="")
        self.score_label = tk.Label(self.stats_container, textvariable=self.score_var, font=("Arial", 12, "bold"))
        self.gamestate_var = tk.StringVar(value="")
        self.gamestate_label = tk.Label(self.stats_container, textvariable=self.gamestate_var, font=("Arial", 11, "bold"))
        # Score oben, Gamestate darunter -> Reihenfolge macht _render_header_stats.
        self._score_text = ""
        self._gamestate_text = ""

        self.toggle_hotkeys() 

    def _create_info_frame(self, parent):
        self.info_outer_frame = tk.Frame(parent)
        self.info_outer_frame.pack(fill="x", padx=0, pady=(20,10))
        info_frame = tk.Frame(self.info_outer_frame)
        info_frame.pack(anchor="w")
        
        info_labels_config = [("Server:", self.server_name_var), ("IP:", self.ip_label_var), ("Ping:", self.ping_var), ("Map:", self.map_name_var), ("Players:", self.player_count_var), ("Gamemode:", self.game_type_var), ("ELO:", self.elo_info_var)]
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


    def update_player_list(self, players, elo_by_name=None, steamid_by_name=None, team_by_name=None):
        # Zuletzt empfangene Spielerliste merken, damit ein Schema-Wechsel
        # die Liste in den neuen Farben neu zeichnen kann.
        self.last_players = players
        # ELO/SteamID/Team nur überschreiben, wenn neue Daten geliefert wurden.
        # Beim Schema-Neuzeichnen (=None) bleiben die alten erhalten.
        if elo_by_name is not None:
            self.last_elo_by_name = elo_by_name
        if steamid_by_name is not None:
            self.last_steamid_by_name = steamid_by_name
        if team_by_name is not None:
            self.last_team_by_name = team_by_name

        # Scrollposition merken, damit die Liste bei jeder Aktualisierung nicht
        # nach oben springt.
        try:
            prev_top = self.player_canvas.yview()[0]
        except Exception:
            prev_top = 0.0

        for widget in self.scrollable_frame.winfo_children(): widget.destroy()
        if not self.current_color_scheme: return
        bg_color = self.current_color_scheme["bg"]; fg_color = self.current_color_scheme["fg"]
        self.scrollable_frame.configure(bg=bg_color)

        # Ghost-Player rausfiltern: QL haelt manchmal Karteileichen in der
        # Liste (Score 0, seit >1h "verbunden"), die nicht wirklich drauf sind.
        # Ein echter (auch stundenlanger) Spectator ist von qlstats getrackt und
        # hat eine SteamID -> nur qlstats-UNBEKANNTE Score-0-Leichen fliegen raus.
        # Ohne qlstats-Daten wird gar nicht gefiltert.
        has_qlstats = bool(self.last_steamid_by_name)
        def is_ghost(p):
            if p.name in config.BOT_NAMES or not has_qlstats:
                return False
            known = utils.normalize_name(p.name) in self.last_steamid_by_name
            return (not known) and p.score <= 0 and p.duration >= 3600
        players = [p for p in players if not is_ghost(p)]

        # Spectator-Erkennung ueber das qlstats-Team (zuverlaessig; der
        # A2S-Score ist bei QL unbrauchbar). team -1 oder >=3 = Spectator,
        # 0/1/2 = aktiv. Ohne qlstats-Daten Fallback auf A2S-Score < 0.
        def team_of(p):
            return self.last_team_by_name.get(utils.normalize_name(p.name))
        def is_spec(p):
            if p.name in config.BOT_NAMES:
                return True
            t = team_of(p)
            if t is not None:
                return t < 0 or t >= 3
            return p.score < 0
        def team_rank(p):
            t = team_of(p)
            return t if t is not None else 99
        def elo_of(p):
            return self.last_elo_by_name.get(utils.normalize_name(p.name)) or 0

        spectators = sorted([p for p in players if is_spec(p)], key=lambda p: p.duration, reverse=True)
        # Aktive nach Team (1=rot, 2=blau, dann Rest), innerhalb nach Score.
        playing = sorted(
            [p for p in players if not is_spec(p)],
            key=lambda p: (team_rank(p), -p.score),
        )

        # Spielstand im Header:
        #  - Team-Spiel (scoreRed/scoreBlue vorhanden): echte Werte, leer -> 0
        #  - Duel: die zwei hoechsten Frags der aktiven Spieler
        #  - sonst (FFA/Race/...): ausblenden
        info = self.last_server_info or {}
        gt = str(info.get("gt") or "").lower()
        if "scoreRed" in info and "scoreBlue" in info:
            r = str(info.get("scoreRed", "")).strip()
            b = str(info.get("scoreBlue", "")).strip()
            r = r if r.lstrip("-").isdigit() else "0"
            b = b if b.lstrip("-").isdigit() else "0"
            self._set_match_score("{} : {}".format(r, b))
        elif gt == "duel":
            sc = sorted((p.score for p in playing), reverse=True)
            if sc:
                self._set_match_score("{} : {}".format(sc[0], sc[1] if len(sc) > 1 else 0))
            else:
                self._set_match_score(None)
        else:
            self._set_match_score(None)        
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
        self.player_canvas.yview_moveto(prev_top)

    def _create_player_list_row(self, parent, player, is_spectator):
        bg_color = self.current_color_scheme["bg"]
        row_frame = tk.Frame(parent, bg=bg_color); row_frame.pack(fill="x", expand=True)
        row_frame.grid_columnconfigure(0, weight=1)
        name_key = utils.normalize_name(player.name)
        name_widget = self.render_colored_name(row_frame, utils.truncate_text(player.name or "(anon)", config.MAX_PLAYER_NAME_CHARS))
        name_widget.grid(row=0, column=0, sticky="w", padx=2)

        # Klick auf den Namen -> Steam-Profil. Nur mit echter SteamID (qlstats).
        # Ohne SteamID und bei Bots kein Link.
        if player.name not in config.BOT_NAMES:
            steamid = self.last_steamid_by_name.get(name_key)
            if steamid:
                name_widget.configure(cursor="hand2")
                name_widget.bind(
                    "<Button-1>",
                    lambda e, sid=steamid: webbrowser.open("https://steamcommunity.com/profiles/{}".format(sid)),
                )

        # --- Team-Farbe (qlstats): Quadrat links neben der ELO ---
        # team 1 = rot, 2 = blau; frei/Spectator -> kein Quadrat.
        team = self.last_team_by_name.get(name_key)
        team_color = {1: "#e03030", 2: "#3565e0"}.get(team)

        # --- ELO-Spalte (qlstats) ---
        # Abgleich ueber den normalisierten Namen. Bots und Spieler mit < 5
        # gewerteten Spielen liefern kein Rating -> "-".
        elo = self.last_elo_by_name.get(name_key)
        if elo is not None:
            elo_text = str(elo)
            elo_fg = utils.get_elo_color(elo, self.current_color_scheme["fg"])
        else:
            elo_text = "-"
            elo_fg = "gray"

        row_frame.grid_columnconfigure(1, minsize=14)
        team_label = tk.Label(row_frame, text=("\u25a0" if team_color else ""),
                              fg=(team_color or bg_color), bg=bg_color, font=("Arial", 9))
        team_label.grid(row=0, column=1, padx=(0, 2))
        tk.Frame(row_frame, width=1, bg="black").grid(row=0, column=2, sticky="ns", padx=5)

        # --- Score (A2S). Spectators haben keinen sinnvollen Score. ---
        row_frame.grid_columnconfigure(3, minsize=34)
        score_text = str(player.score) if not is_spectator else ""
        score_label = tk.Label(row_frame, text=score_text, fg="gray", font=("Arial", 10), bg=bg_color)
        score_label.grid(row=0, column=3, sticky="e", padx=2)
        tk.Frame(row_frame, width=1, bg="black").grid(row=0, column=4, sticky="ns", padx=5)
        row_frame.grid_columnconfigure(5, minsize=46)
        elo_label = tk.Label(row_frame, text=elo_text, fg=elo_fg, font=("Arial", 10, "bold"), bg=bg_color)
        elo_label.grid(row=0, column=5, sticky="e", padx=2)

        # --- Zeit-Spalte ---
        row_frame.grid_columnconfigure(7, minsize=60)
        tk.Frame(row_frame, width=1, bg="black").grid(row=0, column=6, sticky="ns", padx=5)
        time_label = tk.Label(row_frame, text=utils.format_seconds(player.duration), fg="gray", font=("Arial", 10), bg=bg_color)
        time_label.grid(row=0, column=7, padx=2)

        tk.Frame(parent, height=1, bg="black").pack(fill="x", padx=5, pady=2)

    def set_server_elo_info(self, info):
        """Server-Durchschnitt (Ø/Min/Max) als hinterer Teil der ELO-Zeile.
        info=None oder ohne Werte -> kein Durchschnitt."""
        self.last_server_info = info or {}
        summary = None
        if info:
            rating = info.get("rating")
            avg = info.get("avg")
            lo = info.get("min")
            hi = info.get("max")
            suffix = " ({})".format(rating) if rating in ("A", "B") else ""
            if avg:
                summary = "\u00d8 {}{}".format(avg, suffix)
                if lo and hi:
                    summary += "  \u00b7  {}\u2013{}".format(lo, hi)
        self._server_elo_summary = summary
        self._render_elo_line()

    def set_own_elo(self, val):
        """Eigene ELO als vorderer Teil der ELO-Zeile. val=(elo, games) oder
        None (keine ID / keine Wertung) -> wird weggelassen."""
        self._own_elo_val = val[0] if val else None
        self._render_elo_line()

    def _render_elo_line(self):
        """Baut die ELO-Zeile: '<eigene>  ·  Ø <avg> (B)  ·  <min>–<max>'.
        Ohne eigene ELO nur der Durchschnitt; ohne beides 'N/A'."""
        parts = []
        if self._own_elo_val is not None:
            parts.append(str(self._own_elo_val))
        if self._server_elo_summary:
            parts.append(self._server_elo_summary)
        self.elo_info_var.set("  \u00b7  ".join(parts) if parts else "N/A")

    def set_gamestate(self, raw):
        """Setzt den Gamestate-Text unter dem Score (leer -> ausblenden)."""
        self._gamestate_text = raw or ""
        self._render_header_stats()

    def _set_match_score(self, text):
        """Setzt den Header-Spielstand (None/'' -> ausblenden)."""
        self._score_text = text or ""
        self._render_header_stats()

    def _render_header_stats(self):
        """Score oben, Gamestate darunter. Fehlt der Score (z.B. FFA), rutscht
        der Gamestate an dessen Stelle nach oben."""
        self.score_label.pack_forget()
        self.gamestate_label.pack_forget()
        if self._score_text:
            self.score_var.set(self._score_text)
            self.score_label.pack(anchor="w")
        if self._gamestate_text:
            self.gamestate_var.set(self._gamestate_text)
            self.gamestate_label.pack(anchor="w")

    def auto_adjust_window_geometry(self):
        self.root.update_idletasks()

        if self.player_list_position_var.get() == "bottom":
            final_width = max(self.info_pane.winfo_reqwidth() + 20, 450)
            final_height = self.info_pane.winfo_reqheight() + self.separator.winfo_reqheight() + 300
        else:
            # Breite aus den tatsächlichen Pane-Anforderungen berechnen,
            # statt die (evtl. veraltete) aktuelle Fensterbreite zu recyceln.
            # So stimmt die Geometrie auch direkt nach einem Layout-Wechsel.
            info_w = max(self.info_pane.winfo_reqwidth(), 350)
            sep_w = self.separator.winfo_reqwidth()
            player_w = max(self.player_pane.winfo_reqwidth(), 250)
            final_width = info_w + sep_w + player_w + 30
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
            if getattr(widget, 'is_hotkey_button', False):
                # Canvas-Hotkey-Button: über Neuzeichnen einfärben.
                self._draw_hotkey_button(widget, str(widget.fav_index))
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
        # Canvas-basierter Hotkey-Button: zeigt die Zahl, und bei leerem
        # Favoriten-Slot ein schwarzes Kreuz über dem Kästchen.
        size = 22
        cv = tk.Canvas(parent, width=size, height=size, highlightthickness=1,
                       highlightbackground="#000000", cursor="hand2")
        cv.is_hotkey_button = True
        cv.fav_index = int(text)
        cv.bind("<Button-1>", lambda e: command())
        self._draw_hotkey_button(cv, text)
        return cv

    def _is_active_fav(self, idx):
        """True, wenn der Favorit idx dem aktuell angezeigten Server entspricht."""
        try:
            addr_str = self.app.favorites.get(str(idx), "")
            if not addr_str or not addr_str.strip():
                return False
            return tuple(utils.parse_address(addr_str)) == tuple(self.app.SERVER_ADDRESS)
        except Exception:
            return False

    def _draw_hotkey_button(self, cv, text):
        size = 22
        cv.delete("all")
        scheme = self.current_color_scheme
        bg = scheme["bg"] if scheme else "#1a1a1a"
        accent = scheme["accent"] if scheme else "#00ff88"
        idx = getattr(cv, "fav_index", None)
        # Aktiven Server-Button invertiert hervorheben (Akzent als Hintergrund).
        active = idx is not None and self._is_active_fav(idx)
        btn_bg = accent if active else bg
        txt_fill = bg if active else accent
        cv.configure(bg=btn_bg, highlightbackground=(accent if active else "#000000"))
        # Zahl
        cv.create_text(size // 2, size // 2, text=text, fill=txt_fill,
                       font=("Arial", 9, "bold"))
        # Bei nicht vergebenem Favoriten ein schwarzes X darüberlegen
        if idx is not None:
            addr = self.app.favorites.get(str(idx), "")
            if not addr or not addr.strip():
                cv.create_line(3, 3, size - 3, size - 3, fill="#000000", width=2)
                cv.create_line(size - 3, 3, 3, size - 3, fill="#000000", width=2)

    def refresh_hotkey_buttons(self):
        # Zeichnet alle Hotkey-Buttons neu (z.B. nach Speichern von Favoriten).
        if not hasattr(self, 'hotkeys_button_frame'):
            return
        for child in self.hotkeys_button_frame.winfo_children():
            if getattr(child, 'is_hotkey_button', False):
                self._draw_hotkey_button(child, str(child.fav_index))

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

        # Ursprüngliches Schema merken, um es bei Schließen ohne Speichern
        # wiederherzustellen (sonst bleibt die Live-Vorschau aktiv).
        original_scheme_name = self.app.app_config.get("color_scheme", "Dark1")
        saved_flag = {"done": False}
        
        options_width, options_height = 500, 630
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

                # 2. Speicherung der Favoriten 2-7
                for i in range(2, 8):
                    self.app.favorites[str(i)] = fav_entries[str(i)].get().strip()
                
                # 3. Speicherung der App-Konfiguration (Farbe, Hotkeys, Layout, etc.)
                self.app.app_config["color_scheme"] = color_var.get()
                self.app.app_config["show_hotkeys"] = self.show_hotkeys_var.get()
                self.app.app_config["start_minimized"] = self.start_minimized_var.get()
                self.app.app_config["start_with_system"] = self.start_with_system_var.get()
                
                # KORREKTUR: Speichert die neue String-Variable
                self.app.app_config["player_list_position"] = self.player_list_position_var.get()
                self.app.app_config["own_steamid"] = self.own_steamid_var.get().strip()
                self.app.app_config["own_gametype"] = self.own_gametype_var.get()
                self.app.app_config["own_rating"] = self.own_rating_var.get()

                utils.save_app_config(self.app)
                utils.save_favorites(self.app.favorites)

                self.refresh_hotkey_buttons()
                self._arrange_panes()
                self.app.server_handler.manual_refresh()
                saved_flag["done"] = True
                self.options_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Invalid settings: {e}", parent=self.options_window)
        
        tk.Button(main_frame, text="Save & Close", command=save_and_close).pack(side="bottom", pady=5)

        def on_close_without_save():
            # Wenn ohne Speichern geschlossen wird, Live-Vorschau zurücksetzen.
            if not saved_flag["done"]:
                self.apply_color_scheme(original_scheme_name)
            self.options_window.destroy()

        self.options_window.protocol("WM_DELETE_WINDOW", on_close_without_save)

        notebook = ttk.Notebook(main_frame); notebook.pack(fill="both", expand=True, pady=(0, 5)) 
        
        # --- TAB 1: General ---
        general_tab = tk.Frame(notebook, padx=10, pady=10); notebook.add(general_tab, text="General")

        # Update-Intervall (gehoert nicht zu den Favoriten)
        interval_frame = tk.LabelFrame(general_tab, text="General Settings", padx=10, pady=10); interval_frame.pack(fill="x", pady=5)
        tk.Label(interval_frame, text="Update interval (seconds)").pack(anchor="w")
        entry_interval = tk.Entry(interval_frame, width=10); entry_interval.insert(0, str(self.app.REFRESH_INTERVAL)); entry_interval.pack(anchor="w", pady=(0,5))
        tk.Label(interval_frame, text="Your SteamID64 (for \"Own\" ELO)").pack(anchor="w")
        tk.Entry(interval_frame, width=22, textvariable=self.own_steamid_var).pack(anchor="w", pady=(0,5))
        own_row = tk.Frame(interval_frame); own_row.pack(anchor="w", pady=(0,5))
        tk.Label(own_row, text="\"Own\" ELO mode:").pack(side="left")
        tk.OptionMenu(own_row, self.own_gametype_var, *["duel","ffa","ca","tdm","ctf","ft","ad"]).pack(side="left", padx=(5,0))
        tk.OptionMenu(own_row, self.own_rating_var, *["A","B"]).pack(side="left", padx=(5,0))

        # Server-Favoriten 1-6 als gleichwertige Liste.
        # Favorit 1 ist gleichzeitig der Hauptserver, der angezeigt wird.
        fav_outer = tk.LabelFrame(general_tab, text="Server Favorites (1 = main server)", padx=10, pady=10); fav_outer.pack(fill="x", pady=5)
        current_ip_port_str = f"{self.app.main_server_address_setting[0]}:{self.app.main_server_address_setting[1]}"
        for i in range(1, 8):
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