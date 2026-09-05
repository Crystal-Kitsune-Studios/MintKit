#!/usr/bin/env python3
# rootfs/launcher/updater.py  --  MintKit OTA launcher updater
import os, sys, json, urllib.request, shutil, threading
from pathlib import Path

GITHUB_API      = "https://api.github.com/repos/Crystal-Kitsune-Studios/MintKit/releases/latest"
LAUNCHER_BASE   = "https://pocketmint.crystal-kitsune-studios.com/launcher"
LAUNCHER_DIR    = Path(__file__).parent
VERSION_FILE    = Path(os.environ.get("HOME", ".")) / ".mintkit" / "version.txt"
PENDING_FILE    = Path(os.environ.get("HOME", ".")) / ".mintkit" / "pending_update.json"

# Fallback list, used only when the server has no manifest.json yet.
LAUNCHER_FILES = ["mintos.py", "updater.py", "inputbridge.py", "screenshot.py", "parental.py", "settings.py", "themes.py", "battery.py", "splash.py", "sleep_timer.py", "screensaver.py", "mintcalc.py", "pisugar.py", "achievements.py", "desktop.py", "friends_ui.py", "mintshell.py", "overlay.py", "savestates.py", "scores.py", "sideload.py", "themes_ui.py", "mintfb.py", "sitecustomize.py", "mintsetup.py"]

# The manifest is what makes the file list server driven. Without it, adding a
# filename to LAUNCHER_FILES only takes effect one release late, because
# apply_update iterates the list held by the updater.py that is already running.
MANIFEST_URL = f"{LAUNCHER_BASE}/manifest.json"

# Large non-.py files served from LAUNCHER_BASE/assets/. Fetched only when
# missing, so adding one here costs nothing on devices that already have it.
LAUNCHER_ASSETS = ["setup.ogg"]
VERSION_URL  = f"{LAUNCHER_BASE}/version.txt"
APPS_BASE    = "https://pocketmint.crystal-kitsune-studios.com/apps"
APPS_DIR     = Path("/home/mintkit/games")


def get_local_version():
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text().strip()
    # Fall back: parse VERSION constant from mintos.py so a fresh install
    # doesn't report "0.0.0" and trigger a spurious update notification.
    try:
        import re
        src = (LAUNCHER_DIR / "mintos.py").read_text()
        m   = re.search(r'VERSION\s*=\s*["\']MintKit\s+([\d.]+)', src)
        if m:
            return m.group(1)
    except Exception:
        pass
    return "0.0.0"


def parse_version(v):
    try: return tuple(int(x) for x in v.strip().split("."))
    except Exception: return (0, 0, 0)


def fetch_server_version():
    """Read version.txt straight from the OTA server.

    deploy-launcher.sh writes this, so it is the truth. The GitHub release is a
    separate manual step that has drifted before.
    """
    try:
        req = urllib.request.Request(
            VERSION_URL,
            headers={"User-Agent": "MintKit/1.0", "Cache-Control": "no-cache"},
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            tag = r.read().decode("utf-8").strip()
        return {"version": tag, "body": "", "zip_url": ""} if tag else None
    except Exception:
        return None


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


def fetch_manifest():
    """Ask the server what to download.

    Falls back to the built-in list so a device pointed at a server with no
    manifest.json still updates exactly the way it always did.
    """
    try:
        req = urllib.request.Request(
            MANIFEST_URL,
            headers={"User-Agent": "MintKit/1.0", "Cache-Control": "no-cache"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            m = json.loads(r.read().decode("utf-8"))
        launcher = [str(x) for x in (m.get("launcher") or LAUNCHER_FILES)]
        apps     = [str(x) for x in (m.get("apps") or [])]
        return launcher, apps
    except Exception as e:
        print(f"[OTA] manifest unavailable, using built-in list: {e}")
        return list(LAUNCHER_FILES), []


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


def prune_backups(keep_names):
    """Drop .bak files for launcher files that are no longer part of the set."""
    removed = 0
    for bak in LAUNCHER_DIR.glob("*.bak"):
        if bak.name[:-4] not in keep_names:
            try:
                bak.unlink()
                removed += 1
            except Exception:
                pass
    if removed:
        print(f"[OTA] pruned {removed} orphaned .bak file(s)")


def apply_app_update(app_files):
    """Update /home/mintkit/games/<app>/main.py from the manifest.

    Never fatal. A broken app must not be able to block a launcher update.
    Returns the list of files that failed.
    """
    failed = []
    if not app_files or not APPS_DIR.exists():
        return failed
    for rel in app_files:
        dest = APPS_DIR / rel
        tmp  = Path(str(dest) + ".ota")
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"[OTA] cannot create {dest.parent}: {e}")
            failed.append(rel)
            continue
        if download_file(f"{APPS_BASE}/{rel}", tmp):
            try:
                shutil.move(str(tmp), str(dest))
            except Exception as e:
                print(f"[OTA] could not install {rel}: {e}")
                failed.append(rel)
        else:
            failed.append(rel)
    return failed


def fetch_missing_assets():
    """Fetch launcher assets that are absent locally.

    Assets are large and do not change between releases, so re-downloading
    them on every update would make each OTA look hung on a Pi Zero. A
    failure here must never fail an update: the music is cosmetic.
    """
    adir = LAUNCHER_DIR / "assets"
    for name in LAUNCHER_ASSETS:
        dest = adir / name
        if dest.exists() and dest.stat().st_size > 0:
            continue
        adir.mkdir(parents=True, exist_ok=True)
        tmp = adir / (name + ".incoming")
        try:
            req = urllib.request.Request(
                f"{LAUNCHER_BASE}/assets/{name}",
                headers={"User-Agent": "MintKit/1.0"},
            )
            with urllib.request.urlopen(req, timeout=30) as r, open(tmp, "wb") as fh:
                shutil.copyfileobj(r, fh, 65536)
            tmp.replace(dest)
            print(f"[OTA] fetched asset {name}")
        except Exception as e:
            print(f"[OTA] asset {name} unavailable: {e}")
            try:
                tmp.unlink()
            except OSError:
                pass

def apply_update(remote_info, on_done=None):
    version = remote_info.get("version", "?")
    launcher_files, app_files = fetch_manifest()

    tmp_dir = LAUNCHER_DIR / "_ota_tmp"
    shutil.rmtree(tmp_dir, ignore_errors=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    # Download everything before touching anything, and do not stop at the
    # first failure: we want the full list of what went wrong.
    failed = []
    for fname in launcher_files:
        dest = tmp_dir / fname
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not download_file(f"{LAUNCHER_BASE}/{fname}", dest):
            failed.append(fname)

    fetch_missing_assets()

    ok = not failed
    if ok:
        for fname in launcher_files:
            src = tmp_dir / fname
            dst = LAUNCHER_DIR / fname
            bak = LAUNCHER_DIR / f"{fname}.bak"
            try:
                new_bytes = src.read_bytes()
            except Exception as e:
                print(f"[OTA] staged file missing for {fname}: {e}")
                failed.append(fname)
                ok = False
                break
            if dst.exists():
                # Only keep a backup when the file actually changed. This is
                # what stops ~30 identical .bak files piling up every run.
                if dst.read_bytes() == new_bytes:
                    src.unlink()
                    continue
                shutil.copy2(dst, bak)
            shutil.move(str(src), str(dst))

    if ok:
        VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        VERSION_FILE.write_text(version)
        prune_backups(set(launcher_files))
        app_failed = apply_app_update(app_files)
        if app_failed:
            print(f"[OTA] {len(app_failed)} app file(s) failed: {', '.join(app_failed)}")
        print(f"[OTA] updated to {version} ({len(launcher_files)} launcher files checked)")
    else:
        print(f"[OTA] ABORTED at {version}, {len(failed)} file(s) failed: {', '.join(failed)}")

    shutil.rmtree(tmp_dir, ignore_errors=True)
    if on_done:
        on_done(ok, version, failed)


def check_for_update():
    """Compare local version to the newest available. Returns info dict or None."""
    remote = fetch_server_version() or fetch_remote_info()
    if not remote: return None
    local    = parse_version(get_local_version())
    remote_v = parse_version(remote.get("version", "0.0.0"))
    if remote_v > local:
        return remote
    # No update, so clear any stale pending file
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
        self.failed_files     = []
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
        # Fall back to a live check
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

    def _on_apply_done(self, success, version, failed=()):
        self.apply_result = (success, version)
        self.failed_files = list(failed)
        self.applying     = False

    def restart_launcher(self):
        launcher = str(LAUNCHER_DIR / "mintos.py")
        os.execv(sys.executable, [sys.executable, launcher])