import tkinter as tk
import a2s
import socket
import configparser
import os
import sys
import webbrowser
import threading
from PIL import Image, ImageTk
import pystray
import urllib.request
from io import BytesIO
import re
# For creating shortcuts on Windows for "Start with system"
if sys.platform == "win32":
    import winshell # type: ignore
    from win32com.client import Dispatch # type: ignore

# --- Configuration ---
CONFIG_FILE = "config.ini"
APP_NAME = "QLView" # Used for shortcut name
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

# New global BooleanVars for options
start_minimized_on_next_launch_var = None 
start_with_system_var = None

# --- Helper Functions ---
def resource_path(relative_path):
    try: base_path = sys._MEIPASS
    except Exception: base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_application_path():
    if getattr(sys, 'frozen', False): # Check if running as a bundled executable (e.g., PyInstaller)
        return sys.executable
    return os.path.abspath(sys.argv[0]) # Path to the script file

def sanitize_filename(name):
    name = str(name); name = re.sub(r'[<>:"/\\|?*]', '_', name); name = re.sub(r'\s+', '_', name)
    return name[:100]

def truncate_text(text, max_chars):
    if len(text) > max_chars:
        return text[:max_chars-3] + "..."
    return text

def format_seconds(secs):
    mins = int(secs // 60); secs = int(secs % 60)
    return f"{mins}:{secs:02d}"

# --- Image Handling ---
def load_placeholder_image():
    global q3_logo_placeholder_photo, MAPSHOTS_DIR
    placeholder_filename = "placeholder.png"; placeholder_path = os.path.join(MAPSHOTS_DIR, placeholder_filename)
    custom_placeholder_loaded = False
    try:
        if os.path.exists(placeholder_path):
            img = Image.open(placeholder_path)
            if img.mode not in ['RGB', 'RGBA']: img = img.convert('RGBA' if 'A' in img.mode else 'RGB')
            img = img.resize((256, 192), Image.Resampling.LANCZOS)
            q3_logo_placeholder_photo = ImageTk.PhotoImage(img)
            print(f"INFO: Custom placeholder '{placeholder_path}' loaded successfully.")
            custom_placeholder_loaded = True
        else: print(f"INFO: Custom placeholder '{placeholder_path}' not found. Using default.")
    except Exception as e: print(f"WARNING: Could not load custom placeholder '{placeholder_path}': {e}. Using default.")
    if not custom_placeholder_loaded:
        try:
            img_gray = Image.new("RGB", (256, 192), color="#333333")
            q3_logo_placeholder_photo = ImageTk.PhotoImage(img_gray); print("INFO: Default gray placeholder created.")
        except Exception as e: print(f"WARNING: Could not create default gray placeholder image: {e}"); q3_logo_placeholder_photo = None

def set_placeholder_or_clear_preview():
    global preview_label, show_thumbnail, q3_logo_placeholder_photo, error_message_var, root
    if 'preview_label' in globals() and preview_label.winfo_exists():
        current_error = error_message_var.get()
        bg_color = root.cget("bg") if root and root.winfo_exists() else "SystemButtonFace"
        preview_width = preview_label.winfo_width()
        wrapl = max(200, preview_width - 20 if preview_width > 40 else MIN_AUTO_WIDTH - 40) 

        if current_error:
            preview_label.config(image="", text=current_error, font=("Arial", 11, "bold"), fg="white", bg="#B22222", borderwidth=0, highlightthickness=0, padx=0, pady=0, wraplength=wrapl)
            preview_label.image = None
        elif 'show_thumbnail' in globals() and show_thumbnail.get() and q3_logo_placeholder_photo:
            preview_label.config(text="", image=q3_logo_placeholder_photo, bg=bg_color, borderwidth=0, highlightthickness=0, padx=0, pady=0)
            preview_label.image = q3_logo_placeholder_photo
        else:
            preview_label.config(text="", image="", bg=bg_color, borderwidth=0, highlightthickness=0, padx=0, pady=0)
            preview_label.image = None
        if root and root.winfo_exists(): root.update_idletasks()

def update_map_preview(mapname_param):
    global preview_label, show_thumbnail, q3_logo_placeholder_photo, MAPSHOTS_DIR, error_message_var, root
    if mapname_param is None or not show_thumbnail.get():
        set_placeholder_or_clear_preview(); return
        
    mapname_to_use = str(mapname_param); sanitized_map_name = sanitize_filename(mapname_to_use)
    abs_mapshots_dir = os.path.abspath(MAPSHOTS_DIR)
    filenames_to_check = [f"{sanitized_map_name}.png", f"{sanitized_map_name}.jpg", f"{sanitized_map_name}.jpeg"]
    actual_local_image_path = None; pil_image_obj = None
    for filename in filenames_to_check:
        path_to_check = os.path.join(abs_mapshots_dir, filename)
        if os.path.exists(path_to_check):
            actual_local_image_path = path_to_check
            print(f"DEBUG: Local map image found: {actual_local_image_path}")
            try:
                img_opened = Image.open(actual_local_image_path)
                if img_opened.mode not in ['RGB', 'RGBA']: img_opened = img_opened.convert('RGBA' if 'A' in img_opened.mode else 'RGB')
                pil_image_obj = img_opened.resize((256, 192), Image.Resampling.LANCZOS)
                print(f"INFO: Successfully loaded and resized local map image: {actual_local_image_path}")
                break 
            except Exception as e:
                print(f"WARNING: Local image '{actual_local_image_path}' could not be loaded/converted: {e}"); pil_image_obj = None
                try: os.remove(actual_local_image_path); print(f"INFO: Damaged local image '{actual_local_image_path}' removed.")
                except OSError: pass
                actual_local_image_path = None 
    if not pil_image_obj and actual_local_image_path is None: 
         print(f"DEBUG: No local map image found for: {sanitized_map_name} (checked .png, .jpg, .jpeg)")
    bg_color = root.cget("bg") if root and root.winfo_exists() else "SystemButtonFace"
    if 'preview_label' in globals() and preview_label.winfo_exists():
        current_error = error_message_var.get(); preview_width = preview_label.winfo_width()
        wrapl = max(200, preview_width - 20 if preview_width > 40 else MIN_AUTO_WIDTH - 40)
        if current_error:
            preview_label.config(image="", text=current_error, font=("Arial", 11, "bold"), fg="white", bg="#B22222", borderwidth=0, highlightthickness=0, padx=0, pady=0, wraplength=wrapl)
            preview_label.image = None
        elif pil_image_obj:
            photo_to_display = ImageTk.PhotoImage(pil_image_obj)
            preview_label.config(text="", image=photo_to_display, bg=bg_color, borderwidth=0, highlightthickness=0, padx=0, pady=0); preview_label.image = photo_to_display
        elif q3_logo_placeholder_photo:
            preview_label.config(text="", image=q3_logo_placeholder_photo, bg=bg_color, borderwidth=0, highlightthickness=0, padx=0, pady=0); preview_label.image = q3_logo_placeholder_photo
        else:
            preview_label.config(text="", image="", bg=bg_color, borderwidth=0, highlightthickness=0, padx=0, pady=0); preview_label.image = None
        if root and root.winfo_exists(): root.update_idletasks()

# --- Config Handling ---
def load_config():
    global SERVER_ADDRESS, REFRESH_INTERVAL, show_thumbnail, start_minimized_on_next_launch_var, start_with_system_var
    config = configparser.ConfigParser(interpolation=None); SERVER_ADDRESS = DEFAULT_SERVER_ADDRESS; REFRESH_INTERVAL = DEFAULT_REFRESH_INTERVAL
    
    # Initialize BooleanVars if they are not already (e.g. before root window exists)
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

            if 'show_thumbnail' in globals() and isinstance(show_thumbnail, tk.BooleanVar): show_thumbnail.set(thumb)
            start_minimized_on_next_launch_var.set(start_minimized)
            start_with_system_var.set(start_os)
            
            ip, port_str = ip_port.split(":"); SERVER_ADDRESS = (ip, int(port_str)); REFRESH_INTERVAL = interval
        except (configparser.Error, ValueError) as e:
            print(f"WARNING: Error reading config file '{CONFIG_FILE}': {e}. Using default settings.")
            if 'show_thumbnail' in globals() and isinstance(show_thumbnail, tk.BooleanVar): show_thumbnail.set(True)
            start_minimized_on_next_launch_var.set(False); start_with_system_var.set(False)
            SERVER_ADDRESS = DEFAULT_SERVER_ADDRESS; REFRESH_INTERVAL = DEFAULT_REFRESH_INTERVAL; save_config()
    else:
        if 'show_thumbnail' in globals() and isinstance(show_thumbnail, tk.BooleanVar): show_thumbnail.set(True)
        start_minimized_on_next_launch_var.set(False); start_with_system_var.set(False)
        save_config()

def save_config():
    global SERVER_ADDRESS, REFRESH_INTERVAL, show_thumbnail, start_minimized_on_next_launch_var, start_with_system_var
    config = configparser.ConfigParser(interpolation=None)
    if not config.has_section("settings"): config.add_section("settings")
    config.set("settings", "server", f"{SERVER_ADDRESS[0]}:{SERVER_ADDRESS[1]}"); config.set("settings", "interval", str(REFRESH_INTERVAL))
    if 'show_thumbnail' in globals() and isinstance(show_thumbnail, tk.BooleanVar): config.set("settings", "thumbnail", str(show_thumbnail.get()))
    else: config.set("settings", "thumbnail", "True")
    
    if start_minimized_on_next_launch_var is not None: config.set("settings", "start_minimized", str(start_minimized_on_next_launch_var.get()))
    else: config.set("settings", "start_minimized", "False")
    if start_with_system_var is not None: config.set("settings", "start_with_system", str(start_with_system_var.get()))
    else: config.set("settings", "start_with_system", "False")
        
    try:
        with open(CONFIG_FILE, "w") as f: config.write(f)
    except IOError as e: print(f"ERROR: Could not write to config file '{CONFIG_FILE}': {e}")

# --- Server Interaction ---
def fetch_server_info():
    global last_processed_map_name_for_image, last_show_thumbnail_state_for_image, map_name_var, server_name_var, player_count_var, max_players_var, ip_label_var, error_message_var, SERVER_ADDRESS, REFRESH_INTERVAL, show_thumbnail, root, tray_icon, after_id_fetch_server_info
    try:
        info = a2s.info(SERVER_ADDRESS, timeout=3.0); players = a2s.players(SERVER_ADDRESS, timeout=3.0)
        if error_message_var.get(): error_message_var.set(""); update_map_preview(info.map_name if info and show_thumbnail.get() else None)
        new_map_name_from_server = info.map_name; server_name_from_server = info.server_name
        map_name_var.set(truncate_text(new_map_name_from_server, MAX_SERVER_MAP_NAME_CHARS))
        server_name_var.set(truncate_text(server_name_from_server, MAX_SERVER_MAP_NAME_CHARS))
        player_count_var.set(str(info.player_count)); max_players_var.set(str(info.max_players)); ip_label_var.set(f"{SERVER_ADDRESS[0]}:{SERVER_ADDRESS[1]}")
        current_show_thumbnail_setting = show_thumbnail.get()
        map_has_changed = (new_map_name_from_server != last_processed_map_name_for_image); thumbnail_setting_has_changed = (current_show_thumbnail_setting != last_show_thumbnail_state_for_image)
        if map_has_changed or thumbnail_setting_has_changed:
            update_map_preview(new_map_name_from_server if current_show_thumbnail_setting else None)
            if current_show_thumbnail_setting: last_processed_map_name_for_image = new_map_name_from_server
            else: last_processed_map_name_for_image = None
            last_show_thumbnail_state_for_image = current_show_thumbnail_setting
        update_player_list(players)
        root.title(f"{APP_NAME} – {player_count_var.get()}/{max_players_var.get()}")
        if tray_icon and hasattr(tray_icon, 'update_menu'): tray_icon.title = f"Players: {player_count_var.get()}/{max_players_var.get()}"
    except socket.timeout: print(f"WARNING: Timeout connecting to server {SERVER_ADDRESS}"); handle_connection_error("Timeout connecting to server.")
    except ConnectionRefusedError: print(f"WARNING: Connection refused by server {SERVER_ADDRESS}"); handle_connection_error("Connection refused by server.")
    except Exception as e: print(f"ERROR: Failed to fetch server info from {SERVER_ADDRESS}: {e}"); handle_connection_error(f"Error fetching server info.")
    finally:
        if root and root.winfo_exists() and not shutting_down:
            after_id_fetch_server_info = root.after(max(1000, REFRESH_INTERVAL * 1000), fetch_server_info)

def handle_connection_error(specific_error_msg="Failed to connect."):
    global server_name_var, map_name_var, player_count_var, ip_label_var, error_message_var
    error_message_var.set(specific_error_msg)
    if player_count_var.get() == "-": server_name_var.set("Connection failed"); map_name_var.set("N/A"); ip_label_var.set("N/A")
    set_placeholder_or_clear_preview(); update_player_list([])

# --- GUI Rendering & Auto Height ---
def render_colored_name(parent, name_str):
    color_map = { "0": "black", "1": "red", "2": "green", "3": "yellow", "4": "blue", "5": "cyan", "6": "magenta", "7": "white" }
    default_color = "white" if parent.cget("bg") == "black" else "black"; name_container = tk.Frame(parent, bg=parent.cget("bg"))
    current_text = ""; current_color = default_color; i = 0
    while i < len(name_str):
        if name_str[i] == '^' and i + 1 < len(name_str) and name_str[i+1] in color_map:
            if current_text: tk.Label(name_container, text=current_text, fg=current_color, font=("Arial", 10), bg=parent.cget("bg")).pack(side="left")
            current_text = ""; current_color = color_map[name_str[i+1]]; i += 2
        else: current_text += name_str[i]; i += 1
    if current_text: tk.Label(name_container, text=current_text, fg=current_color, font=("Arial", 10), bg=parent.cget("bg")).pack(side="left")
    return name_container

def update_player_list(players):
    for lbl_item in player_labels: lbl_item.destroy()
    player_labels.clear();
    if not player_frame.winfo_exists(): auto_adjust_window_geometry(); return
    if not players:
        lbl = tk.Label(player_frame, text="No players", fg="gray", font=("Arial", 10));
        lbl.grid(row=0, column=0, sticky="w", padx=5) 
        player_labels.append(lbl)
    else:
        sorted_players = sorted(players, key=lambda p: p.duration, reverse=True)
        for i, p in enumerate(sorted_players):
            player_line_frame = tk.Frame(player_frame)
            player_line_frame.pack(anchor="w", fill="x") 
            player_line_frame.columnconfigure(0, weight=1) 
            player_line_frame.columnconfigure(1, weight=0) 
            original_name = p.name or "(anonymous)"; truncated_name = truncate_text(original_name, MAX_PLAYER_NAME_CHARS)
            name_display_widget = render_colored_name(player_line_frame, truncated_name)
            name_display_widget.grid(row=0, column=0, sticky="w", padx=(5,0))
            time_text = format_seconds(p.duration)
            time_label = tk.Label(player_line_frame, text=time_text, fg="gray", font=("Arial", 10))
            time_label.grid(row=0, column=1, sticky="e", padx=(10,5))
            player_labels.append(player_line_frame)
    auto_adjust_window_geometry()

def auto_adjust_window_geometry():
    global root, preview_label, info_frame, separator, player_frame, button_frame, MIN_AUTO_WIDTH, MIN_WINDOW_HEIGHT
    if not root or not root.winfo_exists(): return
    root.update_idletasks()
    window_horizontal_padding = 20 
    req_w_preview = 256 + window_horizontal_padding 
    info_padx = info_frame.grid_info().get('padx', 0) * 2 if isinstance(info_frame.grid_info().get('padx', 0), int) else 0
    player_padx = player_frame.grid_info().get('padx', 0) * 2 if isinstance(player_frame.grid_info().get('padx', 0), int) else 0
    req_w_info = info_frame.winfo_reqwidth() + info_padx
    req_w_player = player_frame.winfo_reqwidth() + player_padx
    req_w_buttons = button_frame.winfo_reqwidth() + window_horizontal_padding
    new_window_width = max(req_w_preview, req_w_info, req_w_player, req_w_buttons, MIN_AUTO_WIDTH)
    h_preview = 192; pady_preview_bottom = 0
    h_info = info_frame.winfo_reqheight(); pady_info_top = 0; pady_info_bottom = 5
    h_sep = separator.winfo_reqheight(); pady_sep_top = 5; pady_sep_bottom = 10
    h_player = player_frame.winfo_reqheight(); pady_player_top = 5; pady_player_bottom = 5
    h_buttons = button_frame.winfo_reqheight(); pady_buttons_top = 10; pady_buttons_bottom = 10
    calculated_height = (h_preview + pady_preview_bottom + pady_info_top + h_info + pady_info_bottom +
                         pady_sep_top + h_sep + pady_sep_bottom + pady_player_top + h_player + pady_player_bottom +
                         pady_buttons_top + h_buttons + pady_buttons_bottom + 5)
    final_height = max(calculated_height, MIN_WINDOW_HEIGHT)
    current_width = root.winfo_width(); current_height = root.winfo_height()
    if current_width != new_window_width or current_height != final_height:
        print(f"INFO: Auto-adjusting geometry to: {new_window_width}x{final_height}")
        root.geometry(f"{new_window_width}x{final_height}")
        root.update_idletasks()

# --- OS Specific Startup Management ---
def get_startup_folder():
    if sys.platform == "win32":
        return os.path.join(os.getenv('APPDATA'), 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')
    elif sys.platform == "darwin": # macOS
        return os.path.expanduser('~/Library/LaunchAgents')
    elif sys.platform.startswith('linux'):
        return os.path.expanduser('~/.config/autostart')
    return None

def manage_startup_registration(enable):
    global start_with_system_var, APP_NAME
    app_path = get_application_path()
    startup_folder = get_startup_folder()
    status_message = ""

    if not startup_folder:
        status_message = "OS not supported for automatic startup."
        print(f"WARNING: {status_message}")
        if enable: start_with_system_var.set(False) # Revert checkbox if OS not supported
        return status_message

    if sys.platform == "win32":
        shortcut_path = os.path.join(startup_folder, f"{APP_NAME}.lnk")
        if enable:
            try:
                if not os.path.exists(app_path):
                    raise FileNotFoundError(f"Application path not found: {app_path}")
                
                # For .py scripts, we need to run "python.exe yourscript.py"
                # For .exe (frozen), app_path is directly the .exe
                target = app_path
                args = ""
                if not getattr(sys, 'frozen', False) and app_path.endswith(".py"): # Running as .py script
                    # Find pythonw.exe to run without console
                    python_exe = sys.executable.replace("python.exe", "pythonw.exe")
                    if not os.path.exists(python_exe): # Fallback to python.exe if pythonw not found
                        python_exe = sys.executable
                    target = python_exe
                    args = f'"{app_path}"' # Script path as argument

                # Using winshell if available, otherwise print instructions
                if 'winshell' in sys.modules:
                    shell = Dispatch('WScript.Shell')
                    shortcut = shell.CreateShortCut(shortcut_path)
                    shortcut.Targetpath = target
                    shortcut.Arguments = args
                    shortcut.WindowStyle = 7 # 7 - Minimized, 1 - Normal, 3 - Maximized
                    shortcut.Description = f"Launch {APP_NAME}"
                    shortcut.WorkingDirectory = os.path.dirname(app_path) # Set working directory
                    if resource_path("quake3.ico"): # Optional: set icon
                        shortcut.IconLocation = resource_path("quake3.ico")
                    shortcut.save()
                    status_message = f"{APP_NAME} added to startup."
                    print(f"INFO: Created shortcut at {shortcut_path} targeting '{target}' with args '{args}'")
                else:
                    status_message = "Please add to startup manually.\n(winshell library not found)"
                    print("WARNING: winshell library not found. Cannot create shortcut automatically for Windows.")

            except Exception as e:
                status_message = f"Error adding to startup: {e}"
                print(f"ERROR: {status_message}")
                if enable: start_with_system_var.set(False) # Revert on error
        else: # Disable
            if os.path.exists(shortcut_path):
                try:
                    os.remove(shortcut_path)
                    status_message = f"{APP_NAME} removed from startup."
                    print(f"INFO: Removed shortcut: {shortcut_path}")
                except Exception as e:
                    status_message = f"Error removing from startup: {e}"
                    print(f"ERROR: {status_message}")
                    if not enable: start_with_system_var.set(True) # Revert on error
            else:
                status_message = f"{APP_NAME} was not in startup."
    
    # Placeholder for Linux (.desktop file) and macOS (LaunchAgent .plist)
    elif sys.platform.startswith('linux'):
        desktop_entry_name = f"{APP_NAME.lower().replace(' ', '-')}.desktop"
        desktop_entry_path = os.path.join(startup_folder, desktop_entry_name)
        if enable:
            # Create .desktop file
            content = f"""[Desktop Entry]
Type=Application
Name={APP_NAME}
Exec={sys.executable} "{app_path}" {'--minimized' if start_minimized_on_next_launch_var.get() else ''}
Icon={resource_path("quake3.ico") if os.path.exists(resource_path("quake3.ico")) else ''}
Comment=Quake Server Viewer
Terminal=false
Categories=Utility;
"""
            try:
                with open(desktop_entry_path, "w") as f: f.write(content)
                os.chmod(desktop_entry_path, 0o755) # Make it executable
                status_message = f"{APP_NAME} .desktop entry created."
                print(f"INFO: Created .desktop entry: {desktop_entry_path}")
            except Exception as e:
                status_message = f"Error creating .desktop entry: {e}"; print(f"ERROR: {status_message}")
                if enable: start_with_system_var.set(False)
        else:
            if os.path.exists(desktop_entry_path):
                try: os.remove(desktop_entry_path); status_message = f"{APP_NAME} .desktop entry removed."
                except Exception as e: status_message = f"Error removing .desktop: {e}"; print(f"ERROR: {status_message}");
                if not enable: start_with_system_var.set(True) 
            else: status_message = f"{APP_NAME} .desktop was not in startup."


    elif sys.platform == "darwin":
        # macOS requires a .plist file in ~/Library/LaunchAgents
        status_message = "macOS: Add to Login Items via System Settings."
        print("INFO: For macOS, please add the application to Login Items manually via System Settings > General > Login Items.")
        if enable: start_with_system_var.set(False) # Cannot automate easily

    return status_message


# --- Options Window ---


# Ensure this global variable is declared at the top of your script:
# options_window = None

def open_options_window():
    global options_window 
    # Other globals needed by the content of the options window
    global SERVER_ADDRESS, REFRESH_INTERVAL, show_thumbnail, map_name_var, root
    global start_minimized_on_next_launch_var, start_with_system_var, after_id_fetch_server_info 

    # 1. Check if a valid options window already exists and show it
    if options_window is not None:
        try:
            if options_window.winfo_exists():
                options_window.lift()
                options_window.focus_force()
                # print("INFO: Existing options window lifted and focused.") # Optional debug
                return
            else:
                # print("INFO: Options window reference was stale (winfo_exists() failed), resetting.") # Optional debug
                options_window = None
        except tk.TclError:
            # print("INFO: TclError checking stale options window, resetting.") # Optional debug
            options_window = None

    # 2. If we are here, no valid options window exists. Create a new one.
    current_options_win_local = None 
    try:
        current_options_win_local = tk.Toplevel(root)
    except tk.TclError as e:
        print(f"ERROR: CRITICAL - Failed to create Toplevel for options: {e}")
        if options_window == current_options_win_local: 
            options_window = None
        return

    if not isinstance(current_options_win_local, tk.Toplevel):
        print(f"ERROR: CRITICAL - Toplevel creation did not return a valid Toplevel object. Got: {type(current_options_win_local)}")
        if current_options_win_local and hasattr(current_options_win_local, 'destroy'):
             try: current_options_win_local.destroy()
             except: pass
        options_window = None 
        return

    # 3. Define the close handler for THIS specific instance.
    def on_actual_options_close_handler():
        global options_window 
        win_to_close = current_options_win_local 
        is_current_window_valid = False
        try:
            if win_to_close and win_to_close.winfo_exists():
                is_current_window_valid = True
        except tk.TclError: 
            is_current_window_valid = False 
        if is_current_window_valid:
            # print(f"INFO: Closing options window ({win_to_close}). Releasing grab and destroying.") # Optional debug
            win_to_close.grab_release()
            win_to_close.destroy()
        # else:
            # print(f"INFO: Options window ({win_to_close}) already destroyed or invalid when on_close handler called.") # Optional debug
        if options_window == win_to_close:
            options_window = None
            # print("INFO: Global options_window tracker reset.") # Optional debug

    # 4. Attempt to set the protocol on the NEW local instance.
    try:
        if not (current_options_win_local and current_options_win_local.winfo_exists()):
             raise tk.TclError(f"Invalid Toplevel instance ('{current_options_win_local}') before setting protocol (winfo_exists failed).")
        current_options_win_local.protocol("WM_DELETE_WINDOW", on_actual_options_close_handler)
        # print(f"INFO: WM_DELETE_WINDOW protocol set for options window ({current_options_win_local}).") # Optional debug
    except (tk.TclError, AttributeError) as e: 
        print(f"ERROR: CRITICAL - Failed to set WM_DELETE_WINDOW protocol: {e} on window {current_options_win_local}")
        try:
            if current_options_win_local and current_options_win_local.winfo_exists(): 
                current_options_win_local.destroy()
        except tk.TclError: pass 
        options_window = None; return 

    # 5. Configure the window (title, transient, geometry, etc.) using current_options_win_local.
    current_options_win_local.title("Options")
    current_options_win_local.transient(root) 
    options_width = 400
    options_height = 590 # Adjusted height based on content
    try:
        if root and root.winfo_exists(): 
            root.update_idletasks() 
            main_win_x = root.winfo_x(); main_win_y = root.winfo_y()
            main_win_width = root.winfo_width(); main_win_height = root.winfo_height()
            pos_x = main_win_x + (main_win_width // 2) - (options_width // 2)
            pos_y = main_win_y + (main_win_height // 2) - (options_height // 2)
            current_options_win_local.geometry(f"{options_width}x{options_height}+{pos_x}+{pos_y}")
        else: current_options_win_local.geometry(f"{options_width}x{options_height}")
    except tk.TclError as e: 
        print(f"WARNING: Could not position options window relative to main window: {e}")
        current_options_win_local.geometry(f"{options_width}x{options_height}") 
    current_options_win_local.resizable(False, False)
    try: current_options_win_local.iconbitmap(resource_path("quake3.ico"))
    except tk.TclError: pass 

    # --- Content for options_window (parent is current_options_win_local) ---
    
    # Common button styling
    button_char_width = 28 # Adjusted for potentially longer text
    button_pady_internal = 3 
    button_pack_pady_outer = (8, 2) # Increased top padding for buttons
    status_label_pady_outer = (2, 8) # Increased bottom padding for status labels

    app_settings_frame = tk.LabelFrame(current_options_win_local, text="Application Settings", padx=10, pady=10)
    app_settings_frame.pack(padx=10, pady=5, fill="x") # Reduced overall frame pady
    
    chk_show_thumbnail = tk.Checkbutton(app_settings_frame, text="Show map thumbnail", variable=show_thumbnail); 
    chk_show_thumbnail.pack(anchor="w", pady=(0,2)) # Reduced bottom padding
    
    chk_start_minimized = tk.Checkbutton(app_settings_frame, text="Start minimized to tray on next launch", variable=start_minimized_on_next_launch_var); 
    chk_start_minimized.pack(anchor="w", pady=(2,2)) # Consistent padding

    chk_start_with_system = tk.Checkbutton(app_settings_frame, text="Start with system (OS dependent)", variable=start_with_system_var, 
                                           command=lambda: startup_status_var.set(manage_startup_registration(start_with_system_var.get()))); 
    chk_start_with_system.pack(anchor="w", pady=(2,0)) # Reduced bottom padding

    # Status label for "Start with system" - only show if it has content
    startup_status_var = tk.StringVar()
    startup_status_label = tk.Label(app_settings_frame, textvariable=startup_status_var, fg="blue", wraplength=360, justify=tk.LEFT)
    # Pack it later if startup_status_var is set, or manage visibility.
    # For now, let's pack it with minimal padding if it's intended to be always there but possibly empty.
    # To remove the space completely when empty, one would need to pack/unpack it dynamically.
    # Let's assume the user wants it to appear right after the checkbox if there's a message.
    # The provided screenshot does not show this label having content.
    # We will pack the "Save and Close" button directly after "Start with system" checkbox for now.
    # If startup_status_var gets text, it will appear below the checkbox.
    startup_status_label.pack(anchor="w", pady=(0,0), fill="x") # Minimal pady for now, will be hidden if empty
    if not startup_status_var.get(): # Hide if empty initially
        startup_status_label.pack_forget()

    # Function to show/hide startup_status_label
    def update_startup_status_display(status_text):
        startup_status_var.set(status_text)
        if status_text:
            startup_status_label.pack(anchor="w", pady=(2,5), fill="x", after=chk_start_with_system)
        else:
            startup_status_label.pack_forget()
    # Modify command for chk_start_with_system
    chk_start_with_system.config(command=lambda: update_startup_status_display(manage_startup_registration(start_with_system_var.get())))


    overall_status_var = tk.StringVar() 
    def save_and_close_options(): 
        save_config() 
        overall_status_var.set("Settings saved.") 
        print("INFO: Settings saved from options window via 'Save and Close'.")
        current_options_win_local.after(750, on_actual_options_close_handler)

    tk.Button(app_settings_frame, text="Save and Close", command=save_and_close_options, width=button_char_width, pady=button_pady_internal).pack(pady=button_pack_pady_outer, fill="x") 
    tk.Label(app_settings_frame, textvariable=overall_status_var, fg="darkgreen").pack(pady=status_label_pady_outer)


    server_settings_frame = tk.LabelFrame(current_options_win_local, text="Server Settings", padx=10, pady=10)
    server_settings_frame.pack(padx=10, pady=5, fill="x")
    tk.Label(server_settings_frame, text="Server IP:Port").pack(anchor="w")
    entry_ip = tk.Entry(server_settings_frame, width=35); entry_ip.insert(0, f"{SERVER_ADDRESS[0]}:{SERVER_ADDRESS[1]}"); entry_ip.pack(anchor="w", pady=(0,5))
    tk.Label(server_settings_frame, text="Update interval (seconds)").pack(anchor="w")
    entry_interval = tk.Entry(server_settings_frame, width=10); entry_interval.insert(0, str(REFRESH_INTERVAL)); entry_interval.pack(anchor="w", pady=(0,5))
    server_status_var = tk.StringVar() 
    
    def apply_server_settings_action(): 
        global SERVER_ADDRESS, REFRESH_INTERVAL, last_processed_map_name_for_image, after_id_fetch_server_info
        global player_count_var, map_name_var, server_name_var, ip_label_var, error_message_var, root
        text_ip = entry_ip.get().strip()
        if ":" not in text_ip: server_status_var.set("Invalid IP format. Use IP:Port"); return
        ip_val, port_str = text_ip.split(":", 1); new_server_address_tuple = None
        try: port_val = int(port_str); new_server_address_tuple = (ip_val, port_val)
        except ValueError: server_status_var.set("Invalid port number."); return
        new_refresh_interval_val = REFRESH_INTERVAL
        try:
            interval_val_from_entry = int(entry_interval.get().strip())
            if interval_val_from_entry < 1: server_status_var.set("Interval must be >= 1 second."); return
            new_refresh_interval_val = interval_val_from_entry
        except ValueError: server_status_var.set("Invalid interval value."); return
        settings_changed = (SERVER_ADDRESS != new_server_address_tuple or REFRESH_INTERVAL != new_refresh_interval_val)
        if settings_changed:
            SERVER_ADDRESS = new_server_address_tuple; REFRESH_INTERVAL = new_refresh_interval_val
            save_config() 
            server_status_var.set("Live settings applied and saved.")
            if after_id_fetch_server_info: 
                try: root.after_cancel(after_id_fetch_server_info)
                except tk.TclError: pass 
                after_id_fetch_server_info = None
            player_count_var.set("-"); map_name_var.set("Loading map..."); server_name_var.set("Loading server..."); ip_label_var.set("Loading IP...")
            error_message_var.set(""); update_player_list([]); set_placeholder_or_clear_preview(); last_processed_map_name_for_image = None
            if root and root.winfo_exists() and not shutting_down: root.after(10, fetch_server_info)
        else: server_status_var.set("Settings are current.")
    tk.Button(server_settings_frame, text="Apply Live Server Settings", command=apply_server_settings_action, width=button_char_width, pady=button_pady_internal).pack(pady=button_pack_pady_outer, fill="x")
    tk.Label(server_settings_frame, textvariable=server_status_var, fg="green", wraplength=350).pack(pady=status_label_pady_outer)

    custom_image_frame = tk.LabelFrame(current_options_win_local, text="Custom Map Image (Download & Save)", padx=10, pady=10)
    custom_image_frame.pack(padx=10, pady=5, fill="x")
    tk.Label(custom_image_frame, text="Map Name (e.g., 'cpm22'):").pack(anchor="w")
    entry_custom_map_name = tk.Entry(custom_image_frame, width=45); entry_custom_map_name.pack(anchor="w", pady=(0,5))
    current_map = map_name_var.get()
    if current_map and current_map not in ["Loading map...", "N/A", "Connection failed"]: entry_custom_map_name.insert(0, current_map)
    tk.Label(custom_image_frame, text="Image URL (direct link to .jpg/.png):").pack(anchor="w")
    entry_custom_map_url = tk.Entry(custom_image_frame, width=45); entry_custom_map_url.pack(anchor="w", pady=(0,5))
    custom_image_status_var = tk.StringVar()
    def download_and_save_custom_image():
        global MAPSHOTS_DIR, map_name_var, last_processed_map_name_for_image, show_thumbnail
        map_n_val = entry_custom_map_name.get().strip(); url_val = entry_custom_map_url.get().strip()
        if not map_n_val: custom_image_status_var.set("Map name cannot be empty."); return
        if not url_val: custom_image_status_var.set("Image URL cannot be empty."); return
        sanitized_map_name = sanitize_filename(map_n_val); local_image_filename = f"{sanitized_map_name}.png"; local_image_path = os.path.join(MAPSHOTS_DIR, local_image_filename)
        try:
            custom_image_status_var.set(f"Downloading for '{map_n_val}'..."); 
            if current_options_win_local and current_options_win_local.winfo_exists(): 
                 current_options_win_local.update_idletasks()
            req = urllib.request.Request(url_val, headers={'User-Agent': 'Mozilla/5.0'});
            with urllib.request.urlopen(req, timeout=10) as response: data = response.read()
            img = Image.open(BytesIO(data))
            if img.mode not in ['RGB', 'RGBA']: img = img.convert('RGBA' if 'A' in img.mode else 'RGB')
            img_resized = img.resize((256, 192), Image.Resampling.LANCZOS); img_resized.save(local_image_path, "PNG")
            custom_image_status_var.set(f"Image for '{map_n_val}' saved as\n'{local_image_filename}'."); print(f"INFO: Custom image for '{map_n_val}' saved to '{local_image_path}'.")
            if sanitized_map_name == sanitize_filename(map_name_var.get()):
                last_processed_map_name_for_image = None; custom_image_status_var.set(custom_image_status_var.get() + "\nPreview will update shortly.")
                if show_thumbnail.get(): update_map_preview(map_name_var.get())
        except urllib.error.URLError as e: custom_image_status_var.set(f"Download Error: URL Issue\n{e.reason}")
        except urllib.error.HTTPError as e: custom_image_status_var.set(f"Download Error: HTTP Issue\n{e.code} {e.reason}")
        except socket.timeout: custom_image_status_var.set("Download Error: Timeout")
        except IOError: custom_image_status_var.set(f"Image Error: Invalid data or\ncannot save to '{local_image_filename}'.")
        except Exception as e: custom_image_status_var.set(f"An unexpected error occurred:\n{str(e)[:100]}")
    
    tk.Button(custom_image_frame, text="Save Custom Image", command=download_and_save_custom_image, width=button_char_width, pady=button_pady_internal).pack(pady=button_pack_pady_outer, fill="x") # Applied consistent styling
    tk.Label(custom_image_frame, textvariable=custom_image_status_var, fg="blue", justify=tk.LEFT, wraplength=350).pack(pady=status_label_pady_outer)
    
    # 6. After all content is packed and configured, set grab and assign to global.
    try:
        if current_options_win_local and current_options_win_local.winfo_exists():
            current_options_win_local.grab_set()
            options_window = current_options_win_local 
            print(f"INFO: Options window ({options_window}) opened successfully and grab_set.")
        else: 
            print("ERROR: Options window (local) became invalid before grab_set / global assignment.")
            if options_window == current_options_win_local : options_window = None 
    except tk.TclError as e:
        print(f"ERROR: Failed to grab_set options window: {e}")
        if current_options_win_local and current_options_win_local.winfo_exists():
            try: current_options_win_local.destroy()
            except tk.TclError: pass
        if options_window == current_options_win_local : options_window = None

# --- System Tray and Window Management ---
def connect_to_server():
    ip_val, port_val = SERVER_ADDRESS; url_val = f"steam://connect/{ip_val}:{port_val}"
    try: webbrowser.open(url_val)
    except Exception as e: print(f"ERROR: Could not open Steam link: {e}"); error_message_var.set("Error: Could not open Steam link.")

def on_minimize_to_tray(event=None):
    if root and root.winfo_exists(): root.withdraw()

def shutdown_application(icon=None, item=None):
    global tray_icon, root, shutting_down
    if shutting_down: return
    shutting_down = True; print("INFO: Shutdown sequence initiated.")
    if tray_icon is not None:
        print("INFO: Stopping tray icon...")
        try: tray_icon.stop()
        except Exception as e: print(f"WARNING: Error stopping tray icon: {e}")
        finally: tray_icon = None
    try:
        if root is not None and root.winfo_exists(): print("INFO: Destroying main window and exiting application."); root.destroy()
    except tk.TclError: print("INFO: Main window already destroyed or inaccessible during shutdown.")

def on_show_from_tray(icon=None, item=None):
    if root and root.winfo_exists(): root.after(0, lambda: [root.deiconify(), root.lift(), root.focus_force()])

def setup_tray_icon():
    global tray_icon
    try:
        icon_path = resource_path("quake3.ico"); image = Image.open(icon_path)
        menu = pystray.Menu(pystray.MenuItem("Show", on_show_from_tray, default=True), pystray.MenuItem("Quit", shutdown_application))
        tray_icon = pystray.Icon(APP_NAME.lower(), image, APP_NAME, menu); print("INFO: Starting Tray Icon."); tray_icon.run() # Use APP_NAME
    except FileNotFoundError: print(f"WARNING: Tray icon 'quake3.ico' not found at '{icon_path}'. Tray will not start.")
    except Exception as e: print(f"---!! ERROR IN TRAY ICON THREAD !!----\nDetails: {e}")

# --- Main Application Setup ---
if __name__ == "__main__":
    root = tk.Tk(); root.title(APP_NAME) # Use APP_NAME
    
    # Initialize BooleanVars that are used in load_config before root exists for them
    start_minimized_on_next_launch_var = tk.BooleanVar()
    start_with_system_var = tk.BooleanVar()
    show_thumbnail = tk.BooleanVar(value=True) # Default value for show_thumbnail

    load_config() # Load settings, including start_minimized and start_with_system

    root.geometry(f"{MIN_AUTO_WIDTH}x580"); root.minsize(MIN_AUTO_WIDTH, MIN_WINDOW_HEIGHT)
    root.resizable(width=False, height=False)
    try: root.iconbitmap(resource_path("quake3.ico"))
    except tk.TclError: print(f"WARNING: Could not load window icon '{resource_path('quake3.ico')}'.")

    server_name_var = tk.StringVar(value="Loading server..."); map_name_var = tk.StringVar(value="Loading map...")
    player_count_var = tk.StringVar(value="-"); max_players_var = tk.StringVar(value="-")
    ip_label_var = tk.StringVar(value="Loading IP..."); error_message_var = tk.StringVar()
    # show_thumbnail is already initialized above

    load_placeholder_image()

    preview_label = tk.Label(root, borderwidth=0, highlightthickness=0, padx=0, pady=0, anchor=tk.CENTER)
    preview_label.grid(row=0, column=0, columnspan=2, pady=0, sticky="ew")
    root.grid_rowconfigure(0, weight=0)

    info_frame = tk.Frame(root, borderwidth=0, highlightthickness=0)
    info_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 5))
    info_labels_config = [("Server Name:", server_name_var), ("Map Name:", map_name_var), ("Players:", player_count_var), ("Max Players:", max_players_var), ("Server IP:", ip_label_var)]
    for i, (text, var) in enumerate(info_labels_config):
        tk.Label(info_frame, text=text, font=("Arial", 10)).grid(row=i, column=0, sticky="e", padx=(0,5))
        tk.Label(info_frame, textvariable=var, font=("Arial", 10), anchor="w").grid(row=i, column=1, sticky="w")

    separator = tk.Frame(root, height=2, bg="black"); separator.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 10))
    
    player_frame = tk.Frame(root); player_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=5, padx=10)
    
    button_frame = tk.Frame(root); button_frame.grid(row=4, column=0, columnspan=2, pady=(10, 10))
    tk.Button(button_frame, text="Connect", command=connect_to_server, width=10).pack(side="left", padx=20)
    tk.Button(button_frame, text="Options", command=open_options_window, width=10).pack(side="right", padx=20)

    root.bind("<Unmap>", on_minimize_to_tray); root.protocol("WM_DELETE_WINDOW", shutdown_application)
    try: os.makedirs(MAPSHOTS_DIR, exist_ok=True)
    except OSError as e: print(f"WARNING: Could not create Mapshots folder '{MAPSHOTS_DIR}': {e}")

    # Initial UI setup
    set_placeholder_or_clear_preview()
    auto_adjust_window_geometry() # Initial geometry adjustment based on content

    # Handle start_minimized_on_next_launch
    if start_minimized_on_next_launch_var.get():
        # Important: Withdraw *after* initial geometry calculation and UI setup,
        # otherwise winfo_reqheight might not be accurate.
        # However, to truly start "hidden", withdraw needs to be early.
        # Let's try withdrawing, then deiconify briefly for geometry, then withdraw again.
        # This is a bit of a hack. A better way might be to calculate geometry without showing.
        # For now, if starting minimized, we might accept a default initial size before first show.
        print("INFO: Starting minimized to tray.")
        root.withdraw() 
    else:
        # If not starting minimized, ensure it's visible (it should be by default)
        pass


    root.after(500, fetch_server_info) # First fetch will also call auto_adjust_window_geometry
    
    tray_thread = threading.Thread(target=setup_tray_icon, daemon=True); tray_thread.start()
    try: root.mainloop()
    except KeyboardInterrupt: print("INFO: Application terminated by user.")
    finally: shutdown_application()