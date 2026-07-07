# server.py
import a2s
import socket
import time
import threading
import json
import urllib.request
import urllib.parse
import config
import utils


class ServerHandler:
    def __init__(self, app):
        self.app = app
        self.refresh_job = None
        self._current_query = 0  # ignoriert veraltete Antworten

    def measure_ping(self, server_address, timeout=1.0, attempts=2):
        OOB = b'\xff\xff\xff\xff'
        payload = OOB + b'getchallenge'
        best = 999
        sock = None
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
        except (OSError, socket.gaierror):
            return 999
        finally:
            if sock:
                sock.close()
        return best

    def fetch_qlstats_players(self, address):
        """Holt die Live-Spielerliste inkl. ELO vom qlstats-Feeder.

        Der Endpunkt /api/server/<ip>:<port>/players liefert für jeden aktuell
        getrackten Spieler steamid, name, team und rating. Das rating ist je
        nach Server-Factory automatisch das A- oder B-Rating (für Vampiric PQL
        CA also das B-Rating). team: 1=rot, 2=blau, 0=frei, >=3/-1=Spectator.
        Gibt (elo_by_name, steamid_by_name, team_by_name, info) zurück, oder
        ({}, {}, {}, None) bei jedem Fehler (Server nicht getrackt, Timeout,
        kein Netz, ...).
        """
        if not getattr(config, "SHOW_ELO", True):
            return {}, {}, {}, None
        ip, port = address
        if not ip:
            return {}, {}, {}, None
        url = "{base}/server/{ip}:{port}/players".format(
            base=config.QLSTATS_API_BASE.rstrip("/"), ip=ip, port=port
        )
        try:
            req = urllib.request.Request(url, headers={"User-Agent": config.APP_NAME})
            with urllib.request.urlopen(req, timeout=config.QLSTATS_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8", "replace"))
        except Exception:
            return {}, {}, {}, None

        if not data or not data.get("ok"):
            return {}, {}, {}, None

        elo_by_name = {}
        steamid_by_name = {}
        team_by_name = {}
        for p in data.get("players", []):
            name = p.get("name")
            if not name:
                continue
            key = utils.normalize_name(name)
            # SteamID fuer den Profil-Link. "0" = Bot -> ueberspringen.
            steamid = p.get("steamid")
            if steamid and steamid != "0":
                steamid_by_name[key] = steamid
            # Team fuer das Farbquadrat (1=rot, 2=blau, sonst kein Team).
            team = p.get("team")
            if team is not None:
                team_by_name[key] = team
            # Rating gibt es nur ab 5 gewerteten Spielen.
            rating = p.get("rating")
            if rating is not None:
                elo_by_name[key] = int(rating)

        info = data.get("serverinfo") or None
        return elo_by_name, steamid_by_name, team_by_name, info

    # --- Öffentlicher Einstiegspunkt: plant eine Abfrage ---
    def fetch_server_info(self):
        """Startet eine Abfrage in einem Worker-Thread (UI bleibt responsiv)."""
        self._current_query += 1
        query_id = self._current_query
        address = self.app.SERVER_ADDRESS
        threading.Thread(
            target=self._query_worker, args=(query_id, address), daemon=True
        ).start()

    def _query_worker(self, query_id, address):
        """Läuft im Hintergrund-Thread. KEINE Tkinter-Zugriffe hier!"""
        result = {"ok": False}
        try:
            info = a2s.info(address, timeout=5.0)
            ping_ms = self.measure_ping(address, timeout=1.5)
            try:
                players = a2s.players(address, timeout=5.0)
            except Exception:
                players = []

            # ELO vom qlstats-Feeder (Netzwerk-Call gehört in den Worker-Thread).
            elo_by_name, steamid_by_name, team_by_name, elo_info = self.fetch_qlstats_players(address)

            # Gamestate aus den A2S-Rules (g_gameState). Manche Server liefern
            # keine Rules -> leer lassen.
            gamestate = ""
            try:
                rules = a2s.rules(address, timeout=1.5)
                raw = rules.get("g_gameState", "")
                gamestate = {
                    "PRE_GAME": "WARMUP",
                    "COUNT_DOWN": "COUNTDOWN",
                    "IN_PROGRESS": "LIVE",
                }.get(raw, raw)
            except Exception:
                gamestate = ""

            result = {
                "ok": True,
                "server_name": info.server_name,
                "map_name": info.map_name,
                "max_players": info.max_players,
                "players": players,
                "player_count": len(players),
                "ping_ms": ping_ms,
                "game": getattr(info, "game", "N/A"),
                "address": address,
                "elo_by_name": elo_by_name,
                "steamid_by_name": steamid_by_name,
                "team_by_name": team_by_name,
                "elo_info": elo_info,
                "gamestate": gamestate,
            }
        except (socket.timeout, ConnectionRefusedError, socket.gaierror):
            result = {"ok": False, "msg": "Connection failed."}
        except Exception:
            result = {"ok": False, "msg": "Error."}

        # Ergebnis zurück in den Hauptthread geben
        root = self.app.root
        if root and root.winfo_exists() and not self.app.shutting_down:
            root.after(0, lambda: self._apply_result(query_id, result))

    def _apply_result(self, query_id, result):
        """Läuft im Hauptthread. Hier sind Tkinter-Zugriffe erlaubt."""
        # Veraltete Antwort (Server inzwischen gewechselt)? -> verwerfen
        if query_id != self._current_query:
            return
        if self.app.shutting_down:
            return

        ui = self.app.ui

        if result["ok"]:
            ui.error_message_var.set("")
            ui.server_name_var.set(
                utils.truncate_text(result["server_name"], config.MAX_SERVER_MAP_NAME_CHARS)
            )
            _map = utils.truncate_text(result["map_name"], config.MAX_SERVER_MAP_NAME_CHARS)
            _state = result.get("gamestate")
            ui.map_name_var.set("{} / {}".format(_map, _state) if _state else _map)
            ui.player_count_var.set(f"{result['player_count']}/{result['max_players']}")
            ui.ip_label_var.set(f"{result['address'][0]}:{result['address'][1]}")
            ui.ping_var.set(f"{result['ping_ms']}ms")

            if hasattr(ui, 'ping_label') and ui.ping_label.winfo_exists():
                if ui.current_color_scheme:
                    ui.ping_label.configure(fg=ui.current_color_scheme["fg"])

            ui.game_type_var.set(result["game"])
            ui.update_map_preview(result["map_name"])
            ui.set_server_elo_info(result.get("elo_info"))
            ui.update_player_list(
                result["players"],
                elo_by_name=result.get("elo_by_name", {}),
                steamid_by_name=result.get("steamid_by_name", {}),
                team_by_name=result.get("team_by_name", {}),
            )

            if self.app.root and self.app.root.winfo_exists():
                self.app.root.after(0, ui.auto_adjust_window_geometry)

            self.app.root.title(
                f"{config.APP_NAME} – {result['player_count']}/{result['max_players']}"
            )
            if self.app.tray_icon and hasattr(self.app.tray_icon, 'update_menu'):
                self.app.tray_icon.title = (
                    f"Players: {result['player_count']}/{result['max_players']}"
                )
        else:
            self.handle_connection_error(result.get("msg", "Error."))

        # Nächste Abfrage planen (immer im Hauptthread)
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
        ui.set_server_elo_info(None)
        ui.set_placeholder_or_clear_preview()
        ui.update_player_list([], elo_by_name={}, steamid_by_name={}, team_by_name={})

    def stop_refresh(self):
        try:
            if self.refresh_job is not None:
                self.app.root.after_cancel(self.refresh_job)
                self.refresh_job = None
        except Exception:
            pass

    def manual_refresh(self, icon=None, item=None):
        ui = self.app.ui
        if self.refresh_job:
            try:
                self.app.root.after_cancel(self.refresh_job)
            except Exception:
                pass
            self.refresh_job = None

        ui.server_name_var.set("Refreshing...")
        ui.player_count_var.set("...")
        ui.map_name_var.set("...")
        ui.ip_label_var.set("...")
        ui.ping_var.set("...")
        ui.game_type_var.set("...")
        ui.set_server_elo_info(None)

        self.fetch_server_info()