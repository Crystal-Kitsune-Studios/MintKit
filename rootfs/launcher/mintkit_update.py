#!/usr/bin/env python3
# rootfs/launcher/mintkit_update.py -- GitHub release checker
# Called by mintkit-update.service (systemd timer). Writes pending_update.json
# when a newer release is available; the launcher OtaManager reads it on startup.
import os, sys, json, urllib.request, re
from pathlib import Path

GITHUB_API   = "https://api.github.com/repos/Crystal-Kitsune-Studios/MintKit/releases/latest"
HOME         = Path(os.environ.get("HOME", "/home/mintkit"))
VERSION_FILE = HOME / ".mintkit" / "version.txt"
PENDING_FILE = HOME / ".mintkit" / "pending_update.json"
LAUNCHER_DIR = Path(__file__).parent


def get_local_version() -> str:
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text().strip()
    try:
        src = (LAUNCHER_DIR / "mintos.py").read_text()
        m   = re.search(r'VERSION\s*=\s*"MintKit\s+([\d.]+)', src)
        if m:
            return m.group(1)
    except Exception:
        pass
    return "0.0.0"


def parse_version(v: str):
    v = v.lstrip("v")
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except Exception:
        return (0, 0, 0)


def fetch_latest() -> dict | None:
    try:
        req = urllib.request.Request(
            GITHUB_API,
            headers={
                "User-Agent": "MintKit/1.0",
                "Accept": "application/vnd.github+json",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        tag = data.get("tag_name", "").lstrip("v")
        if not tag:
            return None
        return {
            "version": tag,
            "tag": data.get("tag_name", ""),
            "body": data.get("body", ""),
            "zip_url": data.get("zipball_url", ""),
        }
    except Exception as e:
        print(f"[mintkit-update] GitHub fetch failed: {e}", file=sys.stderr)
        return None


def main():
    local   = get_local_version()
    release = fetch_latest()
    if not release:
        print("[mintkit-update] Could not reach GitHub.", file=sys.stderr)
        return
    remote = release["version"]
    if parse_version(remote) > parse_version(local):
        print(f"[mintkit-update] Update available: {local} -> {remote}")
        PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
        PENDING_FILE.write_text(json.dumps(release, indent=2))
    else:
        print(f"[mintkit-update] Up to date ({local}).")
        if PENDING_FILE.exists():
            PENDING_FILE.unlink()  # clear stale pending file


if __name__ == "__main__":
    main()