#!/usr/bin/env python3
# rootfs/Launcher/updater.py  --  MintKit OTA launcher updater
import os, sys, json, urllib.request, hashlib, shutil, threading
from pathlib import Path

VERSION_URL     = "https://pocketmint.crystal-kitsune-studios.com/version.json"
LAUNCHER_BASE   = "https://pocketmint.crystal-kitsune-studios.com/launcher"
LAUNCHER_DIR    = Path(__file__).parent
VERSION_FILE    = Path(os.environ.get("HOME", ".")) / ".mintkit" / "version.txt"

# Files to check and update
LAUNCHER_FILES  = ["mintos.py", "updater.py"]

def get_local_version():
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text().strip()
    return "0.0.0"

def parse_version(v):
    try: return tuple(int(x) for x in v.strip().split("."))
    except Exception: return (0, 0, 0)

def fetch_remote_info():
    """Fetch version.json from server. Returns dict or None."""
    try:
        req = urllib.request.Request(
            VERSION_URL,
            headers={"User-Agent": "MintKit/1.0", "Cache-Control": "no-cache"}
        )
        with urllib.request.urlopen(req, timeout=6) as r:
            return json.loads(r.read())
    except Exception:
        return None

def download_file(url, dest):
    """Download url to dest path. Returns True on success."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MintKit/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read()
        dest.write_bytes(data)
        return True
    except Exception as e:
        print(f"[OTA] Download failed {url}: {e}")
        return False

def apply_update(remote_info, on_done=None):
    """
    Download updated launcher files and swap them in.
    Calls on_done(success: bool, version: str) when complete.
    """
    version = remote_info.get("version", "?")
    tmp_dir = LAUNCHER_DIR / "_ota_tmp"
    tmp_dir.mkdir(exist_ok=True)

    ok = True
    for fname in LAUNCHER_FILES:
        url  = f"{LAUNCHER_BASE}/{fname}"
        dest = tmp_dir / fname
        if not download_file(url, dest):
            ok = False; break

    if ok:
        # Swap files
        for fname in LAUNCHER_FILES:
            src  = tmp_dir / fname
            dst  = LAUNCHER_DIR / fname
            bak  = LAUNCHER_DIR / f"{fname}.bak"
            if dst.exists(): shutil.copy2(dst, bak)
            shutil.move(str(src), str(dst))
        # Write new local version
        VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        VERSION_FILE.write_text(version)

    # Cleanup
    shutil.rmtree(tmp_dir, ignore_errors=True)

    if on_done:
        on_done(ok, version)

def check_for_update():
    """
    Synchronous check. Returns remote_info dict if update available, else None.
    """
    remote = fetch_remote_info()
    if not remote: return None
    local  = parse_version(get_local_version())
    remote_v = parse_version(remote.get("version", "0.0.0"))
    if remote_v > local:
        return remote
    return None

class OtaManager:
    """
    Background OTA manager — call from launcher on boot.
    Non-blocking: runs check in a thread, sets .update_available when done.
    """
    def __init__(self):
        self.update_available = False
        self.remote_info      = None
        self.applying         = False
        self.apply_result     = None   # (success, version) after apply
        self._thread          = None

    def start_check(self):
        """Kick off background update check."""
        if self._thread and self._thread.is_alive(): return
        self._thread = threading.Thread(target=self._check_thread, daemon=True)
        self._thread.start()

    def _check_thread(self):
        info = check_for_update()
        if info:
            self.remote_info      = info
            self.update_available = True

    def start_apply(self):
        """Kick off background download + apply."""
        if self.applying: return
        self.applying = True
        t = threading.Thread(
            target=apply_update,
            args=(self.remote_info,),
            kwargs={"on_done": self._on_apply_done},
            daemon=True
        )
        t.start()

    def _on_apply_done(self, success, version):
        self.apply_result = (success, version)
        self.applying     = False

    def restart_launcher(self):
        """Replace current process with updated launcher."""
        launcher = str(LAUNCHER_DIR / "mintos.py")
        os.execv(sys.executable, [sys.executable, launcher])