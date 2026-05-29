#!/usr/bin/env python3
# rootfs/launcher/themes.py -- MintKit theme engine
import json, os
from pathlib import Path

DATA_DIR    = Path(os.environ.get("MINTKIT_DATA", Path.home() / ".mintkit"))
CONFIG_FILE = DATA_DIR / "config.json"

# ── Built-in themes ──────────────────────────────────────────────────────────
# Each theme defines the full palette used across all MintKit apps.
THEMES = {
    "mint": {
        "name":    "Mint (default)",
        "preview": (61, 204, 112),
        "bg":      (10,  26,  16),
        "card":    (13,  32,  20),
        "bar":     ( 6,  13,   8),
        "border":  (29, 100,  55),
        "accent":  (61, 204, 112),
        "dim":     (50, 130,  75),
        "white":   (180, 240, 195),
        "locked":  (50,  70,  55),
        "black":   ( 5,  10,   8),
    },
    "dusk": {
        "name":    "Dusk",
        "preview": (180, 100, 240),
        "bg":      (16,  10,  26),
        "card":    (22,  13,  36),
        "bar":     ( 8,   5,  14),
        "border":  (70,  30, 110),
        "accent":  (180, 100, 240),
        "dim":     (110,  60, 160),
        "white":   (220, 200, 245),
        "locked":  (55,  40,  75),
        "black":   ( 8,   4,  14),
    },
    "ember": {
        "name":    "Ember",
        "preview": (240, 100,  40),
        "bg":      (22,  10,   6),
        "card":    (32,  14,   8),
        "bar":     (12,   6,   3),
        "border":  (110,  40,  12),
        "accent":  (240, 100,  40),
        "dim":     (160,  70,  30),
        "white":   (245, 210, 190),
        "locked":  (70,  35,  18),
        "black":   (10,   4,   2),
    },
    "ice": {
        "name":    "Ice",
        "preview": (80, 180, 240),
        "bg":      ( 8,  18,  28),
        "card":    (12,  24,  36),
        "bar":     ( 4,  10,  16),
        "border":  (25,  70, 110),
        "accent":  (80, 180, 240),
        "dim":     (40, 110, 160),
        "white":   (190, 220, 245),
        "locked":  (30,  60,  90),
        "black":   ( 4,   8,  14),
    },
    "mono": {
        "name":    "Mono",
        "preview": (200, 200, 200),
        "bg":      ( 8,   8,   8),
        "card":    (16,  16,  16),
        "bar":     ( 4,   4,   4),
        "border":  (60,  60,  60),
        "accent":  (200, 200, 200),
        "dim":     (110, 110, 110),
        "white":   (230, 230, 230),
        "locked":  (50,  50,  50),
        "black":   ( 3,   3,   3),
    },
    "rose": {
        "name":    "Rose",
        "preview": (240,  80, 130),
        "bg":      (24,   8,  14),
        "card":    (34,  12,  20),
        "bar":     (12,   4,   8),
        "border":  (110,  25,  55),
        "accent":  (240,  80, 130),
        "dim":     (160,  50,  90),
        "white":   (245, 200, 215),
        "locked":  (70,  25,  45),
        "black":   (10,   3,   7),
    },
}

DEFAULT_THEME = "mint"
THEME_ORDER   = ["mint", "dusk", "ember", "ice", "mono", "rose"]

# ── Config helpers ───────────────────────────────────────────────────────────
def _load_config() -> dict:
    if CONFIG_FILE.exists():
        try: return json.loads(CONFIG_FILE.read_text())
        except Exception: pass
    return {}

def _save_config(cfg: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))

# ── Public API ───────────────────────────────────────────────────────────────
def get_active_id() -> str:
    """Return the active theme ID (falls back to default)."""
    return _load_config().get("theme", DEFAULT_THEME)

def get() -> dict:
    """Return the active theme palette dict."""
    tid = get_active_id()
    return THEMES.get(tid, THEMES[DEFAULT_THEME])

def set_theme(theme_id: str):
    """Persist the active theme ID."""
    if theme_id not in THEMES:
        raise ValueError(f"Unknown theme: {theme_id}")
    cfg = _load_config()
    cfg["theme"] = theme_id
    _save_config(cfg)

def list_themes() -> list:
    """Return ordered list of (id, theme_dict) tuples."""
    return [(tid, THEMES[tid]) for tid in THEME_ORDER]