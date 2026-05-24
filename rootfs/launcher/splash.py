#!/usr/bin/env python3
# rootfs/launcher/splash.py -- Boot splash (OS built-in)
import os, time
from pathlib import Path
from . import themes as th
import pygame

SCREEN_W, SCREEN_H = 640, 480
DATA_DIR    = Path(os.environ.get("MINTKIT_DATA", Path.home() / ".mintkit"))
CUSTOM_IMG  = DATA_DIR / "splash.png"
DEFAULT_MS  = 2500   # how long to show splash (ms)


def show(screen, clock, duration_ms: int = DEFAULT_MS):
    """
    Show the boot splash for duration_ms milliseconds.
    Pressing any key or button skips it early.
    """
    p = th.get()

    # Try custom image first
    img = None
    if CUSTOM_IMG.exists():
        try:
            raw = pygame.image.load(str(CUSTOM_IMG)).convert()
            img = pygame.transform.smoothscale(raw, (SCREEN_W, SCREEN_H))
        except Exception:
            img = None

    start    = pygame.time.get_ticks()
    alpha    = 0
    fade_in  = True
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
        if elapsed < fade_dur:
            alpha = int(255 * elapsed / fade_dur)
        else:
            alpha = 255

        screen.fill(p["bg"])

        if img:
            img.set_alpha(alpha)
            screen.blit(img, (0, 0))
        else:
            _draw_default(screen, p, alpha)

        pygame.display.flip()


def _draw_default(screen, p: dict, alpha: int):
    """Animated default MintKit splash."""
    font_xl = pygame.font.SysFont("monospace", 42, bold=True)
    font_sm = pygame.font.SysFont("monospace", 13)

    overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)

    title = font_xl.render("MintKit", True, p["accent"])
    sub   = font_sm.render("PocketMint OS", True, p["dim"])
    ver   = font_sm.render("v1.0", True, p["dim"])

    overlay.blit(title, (SCREEN_W // 2 - title.get_width() // 2, 160))
    overlay.blit(sub,   (SCREEN_W // 2 - sub.get_width() // 2,   220))
    overlay.blit(ver,   (SCREEN_W // 2 - ver.get_width() // 2,   244))

    # Accent underline
    uw = title.get_width()
    ux = SCREEN_W // 2 - uw // 2
    pygame.draw.rect(overlay, p["accent"], (ux, 210, uw, 2))

    overlay.set_alpha(alpha)
    screen.blit(overlay, (0, 0))