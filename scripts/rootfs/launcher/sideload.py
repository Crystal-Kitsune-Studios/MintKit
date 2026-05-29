#!/usr/bin/env python3
# rootfs/launcher/sideload.py -- USB sideload daemon
import os, json, shutil, zipfile, time
from pathlib import Path

SIDELOAD_DIR = Path("/home/mintkit/sideload")
APPS_DIR     = Path("/home/mintkit/games")
SIDELOAD_DIR.mkdir(parents=True, exist_ok=True)

REQUIRED_KEYS = {"id", "name", "developer", "entry"}

def install_zip(zip_path: Path) -> tuple[bool, str]:
    """Extract and validate a sideloaded app zip. Returns (ok, message)."""
    try:
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            if "game.json" not in names:
                return False, "Missing game.json"
            meta = json.loads(zf.read("game.json"))
            missing = REQUIRED_KEYS - meta.keys()
            if missing:
                return False, f"game.json missing keys: {missing}"
            app_id  = meta["id"]
            dest    = APPS_DIR / app_id
            if dest.exists():
                shutil.rmtree(dest)
            zf.extractall(dest)
        zip_path.unlink()
        return True, f"Installed {meta['name']} ({app_id})"
    except Exception as e:
        return False, str(e)

def watch():
    """Polling loop — call from a background thread in mintos.py."""
    while True:
        for f in SIDELOAD_DIR.glob("*.zip"):
            ok, msg = install_zip(f)
            print(f"[sideload] {msg}")
        time.sleep(3)