# QLView – Quake Server Viewer

A Python desktop app to monitor a Quake Live server (added quake3 now). Shows live server info, the current map and player list, and connects with one click.

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
