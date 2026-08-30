#!/usr/bin/env python3
# rootfs/launcher/splash.py -- Boot splash (OS built-in)
import os
from pathlib import Path
from . import themes as th
import pygame

SCREEN_W, SCREEN_H = 800, 480
DATA_DIR   = Path(os.environ.get("MINTKIT_DATA", Path.home() / ".mintkit"))
CUSTOM_IMG = DATA_DIR / "splash.png"
DEFAULT_MS = 2500   # how long to show splash (ms)

# Fonts are loaded once at module level so SysFont() is never called per-frame.
# On Pi Zero 2W, calling SysFont() inside the render loop caused the splash
# to appear frozen due to repeated font-cache lookups at 60 fps.
_fonts_cache: dict = {}

def _short_version(raw: str) -> str:
    """Turn 'MintKit 2.1.0 "Spearmint"' into 'v2.1.0 "Spearmint"'."""
    text = (raw or "").strip()
    if text.lower().startswith("mintkit"):
        text = text[len("mintkit"):].strip()
    if text and not text.startswith("v"):
        text = "v" + text
    return text


def _fallback_version() -> str:
    """Last resort: whatever the OTA updater last wrote. Never raises."""
    try:
        return _short_version((DATA_DIR / "version.txt").read_text().strip())
    except Exception:
        return ""


def _get_fonts() -> dict:
    """Return cached fonts, loading them once on first call."""
    if not _fonts_cache:
        _fonts_cache["xl"] = pygame.font.SysFont("monospace", 42, bold=True)
        _fonts_cache["sm"] = pygame.font.SysFont("monospace", 13)
    return _fonts_cache


def show(screen, clock, duration_ms: int = DEFAULT_MS, version: str = ""):
    """
    Show the boot splash for duration_ms milliseconds.
    Pressing any key or button skips it early.
    """
    p = th.get()
    SCREEN_W, SCREEN_H = screen.get_size()

    # Load fonts once before the render loop.
    fonts = _get_fonts()

    # Try custom image first
    img = None
    if CUSTOM_IMG.exists():
        try:
            raw = pygame.image.load(str(CUSTOM_IMG)).convert()
            img = pygame.transform.smoothscale(raw, (SCREEN_W, SCREEN_H))
        except Exception:
            img = None

    start    = pygame.time.get_ticks()
    fade_dur = 400   # ms to fade in

    while True:
        clock.tick(60)
        now     = pygame.time.get_ticks()
        elapsed = now - start

        for event in pygame.event.get():
            if event.type in (pygame.KEYDOWN, pygame.JOYBUTTONDOWN):
                return   # skip on input

        if elapsed >= duration_ms:
            return

        # Fade in
        alpha = int(255 * elapsed / fade_dur) if elapsed < fade_dur else 255

        screen.fill(p["bg"])

        if img:
            img.set_alpha(alpha)
            screen.blit(img, (0, 0))
        else:
            _draw_default(screen, p, alpha, fonts, version)

        pygame.display.flip()


def _draw_default(screen, p: dict, alpha: int, fonts: dict, version: str = ""):
    """
    Render the default MintKit splash.
    Fonts are passed in (loaded once by show()) to avoid per-frame SysFont() calls.
    """
    SCREEN_W, SCREEN_H = screen.get_size()

    overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)

    title = fonts["xl"].render("MintKit", True, p["accent"])
    sub   = fonts["sm"].render("PocketMint OS", True, p["dim"])
    ver   = fonts["sm"].render(_short_version(version) or _fallback_version(), True, p["dim"])

    overlay.blit(title, (SCREEN_W // 2 - title.get_width() // 2, 160))
    overlay.blit(sub,   (SCREEN_W // 2 - sub.get_width() // 2,   220))
    overlay.blit(ver,   (SCREEN_W // 2 - ver.get_width() // 2,   244))

    # Accent underline
    uw = title.get_width()
    ux = SCREEN_W // 2 - uw // 2
    pygame.draw.rect(overlay, p["accent"], (ux, 210, uw, 2))

    overlay.set_alpha(alpha)
    screen.blit(overlay, (0, 0))