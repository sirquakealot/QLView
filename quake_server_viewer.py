import tkinter as tk
import a2s
import socket
import configparser
import os
import sys
import webbrowser
import threading
import re
from PIL import Image, ImageTk
import pystray
import urllib.request
from io import BytesIO

if sys.platform == "win32":
    try:
        import winshell
        from win32com.client import Dispatch
    except ImportError:
        print("Warning: 'winshell' or 'pywin32' not found. Startup management will be limited.")
        winshell = None

# --- Configuration ---
CONFIG_FILE = "config.ini"
APP_NAME = "QLView"
DEFAULT_SERVER_ADDRESS = ("108.61.179.235", 27962)
DEFAULT_REFRESH_INTERVAL = 10
MAPSHOTS_DIR = "Mapshots"
MAX_SERVER_MAP_NAME_CHARS = 35
MAX_PLAYER_NAME_CHARS = 28
MIN_AUTO_WIDTH = 280
MIN_WINDOW_HEIGHT = 300

# --- Global Variables ---
options_window = None
tray_icon = None
player_labels = []
last_processed_map_name_for_image = None
last_show_thumbnail_state_for_image = None
q3_logo_placeholder_photo = None
shutting_down = False
after_id_fetch_server_info = None
start_minimized_on_next_launch_var = None
start_with_system_var = None

# --- Helper Functions ---
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_application_path():
    if getattr(sys, 'frozen', False):
        return sys.executable
    return os.path.abspath(sys.argv[0])

def sanitize_filename(name):
    name = str(name)
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'\s+', '_', name)
    return name[:100]

def truncate_text(text, max_chars):
    if len(text) > max_chars:
        return text[:max_chars-3] + "..."
    return text

def format_seconds(secs):
    mins = int(secs // 60)
    secs = int(secs % 60)
    return f"{mins}:{secs:02d}"

# --- Image Handling ---
def load_placeholder_image():
    global q3_logo_placeholder_photo, MAPSHOTS_DIR
    placeholder_path = os.path.join(MAPSHOTS_DIR, "placeholder.png")
    custom_placeholder_loaded = False
    try:
        if os.path.exists(placeholder_path):
            img = Image.open(placeholder_path)
            if img.mode not in ['RGB', 'RGBA']:
                img = img.convert('RGBA' if 'A' in img.mode else 'RGB')
            img = img.resize((256, 192), Image.Resampling.LANCZOS)
            q3_logo_placeholder_photo = ImageTk.PhotoImage(img)
            custom_placeholder_loaded = True
    except Exception as e:
        print(f"Warning: Could not load custom placeholder '{placeholder_path}': {e}")

    if not custom_placeholder_loaded:
        try:
            img_gray = Image.new("RGB", (256, 192), color="#333333")
            q3_logo_placeholder_photo = ImageTk.PhotoImage(img_gray)
        except Exception as e:
            print(f"Warning: Could not create default gray placeholder: {e}")
            q3_logo_placeholder_photo = None

def set_placeholder_or_clear_preview():
    global preview_label, show_thumbnail, q3_logo_placeholder_photo, error_message_var, root
    if 'preview_label' in globals() and preview_label.winfo_exists():
        current_error = error_message_var.get()
        bg_color = root.cget("bg")
        preview_width = preview_label.winfo_width()
        wrapl = max(200, preview_width - 20 if preview_width > 40 else MIN_AUTO_WIDTH - 40)

        if current_error:
            preview_label.config(image="", text=current_error, font=("Arial", 11, "bold"), fg="white", bg="#B22222", wraplength=wrapl)
            preview_label.image = None
        elif show_thumbnail.get() and q3_logo_placeholder_photo:
            preview_label.config(text="", image=q3_logo_placeholder_photo, bg=bg_color)
            preview_label.image = q3_logo_placeholder_photo
        else:
            preview_label.config(text="", image="", bg=bg_color)
            preview_label.image = None
        if root.winfo_exists():
            root.update_idletasks()

def update_map_preview(mapname_param):
    global preview_label, show_thumbnail, q3_logo_placeholder_photo, MAPSHOTS_DIR, error_message_var, root
    if mapname_param is None or not show_thumbnail.get():
        set_placeholder_or_clear_preview()
        return

    sanitized_map_name = sanitize_filename(mapname_param)
    abs_mapshots_dir = os.path.abspath(MAPSHOTS_DIR)
    filenames_to_check = [f"{sanitized_map_name}.png", f"{sanitized_map_name}.jpg", f"{sanitized_map_name}.jpeg"]
    pil_image_obj = None
    for filename in filenames_to_check:
        path_to_check = os.path.join(abs_mapshots_dir, filename)
        if os.path.exists(path_to_check):
            try:
                img_opened = Image.open(path_to_check)
                if img_opened.mode not in ['RGB', 'RGBA']:
                    img_opened = img_opened.convert('RGBA' if 'A' in img_opened.mode else 'RGB')
                pil_image_obj = img_opened.resize((256, 192), Image.Resampling.LANCZOS)
                break
            except Exception as e:
                print(f"Warning: Local image '{path_to_check}' could not be loaded: {e}")
                try:
                    os.remove(path_to_check)
                except OSError: pass

    bg_color = root.cget("bg")
    if 'preview_label' in globals() and preview_label.winfo_exists():
        current_error = error_message_var.get()
        preview_width = preview_label.winfo_width()
        wrapl = max(200, preview_width - 20 if preview_width > 40 else MIN_AUTO_WIDTH - 40)
        if current_error:
            preview_label.config(image="", text=current_error, font=("Arial", 11, "bold"), fg="white", bg="#B22222", wraplength=wrapl)
            preview_label.image = None
        elif pil_image_obj:
            photo_to_display = ImageTk.PhotoImage(pil_image_obj)
            preview_label.config(text="", image=photo_to_display, bg=bg_color)
            preview_label.image = photo_to_display
        elif q3_logo_placeholder_photo:
            preview_label.config(text="", image=q3_logo_placeholder_photo, bg=bg_color)
            preview_label.image = q3_logo_placeholder_photo
        else:
            preview_label.config(text="", image="", bg=bg_color)
            preview_label.image = None
        if root.winfo_exists():
            root.update_idletasks()

# --- Config Handling ---
def load_config():
    global SERVER_ADDRESS, REFRESH_INTERVAL, show_thumbnail, start_minimized_on_next_launch_var, start_with_system_var
    config = configparser.ConfigParser(interpolation=None)
    SERVER_ADDRESS = DEFAULT_SERVER_ADDRESS
    REFRESH_INTERVAL = DEFAULT_REFRESH_INTERVAL

    if start_minimized_on_next_launch_var is None: start_minimized_on_next_launch_var = tk.BooleanVar()
    if start_with_system_var is None: start_with_system_var = tk.BooleanVar()

    if os.path.exists(CONFIG_FILE):
        try:
            config.read(CONFIG_FILE)
            ip_port = config.get("settings", "server", fallback=f"{DEFAULT_SERVER_ADDRESS[0]}:{DEFAULT_SERVER_ADDRESS[1]}")
            interval = config.getint("settings", "interval", fallback=DEFAULT_REFRESH_INTERVAL)
            thumb = config.getboolean("settings", "thumbnail", fallback=True)
            start_minimized = config.getboolean("settings", "start_minimized", fallback=False)
            start_os = config.getboolean("settings", "start_with_system", fallback=False)

            show_thumbnail.set(thumb)
            start_minimized_on_next_launch_var.set(start_minimized)
            start_with_system_var.set(start_os)
            
            ip, port_str = ip_port.split(":")
            SERVER_ADDRESS = (ip, int(port_str))
            REFRESH_INTERVAL = interval
        except (configparser.Error, ValueError) as e:
            print(f"Warning: Error reading config file '{CONFIG_FILE}': {e}. Using defaults.")
            show_thumbnail.set(True)
            start_minimized_on_next_launch_var.set(False)
            start_with_system_var.set(False)
            save_config()
    else:
        show_thumbnail.set(True)
        start_minimized_on_next_launch_var.set(False)
        start_with_system_var.set(False)
        save_config()

def save_config():
    global SERVER_ADDRESS, REFRESH_INTERVAL, show_thumbnail, start_minimized_on_next_launch_var, start_with_system_var
    config = configparser.ConfigParser(interpolation=None)
    if not config.has_section("settings"): config.add_section("settings")
    config.set("settings", "server", f"{SERVER_ADDRESS[0]}:{SERVER_ADDRESS[1]}")
    config.set("settings", "interval", str(REFRESH_INTERVAL))
    config.set("settings", "thumbnail", str(show_thumbnail.get()))
    config.set("settings", "start_minimized", str(start_minimized_on_next_launch_var.get()))
    config.set("settings", "start_with_system", str(start_with_system_var.get()))
        
    try:
        with open(CONFIG_FILE, "w") as f: config.write(f)
    except IOError as e:
        print(f"ERROR: Could not write to config file '{CONFIG_FILE}': {e}")

# --- Server Interaction ---
def fetch_server_info():
    global last_processed_map_name_for_image, last_show_thumbnail_state_for_image, map_name_var, server_name_var, player_count_var, max_players_var, ip_label_var, error_message_var, SERVER_ADDRESS, REFRESH_INTERVAL, show_thumbnail, root, tray_icon, after_id_fetch_server_info
    try:
        info = a2s.info(SERVER_ADDRESS, timeout=3.0)
        players = a2s.players(SERVER_ADDRESS, timeout=3.0)
        
        if error_message_var.get():
            error_message_var.set("")
            update_map_preview(info.map_name if info and show_thumbnail.get() else None)

        map_name_var.set(truncate_text(info.map_name, MAX_SERVER_MAP_NAME_CHARS))
        server_name_var.set(truncate_text(info.server_name, MAX_SERVER_MAP_NAME_CHARS))
        player_count_var.set(str(info.player_count))
        max_players_var.set(str(info.max_players))
        ip_label_var.set(f"{SERVER_ADDRESS[0]}:{SERVER_ADDRESS[1]}")

        current_show_thumbnail_setting = show_thumbnail.get()
        map_has_changed = (info.map_name != last_processed_map_name_for_image)
        thumbnail_setting_has_changed = (current_show_thumbnail_setting != last_show_thumbnail_state_for_image)

        if map_has_changed or thumbnail_setting_has_changed:
            update_map_preview(info.map_name if current_show_thumbnail_setting else None)
            last_processed_map_name_for_image = info.map_name if current_show_thumbnail_setting else None
            last_show_thumbnail_state_for_image = current_show_thumbnail_setting
        
        update_player_list(players)
        root.title(f"{APP_NAME} – {player_count_var.get()}/{max_players_var.get()}")
        if tray_icon and hasattr(tray_icon, 'update_menu'):
            tray_icon.title = f"Players: {player_count_var.get()}/{max_players_var.get()}"
            
    except (socket.timeout, ConnectionRefusedError, Exception) as e:
        error_msg = "Timeout connecting to server."
        if isinstance(e, ConnectionRefusedError): error_msg = "Connection refused by server."
        elif not isinstance(e, socket.timeout): error_msg = "Error fetching server info."
        handle_connection_error(error_msg)
        print(f"Warning: {e}")
    finally:
        if root and root.winfo_exists() and not shutting_down:
            after_id_fetch_server_info = root.after(max(1000, REFRESH_INTERVAL * 1000), fetch_server_info)

def handle_connection_error(specific_error_msg="Failed to connect."):
    global server_name_var, map_name_var, player_count_var, ip_label_var, error_message_var
    error_message_var.set(specific_error_msg)
    if player_count_var.get() == "-":
        server_name_var.set("Connection failed")
        map_name_var.set("N/A")
        ip_label_var.set("N/A")
    set_placeholder_or_clear_preview()
    update_player_list([])

# --- GUI Rendering & Auto Height ---
def render_colored_name(parent, name_str):
    color_map = {"0": "black", "1": "red", "2": "green", "3": "yellow", "4": "blue", "5": "cyan", "6": "magenta", "7": "black"} # Changed 'white' to 'black'
    default_color = "black"
    name_container = tk.Frame(parent, bg=parent.cget("bg"))
    current_text = ""
    current_color = default_color
    i = 0
    while i < len(name_str):
        if name_str[i] == '^' and i + 1 < len(name_str) and name_str[i+1] in color_map:
            if current_text:
                tk.Label(name_container, text=current_text, fg=current_color, font=("Arial", 10), bg=parent.cget("bg")).pack(side="left")
            current_text = ""
            current_color = color_map[name_str[i+1]]
            i += 2
        else:
            current_text += name_str[i]
            i += 1
    if current_text:
        tk.Label(name_container, text=current_text, fg=current_color, font=("Arial", 10), bg=parent.cget("bg")).pack(side="left")
    return name_container

def update_player_list(players):
    for lbl_item in player_labels:
        lbl_item.destroy()
    player_labels.clear()
    
    if not player_frame.winfo_exists():
        auto_adjust_window_geometry()
        return
        
    if not players:
        lbl = tk.Label(player_frame, text="No players", fg="gray", font=("Arial", 10))
        lbl.grid(row=0, column=0, sticky="w", padx=5)
        player_labels.append(lbl)
    else:
        sorted_players = sorted(players, key=lambda p: p.duration, reverse=True)
        for i, p in enumerate(sorted_players):
            player_line_frame = tk.Frame(player_frame)
            player_line_frame.pack(anchor="w", fill="x")
            player_line_frame.columnconfigure(0, weight=1)
            player_line_frame.columnconfigure(1, weight=0)

            original_name = p.name or "(anonymous)"
            truncated_name = truncate_text(original_name, MAX_PLAYER_NAME_CHARS)
            name_display_widget = render_colored_name(player_line_frame, truncated_name)
            name_display_widget.grid(row=0, column=0, sticky="w", padx=(5,0))

            time_text = format_seconds(p.duration)
            time_label = tk.Label(player_line_frame, text=time_text, fg="gray", font=("Arial", 10))
            time_label.grid(row=0, column=1, sticky="e", padx=(10,5))
            player_labels.append(player_line_frame)
            
    auto_adjust_window_geometry()

def auto_adjust_window_geometry():
    global root, preview_label, info_frame, separator, player_frame, button_frame
    if not root or not root.winfo_exists(): return
    root.update_idletasks()
    
    req_w_preview = 256 + 20
    req_w_info = info_frame.winfo_reqwidth() + 20
    req_w_player = player_frame.winfo_reqwidth() + 20
    req_w_buttons = button_frame.winfo_reqwidth() + 20
    
    new_window_width = max(req_w_preview, req_w_info, req_w_player, req_w_buttons, MIN_AUTO_WIDTH)
    
    h_preview = 192
    h_info = info_frame.winfo_reqheight()
    h_sep = separator.winfo_reqheight()
    h_player = player_frame.winfo_reqheight()
    h_buttons = button_frame.winfo_reqheight()
    
    calculated_height = (h_preview + h_info + h_sep + h_player + h_buttons + 55) # Paddings summed up
    final_height = max(calculated_height, MIN_WINDOW_HEIGHT)
    
    current_width = root.winfo_width()
    current_height = root.winfo_height()

    if current_width != new_window_width or current_height != final_height:
        root.geometry(f"{new_window_width}x{final_height}")
        root.update_idletasks()

# --- OS Specific Startup Management ---
def get_startup_folder():
    if sys.platform == "win32":
        return os.path.join(os.getenv('APPDATA'), 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')
    elif sys.platform.startswith('linux'):
        return os.path.expanduser('~/.config/autostart')
    elif sys.platform == "darwin":
        return os.path.expanduser('~/Library/LaunchAgents')
    return None

def manage_startup_registration(enable):
    global start_with_system_var, APP_NAME
    app_path = get_application_path()
    startup_folder = get_startup_folder()
    status_message = ""

    if not startup_folder or not os.path.exists(startup_folder):
        status_message = "OS not supported for automatic startup."
        if enable: start_with_system_var.set(False)
        return status_message

    if sys.platform == "win32":
        if not winshell:
            status_message = "Please add to startup manually.\n(winshell library not found)"
            if enable: start_with_system_var.set(False)
            return status_message
            
        shortcut_path = os.path.join(startup_folder, f"{APP_NAME}.lnk")
        if enable:
            try:
                target = app_path
                args = ""
                if not getattr(sys, 'frozen', False) and app_path.endswith(".py"):
                    python_exe = sys.executable.replace("python.exe", "pythonw.exe")
                    if not os.path.exists(python_exe): python_exe = sys.executable
                    target = python_exe
                    args = f'"{app_path}"'

                shell = Dispatch('WScript.Shell')
                shortcut = shell.CreateShortCut(shortcut_path)
                shortcut.Targetpath = target
                shortcut.Arguments = args
                shortcut.WindowStyle = 7 # Minimized
                shortcut.Description = f"Launch {APP_NAME}"
                shortcut.WorkingDirectory = os.path.dirname(app_path)
                if os.path.exists(resource_path("quake3.ico")):
                    shortcut.IconLocation = resource_path("quake3.ico")
                shortcut.save()
                status_message = f"{APP_NAME} added to startup."
            except Exception as e:
                status_message = f"Error adding to startup: {e}"
                if enable: start_with_system_var.set(False)
        else:
            if os.path.exists(shortcut_path):
                try:
                    os.remove(shortcut_path)
                    status_message = f"{APP_NAME} removed from startup."
                except Exception as e:
                    status_message = f"Error removing from startup: {e}"
                    if not enable: start_with_system_var.set(True)
            else:
                status_message = f"{APP_NAME} was not in startup."

    elif sys.platform.startswith('linux'):
        desktop_entry_path = os.path.join(startup_folder, f"{APP_NAME.lower().replace(' ', '-')}.desktop")
        if enable:
            content = f"""[Desktop Entry]
Type=Application
Name={APP_NAME}
Exec={sys.executable} "{app_path}"
Icon={resource_path("quake3.ico") if os.path.exists(resource_path("quake3.ico")) else ''}
Comment=Quake Server Viewer
Terminal=false
Categories=Utility;
"""
            try:
                with open(desktop_entry_path, "w") as f: f.write(content)
                os.chmod(desktop_entry_path, 0o755)
                status_message = f"{APP_NAME} .desktop entry created."
            except Exception as e:
                status_message = f"Error creating .desktop entry: {e}"
                if enable: start_with_system_var.set(False)
        else:
            if os.path.exists(desktop_entry_path):
                try:
                    os.remove(desktop_entry_path)
                    status_message = f"{APP_NAME} .desktop entry removed."
                except Exception as e:
                    status_message = f"Error removing .desktop: {e}"
                    if not enable: start_with_system_var.set(True)
            else:
                status_message = f"{APP_NAME} .desktop was not in startup."

    elif sys.platform == "darwin":
        status_message = "macOS: Add to Login Items via System Settings."
        if enable: start_with_system_var.set(False)

    return status_message

# --- Options Window ---
def open_options_window():
    global options_window, SERVER_ADDRESS, REFRESH_INTERVAL, show_thumbnail, map_name_var, root
    global start_minimized_on_next_launch_var, start_with_system_var, after_id_fetch_server_info

    if options_window is not None and options_window.winfo_exists():
        options_window.lift()
        options_window.focus_force()
        return

    options_window = tk.Toplevel(root)

    def on_options_close():
        global options_window
        if options_window:
            options_window.grab_release()
            options_window.destroy()
        options_window = None

    options_window.protocol("WM_DELETE_WINDOW", on_options_close)
    options_window.title("Options")
    options_window.transient(root)
    options_width, options_height = 400, 590
    
    try:
        if root and root.winfo_exists():
            root.update_idletasks()
            main_win_x, main_win_y = root.winfo_x(), root.winfo_y()
            main_win_width, main_win_height = root.winfo_width(), root.winfo_height()
            pos_x = main_win_x + (main_win_width // 2) - (options_width // 2)
            pos_y = main_win_y + (main_win_height // 2) - (options_height // 2)
            options_window.geometry(f"{options_width}x{options_height}+{pos_x}+{pos_y}")
        else:
            options_window.geometry(f"{options_width}x{options_height}")
    except tk.TclError:
        options_window.geometry(f"{options_width}x{options_height}")

    options_window.resizable(False, False)
    try:
        options_window.iconbitmap(resource_path("quake3.ico"))
    except tk.TclError: pass
    
    # --- Content ---
    button_char_width, button_pady_internal = 28, 3
    button_pack_pady_outer, status_label_pady_outer = (8, 2), (2, 8)

    app_settings_frame = tk.LabelFrame(options_window, text="Application Settings", padx=10, pady=10)
    app_settings_frame.pack(padx=10, pady=5, fill="x")
    
    tk.Checkbutton(app_settings_frame, text="Show map thumbnail", variable=show_thumbnail).pack(anchor="w", pady=(0,2))
    tk.Checkbutton(app_settings_frame, text="Start minimized to tray on next launch", variable=start_minimized_on_next_launch_var).pack(anchor="w", pady=(2,2))

    startup_status_var = tk.StringVar()
    startup_status_label = tk.Label(app_settings_frame, textvariable=startup_status_var, fg="blue", wraplength=360, justify=tk.LEFT)
    
    def update_startup_status_display(status_text):
        startup_status_var.set(status_text)
        if status_text:
            startup_status_label.pack(anchor="w", pady=(2,5), fill="x")
        else:
            startup_status_label.pack_forget()

    chk_start_with_system = tk.Checkbutton(app_settings_frame, text="Start with system (OS dependent)", variable=start_with_system_var, command=lambda: update_startup_status_display(manage_startup_registration(start_with_system_var.get())))
    chk_start_with_system.pack(anchor="w", pady=(2,0))
    startup_status_label.pack(anchor="w", pady=(0,0), fill="x")
    if not startup_status_var.get():
        startup_status_label.pack_forget()

    overall_status_var = tk.StringVar()
    def save_and_close_options():
        save_config()
        overall_status_var.set("Settings saved.")
        options_window.after(750, on_options_close)
    
    tk.Button(app_settings_frame, text="Save and Close", command=save_and_close_options, width=button_char_width, pady=button_pady_internal).pack(pady=button_pack_pady_outer, fill="x")
    tk.Label(app_settings_frame, textvariable=overall_status_var, fg="darkgreen").pack(pady=status_label_pady_outer)

    server_settings_frame = tk.LabelFrame(options_window, text="Server Settings", padx=10, pady=10)
    server_settings_frame.pack(padx=10, pady=5, fill="x")
    tk.Label(server_settings_frame, text="Server IP:Port").pack(anchor="w")
    entry_ip = tk.Entry(server_settings_frame, width=35)
    entry_ip.insert(0, f"{SERVER_ADDRESS[0]}:{SERVER_ADDRESS[1]}")
    entry_ip.pack(anchor="w", pady=(0,5))
    tk.Label(server_settings_frame, text="Update interval (seconds)").pack(anchor="w")
    entry_interval = tk.Entry(server_settings_frame, width=10)
    entry_interval.insert(0, str(REFRESH_INTERVAL))
    entry_interval.pack(anchor="w", pady=(0,5))
    server_status_var = tk.StringVar()

    def apply_server_settings_action():
        global SERVER_ADDRESS, REFRESH_INTERVAL, last_processed_map_name_for_image, after_id_fetch_server_info
        text_ip = entry_ip.get().strip()
        if ":" not in text_ip:
            server_status_var.set("Invalid IP format. Use IP:Port")
            return
        ip_val, port_str = text_ip.split(":", 1)
        try:
            port_val = int(port_str)
            new_server_address = (ip_val, port_val)
        except ValueError:
            server_status_var.set("Invalid port number.")
            return
        try:
            new_interval = int(entry_interval.get().strip())
            if new_interval < 1:
                server_status_var.set("Interval must be >= 1 second.")
                return
        except ValueError:
            server_status_var.set("Invalid interval value.")
            return
            
        settings_changed = (SERVER_ADDRESS != new_server_address or REFRESH_INTERVAL != new_interval)
        if settings_changed:
            SERVER_ADDRESS, REFRESH_INTERVAL = new_server_address, new_interval
            save_config()
            server_status_var.set("Live settings applied and saved.")
            if after_id_fetch_server_info:
                try: root.after_cancel(after_id_fetch_server_info)
                except tk.TclError: pass
                after_id_fetch_server_info = None

            player_count_var.set("-")
            map_name_var.set("Loading map...")
            server_name_var.set("Loading server...")
            ip_label_var.set("Loading IP...")
            error_message_var.set("")
            update_player_list([])
            set_placeholder_or_clear_preview()
            last_processed_map_name_for_image = None
            if root and root.winfo_exists() and not shutting_down:
                root.after(10, fetch_server_info)
        else:
            server_status_var.set("Settings are current.")

    tk.Button(server_settings_frame, text="Apply Live Server Settings", command=apply_server_settings_action, width=button_char_width, pady=button_pady_internal).pack(pady=button_pack_pady_outer, fill="x")
    tk.Label(server_settings_frame, textvariable=server_status_var, fg="green", wraplength=350).pack(pady=status_label_pady_outer)

    custom_image_frame = tk.LabelFrame(options_window, text="Custom Map Image (Download & Save)", padx=10, pady=10)
    custom_image_frame.pack(padx=10, pady=5, fill="x")
    tk.Label(custom_image_frame, text="Map Name (e.g., 'cpm22'):").pack(anchor="w")
    entry_custom_map_name = tk.Entry(custom_image_frame, width=45)
    entry_custom_map_name.pack(anchor="w", pady=(0,5))
    current_map = map_name_var.get()
    if current_map and current_map not in ["Loading map...", "N/A", "Connection failed"]:
        entry_custom_map_name.insert(0, current_map)
    tk.Label(custom_image_frame, text="Image URL (direct link to .jpg/.png):").pack(anchor="w")
    entry_custom_map_url = tk.Entry(custom_image_frame, width=45)
    entry_custom_map_url.pack(anchor="w", pady=(0,5))
    custom_image_status_var = tk.StringVar()

    def download_and_save_custom_image():
        global MAPSHOTS_DIR, map_name_var, last_processed_map_name_for_image, show_thumbnail
        map_n, url = entry_custom_map_name.get().strip(), entry_custom_map_url.get().strip()
        if not map_n or not url:
            custom_image_status_var.set("Map name and URL cannot be empty.")
            return
        
        sanitized_map_name = sanitize_filename(map_n)
        local_image_filename = f"{sanitized_map_name}.png"
        local_image_path = os.path.join(MAPSHOTS_DIR, local_image_filename)
        
        try:
            custom_image_status_var.set(f"Downloading for '{map_n}'...")
            if options_window.winfo_exists(): options_window.update_idletasks()
            
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = response.read()
            img = Image.open(BytesIO(data))
            if img.mode not in ['RGB', 'RGBA']: img = img.convert('RGBA' if 'A' in img.mode else 'RGB')
            img.resize((256, 192), Image.Resampling.LANCZOS).save(local_image_path, "PNG")
            
            custom_image_status_var.set(f"Image for '{map_n}' saved as\n'{local_image_filename}'.")
            if sanitized_map_name == sanitize_filename(map_name_var.get()):
                last_processed_map_name_for_image = None
                if show_thumbnail.get():
                    update_map_preview(map_name_var.get())
        except Exception as e:
            custom_image_status_var.set(f"An unexpected error occurred:\n{str(e)[:100]}")

    tk.Button(custom_image_frame, text="Save Custom Image", command=download_and_save_custom_image, width=button_char_width, pady=button_pady_internal).pack(pady=button_pack_pady_outer, fill="x")
    tk.Label(custom_image_frame, textvariable=custom_image_status_var, fg="blue", justify=tk.LEFT, wraplength=350).pack(pady=status_label_pady_outer)

    options_window.grab_set()

# --- System Tray and Window Management ---
def connect_to_server():
    try:
        webbrowser.open(f"steam://connect/{SERVER_ADDRESS[0]}:{SERVER_ADDRESS[1]}")
    except Exception as e:
        error_message_var.set("Error: Could not open Steam link.")
        print(f"ERROR: Could not open Steam link: {e}")

def on_minimize_to_tray(event=None):
    if root.state() == 'normal':
        root.withdraw()

def shutdown_application(icon=None, item=None):
    global tray_icon, root, shutting_down
    if shutting_down: return
    shutting_down = True
    if tray_icon:
        try:
            tray_icon.stop()
        except Exception as e:
            print(f"Warning: Error stopping tray icon: {e}")
        finally:
            tray_icon = None
    if root and root.winfo_exists():
        root.destroy()

def on_show_from_tray(icon=None, item=None):
    if root:
        root.after(0, lambda: [root.deiconify(), root.lift(), root.focus_force()])

def setup_tray_icon():
    global tray_icon
    try:
        icon_path = resource_path("quake3.ico")
        image = Image.open(icon_path)
        menu = pystray.Menu(
            pystray.MenuItem("Show", on_show_from_tray, default=True),
            pystray.MenuItem("Quit", shutdown_application)
        )
        tray_icon = pystray.Icon(APP_NAME.lower(), image, APP_NAME, menu)
        tray_icon.run()
    except Exception as e:
        print(f"Warning: Tray icon failed to start. Details: {e}")

# --- Main Application Setup ---
if __name__ == "__main__":
    root = tk.Tk()
    root.title(APP_NAME)
    
    start_minimized_on_next_launch_var = tk.BooleanVar()
    start_with_system_var = tk.BooleanVar()
    show_thumbnail = tk.BooleanVar(value=True)

    load_config()

    root.geometry(f"{MIN_AUTO_WIDTH}x580")
    root.minsize(MIN_AUTO_WIDTH, MIN_WINDOW_HEIGHT)
    root.resizable(width=False, height=False)
    try:
        root.iconbitmap(resource_path("quake3.ico"))
    except tk.TclError:
        print(f"Warning: Could not load window icon '{resource_path('quake3.ico')}'.")

    server_name_var = tk.StringVar(value="Loading server...")
    map_name_var = tk.StringVar(value="Loading map...")
    player_count_var = tk.StringVar(value="-")
    max_players_var = tk.StringVar(value="-")
    ip_label_var = tk.StringVar(value="Loading IP...")
    error_message_var = tk.StringVar()

    load_placeholder_image()

    preview_label = tk.Label(root, borderwidth=0, highlightthickness=0, padx=0, pady=0, anchor=tk.CENTER)
    preview_label.grid(row=0, column=0, columnspan=2, pady=0, sticky="ew")
    root.grid_rowconfigure(0, weight=0)

    info_frame = tk.Frame(root)
    info_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 5))
    info_labels_config = [("Server Name:", server_name_var), ("Map Name:", map_name_var), ("Players:", player_count_var), ("Max Players:", max_players_var), ("Server IP:", ip_label_var)]
    for i, (text, var) in enumerate(info_labels_config):
        tk.Label(info_frame, text=text, font=("Arial", 10)).grid(row=i, column=0, sticky="e", padx=(0,5))
        tk.Label(info_frame, textvariable=var, font=("Arial", 10), anchor="w").grid(row=i, column=1, sticky="w")

    separator = tk.Frame(root, height=2, bg="black")
    separator.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 10))
    
    player_frame = tk.Frame(root)
    player_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=5, padx=10)
    
    button_frame = tk.Frame(root)
    button_frame.grid(row=4, column=0, columnspan=2, pady=(10, 10))
    tk.Button(button_frame, text="Connect", command=connect_to_server, width=10).pack(side="left", padx=20)
    tk.Button(button_frame, text="Options", command=open_options_window, width=10).pack(side="right", padx=20)

    root.bind("<Unmap>", on_minimize_to_tray)
    root.protocol("WM_DELETE_WINDOW", shutdown_application)
    os.makedirs(MAPSHOTS_DIR, exist_ok=True)

    set_placeholder_or_clear_preview()
    auto_adjust_window_geometry()

    if start_minimized_on_next_launch_var.get():
        root.withdraw()

    root.after(500, fetch_server_info)
    
    tray_thread = threading.Thread(target=setup_tray_icon, daemon=True)
    tray_thread.start()
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        shutdown_application()