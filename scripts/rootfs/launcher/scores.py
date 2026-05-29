#!/usr/bin/env python3
# rootfs/launcher/scores.py -- MintKit score / leaderboard engine
import json, time
from pathlib import Path

DATA_DIR   = Path(__file__).parent.parent.parent / ".mintkit"  # overridden by env
import os
DATA_DIR   = Path(os.environ.get("MINTKIT_DATA", Path.home() / ".mintkit"))
SCORES_FILE = DATA_DIR / "scores.json"

# ── Internal helpers ──────────────────────────────────────────────────────────────
def _load() -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if SCORES_FILE.exists():
        try: return json.loads(SCORES_FILE.read_text())
        except Exception: pass
    return {}

def _save(data: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SCORES_FILE.write_text(json.dumps(data, indent=2))

# ── Game metadata (display names & icons) ────────────────────────────────────────
GAME_META = {
    "crypt-raid":   {"name": "Crypt Raid",       "icon": "⚔️",  "unit": "gold"},
    "pixelcraft":   {"name": "PixelCraft",        "icon": "🟩", "unit": "blocks"},
    "retrocore":    {"name": "RetroCore",         "icon": "🎮", "unit": "pts"},
    "mintnotes":    {"name": "MintNotes",         "icon": "📝", "unit": "notes"},
    "pocketdraw":   {"name": "PocketDraw",        "icon": "🎨", "unit": "saves"},
    "chiptune":     {"name": "ChipTune Player",   "icon": "🎵", "unit": "tracks"},
    "mintshell":    {"name": "MintShell",         "icon": "⚡", "unit": "cmds"},
    "crystal-browser": {"name": "Crystal Browser", "icon": "🌐", "unit": "pages"},
}

# ── Public API ─────────────────────────────────────────────────────────────────
def report(game_id: str, score: int, label: str = "") -> bool:
    """Report a score for a game. Returns True if it's a new personal best."""
    data = _load()
    entry = data.get(game_id, {"best": 0, "best_at": None, "history": []})
    is_pb = score > entry.get("best", 0)
    if is_pb:
        entry["best"] = score
        entry["best_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        entry["best_label"] = label
    # Keep last 10 sessions
    history = entry.get("history", [])
    history.append({"score": score, "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "label": label})
    entry["history"] = history[-10:]
    data[game_id] = entry
    _save(data)
    return is_pb

def get_best(game_id: str) -> int:
    """Get the personal best score for a game."""
    return _load().get(game_id, {}).get("best", 0)

def get_all() -> list:
    """Return list of all game scores, sorted by game name.
    Each item: {game_id, name, icon, unit, best, best_at, best_label}
    """
    data = _load()
    result = []
    for gid, meta in GAME_META.items():
        entry = data.get(gid, {})
        result.append({
            "game_id":    gid,
            "name":       meta["name"],
            "icon":       meta["icon"],
            "unit":       meta["unit"],
            "best":       entry.get("best", 0),
            "best_at":    entry.get("best_at"),
            "best_label": entry.get("best_label", ""),
            "history":    entry.get("history", []),
        })
    result.sort(key=lambda x: (-x["best"], x["name"]))
    return result