# config.py

# --- Application Configuration ---
APP_NAME = "QLView"
CONFIG_FILE = "config.ini"
FAVORITES_FILE = "favorites.json"
MAPSHOTS_DIR = "Mapshots"
BOT_NAMES = ["PQL Twitch Vamp TV"]

# --- Default Server Settings ---
DEFAULT_SERVER_ADDRESS = ("108.61.179.235", 27962)
DEFAULT_REFRESH_INTERVAL = 10

# --- Connect Command ---
# Wird von main.py genutzt, um dem Server beizutreten (Steam-Protokoll).
CONNECT_COMMAND = "steam://connect/{ip}:{port}"

# --- QLStats ELO API ---
# Öffentlicher, CORS-freigegebener Endpunkt des qlstats-Feeders.
# /server/<ip>:<port>/players liefert die aktuell verbundenen Spieler inkl.
# steamid, name, team und rating. Das rating ist je nach Server-Factory
# automatisch das A- oder B-Rating: für Vampiric PQL CA ist es das B-Rating.
QLSTATS_API_BASE = "https://qlstats.net/api"
QLSTATS_TIMEOUT = 4.0
SHOW_ELO = True

# --- UI Layout Constants ---
MAX_SERVER_MAP_NAME_CHARS = 256
MAX_PLAYER_NAME_CHARS = 64

# --- Color Schemes ---
COLOR_SCHEMES = {
    "Dark1": {"bg": "#1a1a1a", "fg": "#ffffff", "button_bg": "#2d2d2d", "button_fg": "#ffffff", "info_bg": "#2a2a2a", "separator": "#00ff88", "error_bg": "#8B0000", "button_active": "#404040", "accent": "#00ff88", "secondary": "#ff6600"},
    "Dark2": {"bg": "#0d1117", "fg": "#c9d1d9", "button_bg": "#21262d", "button_fg": "#f0f6fc", "info_bg": "#161b22", "separator": "#30d158", "error_bg": "#da3633", "button_active": "#30363d", "accent": "#30d158", "secondary": "#58a6ff"},
    "Bright1": {"bg": "#fdf6e3", "fg": "#586e75", "button_bg": "#eee8d5", "button_fg": "#073642", "info_bg": "#eee8d5", "separator": "#2aa198", "error_bg": "#dc322f", "button_active": "#e8e1ce", "accent": "#268bd2", "secondary": "#b58900"},
    "Bright2": {"bg": "#f0f2f5", "fg": "#1c1e21", "button_bg": "#e4e6eb", "button_fg": "#050505", "info_bg": "#ffffff", "separator": "#1877f2", "error_bg": "#fa383e", "button_active": "#d8dade", "accent": "#1877f2", "secondary": "#34a853"},
    "Cyber": {"bg": "#0a0a0a", "fg": "#00ff41", "button_bg": "#1a1a1a", "button_fg": "#00ff41", "info_bg": "#111111", "separator": "#ff0080", "error_bg": "#ff0040", "button_active": "#2a2a2a", "accent": "#ff0080", "secondary": "#00ffff"},
    "Ocean": {"bg": "#1a2332", "fg": "#a8c8ec", "button_bg": "#2a3441", "button_fg": "#ffffff", "info_bg": "#223040", "separator": "#4fc3f7", "error_bg": "#f44336", "button_active": "#3a4451", "accent": "#4fc3f7", "secondary": "#26c6da"},
    "Matrix": {"bg": "#000000", "fg": "#00ff00", "button_bg": "#0a0a0a", "button_fg": "#00ff00", "info_bg": "#050505", "separator": "#008f11", "error_bg": "#4d0000", "button_active": "#1f1f1f", "accent": "#00ff00", "secondary": "#008f11"},
    "Vampire": {"bg": "#1c1c1c", "fg": "#dcdcdc", "button_bg": "#4d0000", "button_fg": "#ffffff", "info_bg": "#2b2b2b", "separator": "#ff4500", "error_bg": "#8b0000", "button_active": "#8b0000", "accent": "#ff4500", "secondary": "#d2b48c"},
    "Forest": {"bg": "#2f4f4f", "fg": "#f5fffa", "button_bg": "#556b2f", "button_fg": "#ffffff", "info_bg": "#4a704a", "separator": "#9acd32", "error_bg": "#8b4513", "button_active": "#6b8e23", "accent": "#9acd32", "secondary": "#d2b48c"},
    "Arctic": {"bg": "#f0f8ff", "fg": "#4682b4", "button_bg": "#e6e6fa", "button_fg": "#000080", "info_bg": "#ffffff", "separator": "#add8e6", "error_bg": "#ffc0cb", "button_active": "#d8bfd8", "accent": "#4682b4", "secondary": "#87ceeb"},
    "Sunset": {"bg": "#4c0033", "fg": "#ffcc00", "button_bg": "#73004b", "button_fg": "#ffcc00", "info_bg": "#2e001f", "separator": "#e5007a", "error_bg": "#990024", "button_active": "#990063", "accent": "#e5007a", "secondary": "#ff9900"},
    "Mint": {"bg": "#e0f2f1", "fg": "#004d40", "button_bg": "#b2dfdb", "button_fg": "#004d40", "info_bg": "#ffffff", "separator": "#00897b", "error_bg": "#ef9a9a", "button_active": "#80cbc4", "accent": "#00897b", "secondary": "#004d40"},
    "Coffee": {"bg": "#ece0d1", "fg": "#3e2723", "button_bg": "#d7ccc8", "button_fg": "#3e2723", "info_bg": "#f5f5f5", "separator": "#8d6e63", "error_bg": "#bcaaa4", "button_active": "#bcaaa4", "accent": "#5d4037", "secondary": "#a1887f"},
    "Slate": {"bg": "#263238", "fg": "#eceff1", "button_bg": "#37474f", "button_fg": "#eceff1", "info_bg": "#37474f", "separator": "#009688", "error_bg": "#7f0000", "button_active": "#455a64", "accent": "#009688", "secondary": "#00695c"},
    "Mustard": {"bg": "#fffde7", "fg": "#424242", "button_bg": "#fff9c4", "button_fg": "#424242", "info_bg": "#ffffff", "separator": "#fdd835", "error_bg": "#e57373", "button_active": "#fff59d", "accent": "#afb42b", "secondary": "#fbc02d"},
    "Retro Gaming": {"bg": "#212121", "fg": "#e0e0e0", "button_bg": "#424242", "button_fg": "#ffffff", "info_bg": "#303030", "separator": "#ff4081", "error_bg": "#d32f2f", "button_active": "#616161", "accent": "#40c4ff", "secondary": "#76ff03"},
    "Lavender Dream": {"bg": "#f3e5f5", "fg": "#4a148c", "button_bg": "#e1bee7", "button_fg": "#4a148c", "info_bg": "#ffffff", "separator": "#ab47bc", "error_bg": "#f48fb1", "button_active": "#ce93d8", "accent": "#7b1fa2", "secondary": "#ba68c8"},
    "Graphite Gold": {"bg": "#373737", "fg": "#e8e8e8", "button_bg": "#484848", "button_fg": "#ffd700", "info_bg": "#2a2a2a", "separator": "#ffd700", "error_bg": "#b22222", "button_active": "#5a5a5a", "accent": "#ffd700", "secondary": "#c0c0c0"},
    "Deep Sea": {"bg": "#00334d", "fg": "#e0f7fa", "button_bg": "#004d66", "button_fg": "#ffffff", "info_bg": "#002233", "separator": "#4dd0e1", "error_bg": "#e53935", "button_active": "#006080", "accent": "#4dd0e1", "secondary": "#80deea"},
    "Autumn Leaves": {"bg": "#5d4037", "fg": "#fff3e0", "button_bg": "#795548", "button_fg": "#ffffff", "info_bg": "#4e342e", "separator": "#ff7043", "error_bg": "#d84315", "button_active": "#8d6e63", "accent": "#ff8a65", "secondary": "#ffb74d"},
    "Ruby": {"bg": "#4c0000", "fg": "#ffcdd2", "button_bg": "#800000", "button_fg": "#ffffff", "info_bg": "#330000", "separator": "#e57373", "error_bg": "#b71c1c", "button_active": "#9a0000", "accent": "#ef5350", "secondary": "#ff8a80"},
    "Emerald": {"bg": "#004d40", "fg": "#e0f2f1", "button_bg": "#00695c", "button_fg": "#ffffff", "info_bg": "#00332c", "separator": "#4db6ac", "error_bg": "#2e7d32", "button_active": "#00796b", "accent": "#26a69a", "secondary": "#80cbc4"},
    "Sapphire": {"bg": "#0d47a1", "fg": "#e3f2fd", "button_bg": "#1565c0", "button_fg": "#ffffff", "info_bg": "#0a3880", "separator": "#42a5f5", "error_bg": "#c62828", "button_active": "#1976d2", "accent": "#2196f3", "secondary": "#64b5f6"},
    "Amethyst": {"bg": "#311b92", "fg": "#ede7f6", "button_bg": "#4527a0", "button_fg": "#ffffff", "info_bg": "#251470", "separator": "#9575cd", "error_bg": "#8e24aa", "button_active": "#512da8", "accent": "#7e57c2", "secondary": "#b39ddb"},
    "Solar Flare": {"bg": "#1a1a1a", "fg": "#ffeb3b", "button_bg": "#ff6f00", "button_fg": "#000000", "info_bg": "#2c2c2c", "separator": "#fdd835", "error_bg": "#bf360c", "button_active": "#ff8f00", "accent": "#ffc107", "secondary": "#ff6f00"},
    "Clean Slate": {"bg": "#ffffff", "fg": "#333333", "button_bg": "#e0e0e0", "button_fg": "#004d40", "info_bg": "#f0f0f0", "separator": "#004d40", "error_bg": "#d32f2f", "button_active": "#cccccc", "accent": "#004d40", "secondary": "#1976d2"},
    "Blaze": {"bg": "#111111", "fg": "#e0e0e0", "button_bg": "#333333", "button_fg": "#ff8800", "info_bg": "#222222", "separator": "#ff8800", "error_bg": "#b71c1c", "button_active": "#444444", "accent": "#ff8800", "secondary": "#ffd700"},
    "Soft Lilac": {"bg": "#f5f0ff", "fg": "#4a148c", "button_bg": "#e6e0ff", "button_fg": "#4a148c", "info_bg": "#ffffff", "separator": "#9c27b0", "error_bg": "#e91e63", "button_active": "#d4c4f0", "accent": "#7e57c2", "secondary": "#ff9800"}
}