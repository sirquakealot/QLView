# server.py
import a2s
import socket
import time
import threading
import json
import urllib.request
import urllib.parse
import re
import config
import utils

OOB = b'\xff\xff\xff\xff'

# g_gametype -> Name. 0-7 sind ioq3/baseq3 (+ Team Arena), 8+ kommen aus
# OpenArena (und damit auch aus OA-basierten Spielen wie OpenVampArena).
Q3_GAMETYPES = {
    0: "FFA", 1: "Tournament", 2: "Single Player", 3: "Team DM", 4: "CTF",
    5: "One Flag CTF", 6: "Overload", 7: "Harvester", 8: "Elimination",
    9: "CTF Elimination", 10: "Last Man Standing", 11: "Double Domination",
    12: "Domination", 13: "Possession",
}

# Spielerzeile in der statusResponse: '<score> <ping> "<name>"'. Manche Mods
# haengen weitere Zahlen vor den Namen -> beliebig viele Zahlen erlauben.
_Q3_PLAYER_RE = re.compile(r'^\s*((?:-?\d+\s+)+)"(.*)"\s*$')


class Q3Player:
    """Spieler aus einer ioq3-statusResponse. Gleiche Attribute wie die
    a2s-Player (name, score, duration), damit die UI beide gleich behandelt.
    ioq3 liefert keine Verbindungsdauer (duration=None), dafuer den Ping."""
    __slots__ = ("name", "score", "ping", "duration")

    def __init__(self, name, score, ping):
        self.name = name
        self.score = score
        self.ping = ping
        self.duration = None


def query_q3_status(address, timeout=3.0):
    """Fragt einen ioq3-Server per 'getstatus' ab (klassisches Q3-Protokoll).
    Gibt (serverinfo_dict, [Q3Player, ...]) zurueck. Wirft socket.timeout /
    OSError bei keiner Antwort, ValueError bei unerwarteter Antwort."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.settimeout(timeout)
        sock.connect(address)
        sock.send(OOB + b'getstatus')
        data = sock.recv(65535)
    finally:
        sock.close()

    prefix = OOB + b'statusResponse'
    if not data.startswith(prefix):
        raise ValueError("No statusResponse")
    # Q3 hat kein festes Encoding; latin-1 bildet jedes Byte verlustfrei ab.
    lines = data[len(prefix):].decode("latin-1").split("\n")
    lines = [l for l in lines if l.strip()]
    if not lines:
        raise ValueError("Empty statusResponse")

    parts = lines[0].split("\\")
    if parts and parts[0] == "":
        parts = parts[1:]
    info = {parts[i]: parts[i + 1] for i in range(0, len(parts) - 1, 2)}

    players = []
    for line in lines[1:]:
        m = _Q3_PLAYER_RE.match(line)
        if not m:
            continue
        nums = [int(x) for x in m.group(1).split()]
        score = nums[0]
        ping = nums[1] if len(nums) > 1 else 0
        players.append(Q3Player(m.group(2), score, ping))
    return info, players


def _to_int(value, default=0):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


class ServerHandler:
    def __init__(self, app):
        self.app = app
        self.refresh_job = None
        self._current_query = 0  # ignoriert veraltete Antworten
        # Erkanntes Protokoll je Adresse: "a2s" (Quake Live) oder "q3" (ioq3).
        # Wird bei der ersten erfolgreichen Abfrage gesetzt und bei einem
        # Fehler wieder geloescht, damit danach neu erkannt wird.
        self._protocol_by_address = {}

    def get_protocol(self, address):
        """'a2s', 'q3' oder None (noch nicht erkannt)."""
        return self._protocol_by_address.get(tuple(address))

    def measure_ping(self, server_address, timeout=1.0, attempts=2, payload=None):
        # Standard: 'getchallenge' (QL). ioq3-Server bekommen 'getinfo'.
        payload = payload or (OOB + b'getchallenge')
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

    def fetch_own_elo(self):
        """Eigene ELO per SteamID aus den Optionen, unabhaengig davon ob man
        gerade auf dem Server ist. Gamemode und A/B-Rating kommen ebenfalls aus
        den Optionen (Route /elo bzw. /elo_b). Gibt (elo, games) oder None
        (keine ID, 0 Spiele, Fehler)."""
        steamid = str(self.app.app_config.get("own_steamid", "")).strip()
        if not steamid.isdigit() or not getattr(config, "SHOW_ELO", True):
            return None
        gt = str(self.app.app_config.get("own_gametype", "ca")).lower()
        rating = str(self.app.app_config.get("own_rating", "B")).upper()
        route = "elo_b" if rating == "B" else "elo"
        # /elo und /elo_b liegen im Root (xonstat), NICHT unter /api (Feeder).
        base = config.QLSTATS_API_BASE.rstrip("/")
        site = base[:-4] if base.endswith("/api") else base
        url = "{site}/{route}/{sid}".format(site=site, route=route, sid=steamid)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": config.APP_NAME})
            with urllib.request.urlopen(req, timeout=config.QLSTATS_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8", "replace"))
        except Exception:
            return None
        players = data.get("players") or []
        if not players:
            return None
        entry = (players[0] or {}).get(gt) or {}
        elo = entry.get("elo")
        games = entry.get("games", 0)
        if elo is None or not games:   # 0 gewertete Spiele -> ungewertet
            return None
        return (int(elo), int(games))

    def _query_worker(self, query_id, address):
        """Läuft im Hintergrund-Thread. KEINE Tkinter-Zugriffe hier!"""
        # Eigene ELO unabhaengig vom Server-Ergebnis (zeigt sie auch, wenn der
        # getrackte Server gerade down ist).
        own_elo = self.fetch_own_elo()
        address = tuple(address)
        proto = self._protocol_by_address.get(address)

        if proto == "q3":
            result = self._query_q3(address, own_elo)
        else:
            result = self._query_a2s(address, own_elo, timeout=5.0 if proto == "a2s" else 3.0)
            # Kein A2S und Protokoll noch unbekannt -> vielleicht ein ioq3-Server
            # (OpenArena, OpenVampArena, ...). Die sprechen nur 'getstatus'.
            if not result["ok"] and proto is None and not result.get("dns_error"):
                result = self._query_q3(address, own_elo)

        if result["ok"]:
            self._protocol_by_address[address] = result["protocol"]
        else:
            self._protocol_by_address.pop(address, None)

        # Ergebnis zurück in den Hauptthread geben
        root = self.app.root
        if root and root.winfo_exists() and not self.app.shutting_down:
            root.after(0, lambda: self._apply_result(query_id, result))

    def _query_q3(self, address, own_elo):
        """Abfrage eines ioq3-Servers ueber das klassische Q3-Protokoll.
        Laeuft im Worker-Thread -> keine Tk-Zugriffe."""
        try:
            info, players = query_q3_status(address, timeout=3.0)
        except (OSError, ValueError):   # Timeout, DNS, Port zu, Muell-Antwort
            return {"ok": False, "msg": "Connection failed.", "own_elo": own_elo}

        ping_ms = self.measure_ping(address, timeout=1.5, payload=OOB + b'getinfo ping')

        gt_num = _to_int(info.get("g_gametype"), -1)
        gt_name = Q3_GAMETYPES.get(gt_num, "Gametype {}".format(gt_num) if gt_num >= 0 else "N/A")
        game_name = info.get("com_gamename") or info.get("gamename") or ""
        game = "{} ({})".format(gt_name, game_name) if game_name else gt_name

        max_players = _to_int(info.get("sv_maxclients"), 0) - _to_int(info.get("sv_privateClients"), 0)

        # Fuer die Header-Anzeige: bei Tournament (1v1) den Duel-Score zeigen.
        header_info = {"gt": "duel"} if gt_num == 1 else None

        return {
            "ok": True,
            "protocol": "q3",
            # Q3-Hostnamen enthalten oft Farbcodes -> fuer die Info-Zeile entfernen.
            "server_name": utils.strip_quake_colors(info.get("sv_hostname") or info.get("hostname") or "") or "N/A",
            "map_name": info.get("mapname", "N/A"),
            "max_players": max(max_players, 0),
            "players": players,
            "player_count": len(players),
            "ping_ms": ping_ms,
            "game": game,
            "address": address,
            # qlstats kennt nur Quake-Live-Server -> keine ELO/SteamID/Teams.
            "elo_by_name": {},
            "steamid_by_name": {},
            "team_by_name": {},
            "elo_info": header_info,
            "gamestate": "",
            "own_elo": own_elo,
        }

    def _query_a2s(self, address, own_elo, timeout=5.0):
        """Abfrage eines Quake-Live-Servers per A2S (+ qlstats)."""
        try:
            info = a2s.info(address, timeout=timeout)
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
                if raw == "IN_PROGRESS":
                    gamestate = "Active"
                elif raw:
                    gamestate = "Warmup"
            except Exception:
                gamestate = ""

            return {
                "ok": True,
                "protocol": "a2s",
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
                "own_elo": own_elo,
            }
        except socket.gaierror:
            return {"ok": False, "msg": "Connection failed.", "own_elo": own_elo, "dns_error": True}
        except (socket.timeout, ConnectionRefusedError):
            return {"ok": False, "msg": "Connection failed.", "own_elo": own_elo}
        except Exception:
            return {"ok": False, "msg": "Error.", "own_elo": own_elo}

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
            ui.map_name_var.set(
                utils.truncate_text(result["map_name"], config.MAX_SERVER_MAP_NAME_CHARS)
            )
            ui.set_gamestate(result.get("gamestate"))
            ui.player_count_var.set(f"{result['player_count']}/{result['max_players']}")
            ui.ip_label_var.set(f"{result['address'][0]}:{result['address'][1]}")
            ui.ping_var.set(f"{result['ping_ms']}ms")

            if hasattr(ui, 'ping_label') and ui.ping_label.winfo_exists():
                if ui.current_color_scheme:
                    ui.ping_label.configure(fg=ui.current_color_scheme["fg"])

            ui.game_type_var.set(result["game"])
            ui.update_map_preview(result["map_name"])
            ui.set_server_elo_info(result.get("elo_info"))
            ui.set_own_elo(result.get("own_elo"))
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
            ui.set_own_elo(result.get("own_elo"))

        # Aktiven Favoriten-Button markieren (Server kann gewechselt haben).
        ui.refresh_hotkey_buttons()

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
        ui.set_gamestate("")
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
        ui.set_gamestate("")
        ui.ip_label_var.set("...")
        ui.ping_var.set("...")
        ui.game_type_var.set("...")
        ui.set_server_elo_info(None)

        self.fetch_server_info()