# utils.py
import os
import sys
import re
import configparser
import json
import config

# Neue Windows-spezifische Importe für die Verknüpfung
if sys.platform == "win32":
    try:
        import winshell
        from win32com.client import Dispatch
    except ImportError:
        winshell = None
        Dispatch = None
else:
    winshell = None
    Dispatch = None


def resource_path(relative_path):
    try: 
        base_path = sys._MEIPASS
    except Exception: 
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def sanitize_filename(name):
    name = str(name)
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'\s+', '_', name)
    return name[:100]

def truncate_text(text, max_chars):
    return text[:max_chars-3] + "..." if len(text) > max_chars else text

def format_seconds(secs):
    hours = int(secs // 3600)
    mins = int((secs % 3600) // 60)
    return f"{hours}:{mins:02d}h" if hours > 0 else f"{mins}m"

def strip_quake_colors(name):
    """Entfernt Quake-Farbcodes (^0-^9) aus einem Namen. ^^ wird zu ^."""
    if not name:
        return ""
    out = []
    i = 0
    n = len(name)
    while i < n:
        ch = name[i]
        if ch == '^' and i + 1 < n:
            nxt = name[i + 1]
            if nxt == '^':
                out.append('^')
                i += 2
                continue
            elif nxt.isdigit():
                i += 2
                continue
        out.append(ch)
        i += 1
    return ''.join(out)

def normalize_name(name):
    """Vergleichsschlüssel für den Abgleich A2S-Name <-> qlstats-Name."""
    return strip_quake_colors(name).replace('\x00', '').strip().lower()

def get_elo_color(elo, default="#ffffff"):
    """Farbe für einen ELO-Wert. Schwellen sind grob an QL-CA angelehnt."""
    if elo is None:
        return default
    if elo >= 2000:
        return "#ff4500"   # Spitze
    elif elo >= 1700:
        return "#ffa500"   # stark
    elif elo >= 1400:
        return "#00ff00"   # überdurchschnittlich
    elif elo >= 1100:
        return default     # Durchschnitt
    else:
        return "#9e9e9e"   # niedrig

def load_favorites():
    default_favs = {str(i): "" for i in range(1, 8)}
    if os.path.exists(config.FAVORITES_FILE):
        try:
            with open(config.FAVORITES_FILE, 'r') as f:
                favorites = json.load(f)
            for i in range(1, 8):
                if str(i) not in favorites: 
                    favorites[str(i)] = ""
            return favorites
        except Exception as e:
            print(f"Warning: Could not load favorites: {e}")
            return default_favs
    return default_favs

def save_favorites(favorites):
    """Speichert die Favoriten-Liste als JSON-Datei."""
    try:
        with open(config.FAVORITES_FILE, 'w') as f:
            json.dump(favorites, f, indent=4)
    except Exception as e: 
        print(f"Error: Could not save favorites: {e}")

def load_app_config():
    app_cfg = {
        "main_server_address": f"{config.DEFAULT_SERVER_ADDRESS[0]}:{config.DEFAULT_SERVER_ADDRESS[1]}",
        "refresh_interval": config.DEFAULT_REFRESH_INTERVAL,
        "show_hotkeys": True, 
        "start_minimized": False,
        "start_with_system": False,
        "color_scheme": "Dark1",
        "player_list_position": "right",
    }
    parser = configparser.ConfigParser(interpolation=None)
    
    if os.path.exists(config.CONFIG_FILE):
        parser.read(config.CONFIG_FILE)
        
        ip_port_str = parser.get("settings", "server", fallback=f"{config.DEFAULT_SERVER_ADDRESS[0]}:{config.DEFAULT_SERVER_ADDRESS[1]}")
        app_cfg["main_server_address"] = ip_port_str

        app_cfg["refresh_interval"] = parser.getint("settings", "interval", fallback=config.DEFAULT_REFRESH_INTERVAL)
        app_cfg["show_hotkeys"] = parser.getboolean("settings", "show_hotkeys", fallback=True)
        app_cfg["start_minimized"] = parser.getboolean("settings", "start_minimized", fallback=False)
        app_cfg["start_with_system"] = parser.getboolean("settings", "start_with_system", fallback=False)
        app_cfg["color_scheme"] = parser.get("settings", "color_scheme", fallback="Dark1")

        # LOGIK FÜR DIE PLAYER-LISTE (Konvertierung/Laden)
        new_position = parser.get("settings", "player_list_position", fallback=None)
        
        if new_position:
            app_cfg["player_list_position"] = new_position
        else:
            on_bottom = parser.getboolean("settings", "player_list_on_bottom", fallback=False)
            if on_bottom:
                app_cfg["player_list_position"] = "bottom"
            else:
                app_cfg["player_list_position"] = "right"

    return app_cfg

def parse_address(address_str):
    """
    Parses an 'IP:Port' string into a tuple (str, int).
    Raises ValueError if the format is invalid.
    """
    if not address_str:
        return ("", 0) 
        
    parts = address_str.split(':')
    
    if len(parts) != 2:
        raise ValueError(f"Invalid address format: '{address_str}'. Must be 'IP:Port'.")
        
    ip, port_str = parts[0].strip(), parts[1].strip()
    
    try:
        port = int(port_str)
    except ValueError:
        raise ValueError(f"Invalid port number: '{port_str}'. Port must be an integer.")
        
    if not (0 <= port <= 65535): 
        raise ValueError("Port number must be between 0 and 65535.")
        
    return (ip, port)

def get_application_path():
    """Gibt den Pfad zur ausführbaren Datei oder zum Skript zurück."""
    if getattr(sys, 'frozen', False):
        return sys.executable
    return os.path.abspath(sys.argv[0])

def get_startup_folder():
    """Ruft den Windows-Startup-Ordner ab."""
    if sys.platform == "win32" and winshell:
        try:
            # Winshell ist der zuverlässigste Weg
            return winshell.startup()
        except Exception:
            # Fallback
            return os.path.join(os.getenv('APPDATA'), 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')
    return None

def toggle_autostart(should_start):
    """
    Managt Autostart via Windows Shortcut (.lnk) im Startup folder.
    Dies ist der robuste Weg, um die Start-Minimiert-Eigenschaft zu setzen (WindowStyle=7).
    """
    if sys.platform != "win32" or not winshell or not Dispatch:
        if sys.platform == "win32":
             print("Warning: winshell or pywin32 not available. Autostart management is limited.")
        return
        
    APP_NAME = config.APP_NAME 
    startup_folder = get_startup_folder()
    
    if not startup_folder:
        print("Warning: Could not determine Windows Startup folder.")
        return

    app_path = get_application_path()
    shortcut_path = os.path.join(startup_folder, f"{APP_NAME}.lnk")

    if should_start:
        try:
            target = app_path
            args = ""
            # Wenn es ein Skript ist, mit pythonw.exe starten, um das Konsolenfenster zu vermeiden
            if not getattr(sys, 'frozen', False) and app_path.endswith(".py"):
                python_exe = sys.executable.replace("python.exe", "pythonw.exe")
                if not os.path.exists(python_exe): python_exe = sys.executable
                target = python_exe
                args = f'"{app_path}"'
                
            shell = Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(shortcut_path)
            shortcut.Targetpath = target
            shortcut.Arguments = args
            shortcut.WindowStyle = 7 # 7 = Minimized window
            shortcut.Description = f"Launch {APP_NAME}"
            shortcut.WorkingDirectory = os.path.dirname(app_path)
            
            icon_path = resource_path("quake3.ico")
            if os.path.exists(icon_path):
                shortcut.IconLocation = icon_path

            shortcut.save()
            print(f"Autostart enabled via shortcut: {shortcut_path}")
        except Exception as e:
            print(f"ERROR: Could not create Windows shortcut for autostart: {e}")
    else:
        if os.path.exists(shortcut_path):
            try:
                os.remove(shortcut_path)
                print(f"Autostart disabled (shortcut removed): {shortcut_path}")
            except Exception as e:
                print(f"ERROR: Could not remove shortcut: {e}")

def save_app_config(app):
    parser = configparser.ConfigParser(interpolation=None)
    parser.add_section("settings")
    parser.set("settings", "server", f"{app.main_server_address_setting[0]}:{app.main_server_address_setting[1]}")
    parser.set("settings", "interval", str(app.REFRESH_INTERVAL))
    parser.set("settings", "show_hotkeys", str(app.ui.show_hotkeys_var.get()))
    parser.set("settings", "start_minimized", str(app.ui.start_minimized_var.get()))
    parser.set("settings", "start_with_system", str(app.ui.start_with_system_var.get()))
    
    parser.set("settings", "player_list_position", app.ui.player_list_position_var.get())
    
    scheme_name = next((name for name, scheme in config.COLOR_SCHEMES.items() if scheme == app.ui.current_color_scheme), "Dark1")
    parser.set("settings", "color_scheme", scheme_name)

    try:
        with open(config.CONFIG_FILE, "w") as f: 
            parser.write(f)
    except IOError as e: 
        print(f"ERROR: Could not write to config file '{config.CONFIG_FILE}': {e}")
    
    # Autostart nach Speicherung der Konfiguration umschalten
    toggle_autostart(app.ui.start_with_system_var.get())