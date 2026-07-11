# QLView – Quake Server Viewer

A Python desktop app to monitor a Quake Live server. Shows live server info, the current map and player list, and connects with one click.

## Features
- Server name, map and player count (also in window title & tray tooltip)
- Live ping via Quake `getchallenge` (close to real in-game ping)
- Map thumbnail from `Mapshots/`, placeholder if none found
- Player list: active players (by team red/blue, then score) and spectators/bots (by time), each with score, ELO and connect time
- ELO and team from qlstats (B-rating for CA), colored by strength; red/blue team square
- Match score red : blue in the header (hidden in FFA)
- Click a name → Steam profile
- Quake color codes (`^0`–`^9`)
- "Connect" via `steam://connect/`, also from the tray
- 7 favorites with optional hotkeys (favorite 1 = main server)
- 28 color schemes with live preview
- Switchable layout: player list on the right or below
- Minimizes to system tray (Show/Hide, Refresh, Connect, Exit)

## Structure
`main.py` (entry point, window + tray) · `ui.py` (`UIManager`) · `server.py` (`ServerHandler`, A2S + ping) · `utils.py` (config/favorites/autostart) · `config.py` (constants, color schemes)

## Install & run
```
pip install python-a2s Pillow pystray winshell pywin32
python main.py
```
`quake3.ico` must be in the script folder. `tkinter` ships with standard Python.

## Build .EXE
```
pyinstaller --noconsole --icon="quake3.ico" --onedir --add-data="quake3.ico;." --add-data="Mapshots;Mapshots" --hidden-import="pystray._win32" main.py
```

## Configuration
`config.ini` (server, interval, layout, scheme …) and `favorites.json` (favorites 1–7) are created automatically; change them via the in-app "Options" (tabs General & Appearance). Default server `108.61.179.235:27962`, interval 10 s. Map images as `.png`/`.jpg` named after the map (e.g. `cpm22.png`).

## Preview
![preview1](https://github.com/sirquakealot/QLView/releases/download/v1.71/preview1.jpg "QLView")

GL & HF
