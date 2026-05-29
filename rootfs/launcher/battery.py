#!/usr/bin/env python3
# rootfs/launcher/battery.py -- Battery reader (OS built-in)
from pathlib import Path

SYSFS_ROOTS = [
    Path("/sys/class/power_supply/BAT0"),
    Path("/sys/class/power_supply/BAT1"),
    Path("/sys/class/power_supply/battery"),
]


def _read(path: Path) -> str:
    try: return path.read_text().strip()
    except Exception: return ""


def get() -> dict | None:
    """
    Returns {"pct": int, "charging": bool} or None if no battery found.
    """
    for root in SYSFS_ROOTS:
        cap_file    = root / "capacity"
        status_file = root / "status"
        if cap_file.exists():
            try:
                pct      = int(_read(cap_file))
                status   = _read(status_file).lower()
                charging = status in ("charging", "full")
                return {"pct": pct, "charging": charging}
            except Exception:
                continue
    return None


def icon(info: dict | None) -> str:
    if info is None:
        return ""
    if info["charging"]:
        return "⚡"
    pct = info["pct"]
    if pct >= 75: return "🔋"
    if pct >= 50: return "🔋"
    if pct >= 20: return "🪫"
    return "🪫"


def color(info: dict | None, p: dict) -> tuple:
    """Return an RGB colour tuple appropriate for the battery level."""
    if info is None:
        return p["dim"]
    pct = info["pct"]
    if pct >= 50: return (60, 200, 90)    # green
    if pct >= 20: return (240, 180, 40)   # yellow
    return (220, 60, 60)                  # red


def draw_bar(surf, font, x: int, y: int) -> None:
    """Draw battery icon + % into surf at (x, y). Safe no-op if no battery."""
    import pygame
    from launcher import themes as _th
    info = get()
    if info is None:
        return
    p   = _th.get()
    col = color(info, p)
    img = font.render(f"{icon(info)} {info['pct']}%", True, col)
    surf.blit(img, (x, y))