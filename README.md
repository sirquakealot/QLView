# QLView – Quake Server Viewer

A Python desktop application to monitor a Quake-engine game server (built for Quake Live). It displays live server information, the current map, the player list, and lets you connect to the server with one click.

## Features

* Displays server name, current map and player count (also shown in the window title and tray tooltip).
* Live ping measurement via a Quake `getchallenge` request on the game port (close to the real in-game ping).
* Shows a thumbnail image for the current map from the local `Mapshots` directory, with a placeholder if none is found.
* Player list split into active players (sorted by score) and spectators/bots (sorted by time on server), each with their time connected.
* Player names rendered with Quake color codes (`^0`–`^9`).
* "Connect" button and tray entry to join the server via Steam's `steam://connect/` protocol.
* Up to 6 server favorites with optional hotkeys; favorite 1 doubles as the main server that is displayed.
* 27 selectable color schemes with live preview.
* Switchable layout: player list on the right (side-by-side) or below the server info (stacked).
* Minimizes to the system tray with Show/Hide, Refresh, Connect and Exit controls.

## Project structure

The application is split into several modules (it used to be a single file):

* `main.py` – entry point; builds the window, tray icon and wires everything together.
* `ui.py` – the `UIManager`: window layout, options panel, player list and color schemes.
* `server.py` – the `ServerHandler`: server queries (via `a2s`) and ping measurement.
* `utils.py` – helpers for config/favorites loading and saving, address parsing, autostart.
* `config.py` – constants, default server, and the color scheme definitions.

## Requirements

* Python 3.x
* Python libraries (install via pip):
    * `a2s` (querying game servers — the PyPI package is `python-a2s`)
    * `Pillow` (image handling)
    * `pystray` (system tray icon)
    * `winshell` (Windows only, for the "start with system" shortcut)
    * `pywin32` (Windows only, dependency for `winshell` / system interactions)

```bash
pip install python-a2s Pillow pystray winshell pywin32
```

*Note: `tkinter` is used for the GUI and is normally included with standard Python installations.*

## How to run

1. Install the requirements above.
2. Place a `quake3.ico` file in the same directory as the scripts for the window and tray icon.
3. Run the entry point from a terminal:

```bash
python main.py
```

## Building an .EXE

```bash
pyinstaller --noconsole --icon="quake3.ico" --onedir --add-data="quake3.ico;." --add-data="Mapshots;Mapshots" --hidden-import="pystray._win32" main.py
```

## Configuration

The application creates and uses a `config.ini` file in the same directory for:

* Main server address and port
* Refresh interval
* Show favorite hotkeys
* Start minimized
* Start with system
* Player list position (right / bottom)
* Color scheme

Favorites are stored separately in `favorites.json` (entries 1–6, where 1 is the main server).

Settings are changed through the in-app "Options" window, which has two tabs: **General** (interval, the six server favorites, application settings) and **Appearance** (hotkeys, layout, color scheme).

The default server is `108.61.179.235:27962` with a refresh interval of `10` seconds.

Map images go in the `Mapshots` directory as `.png` or `.jpg` files named after the map (e.g. `cpm22.png`).

## Notes

* "Start with system" creates a shortcut in the OS-specific startup folder (Windows).
* `sys._MEIPASS` is used for path resolution when running as a bundled executable.

## Preview
![preview1](https://github.com/sirquakealot/QLView/releases/download/v1.6/preview1.jpg "QLView")

GL & HF
