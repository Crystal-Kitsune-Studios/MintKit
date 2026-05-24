#!/usr/bin/env python3
# rootfs/launcher/savestates.py -- Save-state manager
import json, shutil, datetime
from pathlib import Path

STATE_DIR = Path("/home/mintkit/.mintkit/savestates")
MAX_SLOTS = 4

def _slot_path(game_id: str, slot: int) -> Path:
    d = STATE_DIR / game_id
    d.mkdir(parents=True, exist_ok=True)
    return d / f"slot{slot}.sav"

def _meta_path(game_id: str) -> Path:
    return STATE_DIR / game_id / "meta.json"

def save(game_id: str, slot: int, state_bytes: bytes) -> Path:
    """Write raw state bytes to a slot."""
    path = _slot_path(game_id, slot)
    path.write_bytes(state_bytes)
    # Update metadata
    meta = load_meta(game_id)
    meta[str(slot)] = {"saved_at": datetime.datetime.now().isoformat()}
    _meta_path(game_id).write_text(json.dumps(meta))
    return path

def load(game_id: str, slot: int) -> bytes | None:
    """Read raw state bytes from a slot, or None if empty."""
    path = _slot_path(game_id, slot)
    return path.read_bytes() if path.exists() else None

def load_meta(game_id: str) -> dict:
    mp = _meta_path(game_id)
    return json.loads(mp.read_text()) if mp.exists() else {}

def delete(game_id: str, slot: int):
    _slot_path(game_id, slot).unlink(missing_ok=True)
    meta = load_meta(game_id)
    meta.pop(str(slot), None)
    _meta_path(game_id).write_text(json.dumps(meta))

def list_slots(game_id: str) -> list[dict]:
    """Return info for all 4 slots (empty slots have saved_at=None)."""
    meta = load_meta(game_id)
    return [
        {"slot": i, "saved_at": meta.get(str(i), {}).get("saved_at")}
        for i in range(MAX_SLOTS)
    ]