# Quake Server Viewer

A Python desktop application to monitor a Quake-engine game server. It displays server information, current map, player list, and provides an option to connect to the server.

## Features

* Displays server name, current map, and player count.
* Shows a thumbnail image for the current map (if available locally or downloaded).
* Lists connected players, their scores (if applicable, though the script shows duration), and time on the server.
* "Connect" button to join the server (uses Steam's `steam://connect/` protocol).
* "Options" panel to configure:
    * Server IP address and port.
    * Data refresh interval.
    * Show/hide map thumbnail.
    * Start minimized to tray on next launch.
    * Start with system (OS dependent).
    * Download custom map images.
* Minimizes to system tray with basic controls (Show/Quit).
* Player names can be displayed with Quake color codes.
* Mapshots are stored in a `Mapshots` directory. A placeholder is used if a map image is not found.

## Requirements

* Python 3.x
* The following Python libraries (install via pip):
    * `a2s` (for querying game servers)
    * `Pillow` (for image handling)
    * `pystray` (for the system tray icon)
    * `winshell` (on Windows, for "start with system" shortcut creation)
    * `pywin32` (on Windows, dependency for `winshell` or other system interactions)

    ```bash
    pip install a2s Pillow pystray winshell pywin32
    ```
    *Note: `tkinter` is used for the GUI and is typically included with standard Python installations.*

## How to Run

1.  Ensure all requirements are installed.
2.  Place a `quake3.ico` file (or your preferred icon) in the same directory as the script if you want a custom icon for the window and tray.
3.  Run the script from your terminal:
    ```bash
    python qlview.py
    ```
## .EXE

    pyinstaller --noconsole --icon="quake3.ico" --onedir --add-data="quake3.ico;." --add-data="Mapshots;Mapshots" --hidden-import="pystray._win32" quake_server_viewer.py
   
## Configuration

The application creates and uses a `config.ini` file in the same directory to store settings like:
* Server address and port
* Refresh interval
* Thumbnail visibility preference
* Start minimized option
* Start with system option

These settings can be changed via the "Options" menu in the application.

The default server is set to `108.61.179.235:27962` with a refresh interval of `10` seconds.

Map images are expected in the `Mapshots` directory. You can add your own `.png` or `.jpg` files named after the map (e.g., `cpm22.png`).

## Notes

* The "Start with system" feature creates a shortcut in the appropriate OS-specific startup folder.
* The application uses `sys._MEIPASS` for path resolution when running as a bundled executable.

preview: 

![preview1](https://github.com/realkraz0r/QLView/releases/download/1.3/preview.png "QLView")

![preview2](https://github.com/realkraz0r/QLView/releases/download/1.3/tray2.jpg "QLView")

GL & HF
