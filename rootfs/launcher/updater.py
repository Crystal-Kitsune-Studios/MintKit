#!/usr/bin/env python3
# rootfs/launcher/updater.py  --  MintKit OTA launcher updater
import os, sys, json, urllib.request, hashlib, shutil, threading
from pathlib import Path

GITHUB_API      = "https://api.github.com/repos/Crystal-Kitsune-Studios/MintKit/releases/latest"
LAUNCHER_BASE   = "https://pocketmint.crystal-kitsune-studios.com/launcher"
LAUNCHER_DIR    = Path(__file__).parent
VERSION_FILE    = Path(os.environ.get("HOME", ".")) / ".mintkit" / "version.txt"
PENDING_FILE    = Path(os.environ.get("HOME", ".")) / ".mintkit" / "pending_update.json"

LAUNCHER_FILES  = ["mintos.py", "updater.py", "inputbridge.py", "screenshot.py", "parental.py", "settings.py", "themes.py", "battery.py", "splash.py", "sleep_timer.py"]

def get_local_version():
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text().strip()
    # Fall back: parse VERSION constant from mintos.py so a fresh install
    # doesn't report "0.0.0" and trigger a spurious update notification.
    try:
        import re
        src = (LAUNCHER_DIR / "mintos.py").read_text()
        m   = re.search(r'VERSION\s*=\s*"MintKit\s+([\d.]+)', src)
        if m:
            return m.group(1)
    except Exception:
        pass
    return "0.0.0"

def parse_version(v):
    try: return tuple(int(x) for x in v.strip().split("."))
    except Exception: return (0, 0, 0)

def fetch_remote_info():
    """Check GitHub releases API for latest version."""
    try:
        req = urllib.request.Request(
            GITHUB_API,
            headers={
                "User-Agent": "MintKit/1.0",
                "Accept": "application/vnd.github+json",
                "Cache-Control": "no-cache",
            }
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        tag  = data.get("tag_name", "").lstrip("v")
        body = data.get("body", "")
        zip_url = data.get("zipball_url", "")
        if not tag:
            return None
        return {"version": tag, "body": body, "zip_url": zip_url}
    except Exception:
        return None

def download_file(url, dest):
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
        for fname in LAUNCHER_FILES:
            src  = tmp_dir / fname
            dst  = LAUNCHER_DIR / fname
            bak  = LAUNCHER_DIR / f"{fname}.bak"
            if dst.exists(): shutil.copy2(dst, bak)
            shutil.move(str(src), str(dst))
        VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        VERSION_FILE.write_text(version)
    shutil.rmtree(tmp_dir, ignore_errors=True)
    if on_done:
        on_done(ok, version)

def check_for_update():
    """Compare local version to latest GitHub release. Returns remote info dict or None."""
    remote = fetch_remote_info()
    if not remote: return None
    local    = parse_version(get_local_version())
    remote_v = parse_version(remote.get("version", "0.0.0"))
    if remote_v > local:
        return remote
    # No update — clear any stale pending file
    if PENDING_FILE.exists():
        try: PENDING_FILE.unlink()
        except Exception: pass
    return None

class OtaManager:
    def __init__(self):
        self.update_available = False
        self.remote_info      = None
        self.applying         = False
        self.apply_result     = None
        self._thread          = None

    def start_check(self):
        if self._thread and self._thread.is_alive(): return
        self._thread = threading.Thread(target=self._check_thread, daemon=True)
        self._thread.start()

    def _check_thread(self):
        # First check pending_update.json written by the mintkit-update timer service
        if PENDING_FILE.exists():
            try:
                info = json.loads(PENDING_FILE.read_text())
                if parse_version(info.get("version", "0")) > parse_version(get_local_version()):
                    self.remote_info      = info
                    self.update_available = True
                    return
            except Exception:
                pass
        # Fall back to a live GitHub check
        info = check_for_update()
        if info:
            self.remote_info      = info
            self.update_available = True

    def start_apply(self):
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
        launcher = str(LAUNCHER_DIR / "mintos.py")
        os.execv(sys.executable, [sys.executable, launcher])