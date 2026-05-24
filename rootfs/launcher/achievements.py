#!/usr/bin/env python3
# rootfs/launcher/achievements.py -- MintKit achievement engine
import json, os, time
from pathlib import Path

DATA_DIR  = Path(os.environ.get("MINTKIT_DATA", Path.home() / ".mintkit"))
ACH_FILE  = DATA_DIR / "achievements.json"

# ── Master achievement definitions ──────────────────────────────────────────────
ACHIEVEMENTS = {
    # ─ Launcher / OS ─────────────────────────────────────────────────────
    "first_boot":       {"name": "Welcome to MintKit!",    "desc": "Boot the device for the first time.",         "icon": "🌱", "game": "os"},
    "app_installed":    {"name": "Getting Started",        "desc": "Install your first app from PocketMall.",      "icon": "📦", "game": "os"},
    "ten_apps":         {"name": "Collector",               "desc": "Install 10 apps.",                           "icon": "📚", "game": "os"},
    "wifi_connected":   {"name": "Online",                  "desc": "Connect to WiFi for the first time.",        "icon": "📡", "game": "os"},
    "ota_updated":      {"name": "Up to Date",              "desc": "Update MintKit via OTA.",                    "icon": "⬆️", "game": "os"},
    "mintshell_opened": {"name": "Hacker",                  "desc": "Open MintShell.",                           "icon": "🖥️", "game": "os"},
    "uptime_1h":        {"name": "Committed",               "desc": "Keep the device on for 1 hour.",             "icon": "⏱️", "game": "os"},

    # ─ Crystal Browser ──────────────────────────────────────────────
    "browser_first":    {"name": "World Wide Web",          "desc": "Browse a website in Crystal Browser.",       "icon": "🌐", "game": "crystal-browser"},
    "browser_bookmark": {"name": "Bookmarked",              "desc": "Visit all 4 default bookmarks.",             "icon": "🔖", "game": "crystal-browser"},
    "browser_wiki":     {"name": "Encyclopedia",           "desc": "Visit Wikipedia.",                          "icon": "📚", "game": "crystal-browser"},
    "browser_hn":       {"name": "Hacker News Reader",     "desc": "Visit Hacker News.",                        "icon": "🟠", "game": "crystal-browser"},

    # ─ Crypt Raid ──────────────────────────────────────────────────
    "crypt_first_kill": {"name": "First Blood",             "desc": "Defeat your first enemy.",                  "icon": "⚔️",  "game": "crypt-raid"},
    "crypt_floor5":     {"name": "Spelunker",               "desc": "Reach floor 5 of the crypt.",               "icon": "🗓️", "game": "crypt-raid"},
    "crypt_floor10":    {"name": "Deep Diver",              "desc": "Reach floor 10.",                           "icon": "🕳️", "game": "crypt-raid"},
    "crypt_boss":       {"name": "Crypt Cleared",           "desc": "Defeat the final boss.",                   "icon": "💀", "game": "crypt-raid"},
    "crypt_no_damage":  {"name": "Untouchable",             "desc": "Clear a floor without taking damage.",      "icon": "🛡️", "game": "crypt-raid"},
    "crypt_100_kills":  {"name": "Dungeon Cleaner",         "desc": "Defeat 100 enemies total.",                "icon": "🗡️", "game": "crypt-raid"},

    # ─ RetroCore ───────────────────────────────────────────────────
    "retro_first_rom":  {"name": "Retro Gamer",             "desc": "Load a ROM in RetroCore.",                  "icon": "🎮", "game": "retrocore"},
    "retro_1h":         {"name": "Nostalgia Trip",          "desc": "Play a ROM for 1 hour.",                   "icon": "⏰", "game": "retrocore"},

    # ─ ChipTune ───────────────────────────────────────────────────
    "chip_first_track": {"name": "DJ MintKit",              "desc": "Play a track in ChipTune Player.",          "icon": "🎵", "game": "chiptune"},
    "chip_full_album":  {"name": "Full Album",              "desc": "Listen to 10 tracks in one session.",       "icon": "💿", "game": "chiptune"},

    # ─ MintNotes ──────────────────────────────────────────────────
    "notes_first":      {"name": "Note Taker",              "desc": "Create your first note.",                  "icon": "📝", "game": "mintnotes"},
    "notes_10":         {"name": "Journaling",              "desc": "Create 10 notes.",                         "icon": "📓", "game": "mintnotes"},

    # ─ PocketDraw ─────────────────────────────────────────────────
    "draw_first":       {"name": "Pixel Artist",            "desc": "Save your first drawing.",                 "icon": "🎨", "game": "pocketdraw"},
    "draw_10":          {"name": "Gallery",                 "desc": "Save 10 drawings.",                        "icon": "🖼️", "game": "pocketdraw"},

    # ─ PixelCraft ─────────────────────────────────────────────────
    "pixelcraft_first_block": {"name": "First Block",       "desc": "Place your first block in PixelCraft.",     "icon": "🟩", "game": "pixelcraft"},
    "pixelcraft_builder":     {"name": "Master Builder",    "desc": "Place 100 blocks in PixelCraft.",           "icon": "🏗️", "game": "pixelcraft"},
    "pixelcraft_saved":       {"name": "World Keeper",      "desc": "Save your world in PixelCraft.",            "icon": "💾", "game": "pixelcraft"},

    # ─ MintShell ──────────────────────────────────────────────────
    "shell_100_cmds":   {"name": "Power User",              "desc": "Run 100 commands in MintShell.",            "icon": "⚡", "game": "mintshell"},
    "shell_sudo":       {"name": "Root Access",             "desc": "Run a sudo command in MintShell.",          "icon": "🔐", "game": "mintshell"},
}

# ── Internal helpers ──────────────────────────────────────────────────────────────
def _load() -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if ACH_FILE.exists():
        try:
            return json.loads(ACH_FILE.read_text())
        except Exception:
            pass
    return {}

def _save(data: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ACH_FILE.write_text(json.dumps(data, indent=2))

# ── Public API ─────────────────────────────────────────────────────────────────
def unlock(achievement_id: str) -> bool:
    """Unlock an achievement. Returns True if newly unlocked, False if already unlocked or unknown."""
    if achievement_id not in ACHIEVEMENTS:
        return False
    data = _load()
    if achievement_id in data:
        return False  # already unlocked
    data[achievement_id] = {"unlocked_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    _save(data)
    return True  # newly unlocked — caller can show a popup

def is_unlocked(achievement_id: str) -> bool:
    """Check if an achievement is already unlocked."""
    return achievement_id in _load()

def get_all() -> list:
    """Return list of all achievements with unlock status.
    Each item: {id, name, desc, icon, game, unlocked, unlocked_at}
    """
    data = _load()
    result = []
    for ach_id, meta in ACHIEVEMENTS.items():
        entry = dict(meta)
        entry["id"] = ach_id
        entry["unlocked"] = ach_id in data
        entry["unlocked_at"] = data[ach_id]["unlocked_at"] if ach_id in data else None
        result.append(entry)
    return result

def count() -> tuple:
    """Returns (unlocked_count, total_count)."""
    data = _load()
    return len(data), len(ACHIEVEMENTS)