#!/usr/bin/env python3
# rootfs/launcher/desktop.py -- Desktop Mode (OS built-in)
import json, os, time
from pathlib import Path
from . import themes as th
import pygame

SCREEN_W, SCREEN_H = 640, 480
FPS      = 60
PAD      = 14
HEADER   = 36
FOOTER   = 34
TILE_W   = 100
TILE_H   = 90
TILE_COLS = 5

DATA_DIR  = Path(os.environ.get("MINTKIT_DATA", Path.home() / ".mintkit"))
PINS_FILE = DATA_DIR / "desktop_pins.json"

DEFAULT_PINS = [
    {"id": "crypt-raid",  "name": "Crypt Raid",  "icon": "⚔️"},
    {"id": "pixelcraft",  "name": "PixelCraft",   "icon": "🟩"},
    {"id": "retrocore",   "name": "RetroCore",    "icon": "🎮"},
    {"id": "pocketcast",  "name": "PocketCast",   "icon": "🎙️"},
    {"id": "mintdocs",    "name": "MintDocs",     "icon": "📖"},
    {"id": "mintcalc",    "name": "Calculator",   "icon": "🧮"},
]

def load_pins():
    if PINS_FILE.exists():
        try: return json.loads(PINS_FILE.read_text())
        except Exception: pass
    return DEFAULT_PINS


def run(screen, clock, launch_cb=None):
    """Desktop overlay. launch_cb(app_id) called when user selects an app."""
    font_lg = pygame.font.SysFont("monospace", 13, bold=True)
    font_sm = pygame.font.SysFont("monospace", 10)
    font_ic = pygame.font.SysFont("monospace", 26)
    pygame.key.set_repeat(400, 60)

    pins = load_pins()
    cur  = 0

    running = True
    while running:
        clock.tick(FPS)
        p = th.get()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RIGHT, pygame.K_d):
                    cur = (cur + 1) % len(pins)
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    cur = (cur - 1) % len(pins)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    cur = min(len(pins) - 1, cur + TILE_COLS)
                elif event.key in (pygame.K_UP, pygame.K_w):
                    cur = max(0, cur - TILE_COLS)
                elif event.key in (pygame.K_RETURN, pygame.K_z):
                    if launch_cb:
                        launch_cb(pins[cur]["id"])
                    running = False
                elif event.key in (pygame.K_ESCAPE, pygame.K_HOME):
                    running = False

        # Dim background
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 200))
        screen.blit(ov, (0, 0))

        # Header
        pygame.draw.rect(screen, p["bar"], (0, 0, SCREEN_W, HEADER))
        pygame.draw.line(screen, p["border"], (0, HEADER), (SCREEN_W, HEADER))
        screen.blit(font_lg.render("Desktop", True, p["accent"]), (PAD, 10))
        ct = font_lg.render(time.strftime("%H:%M"), True, p["dim"])
        screen.blit(ct, (SCREEN_W - ct.get_width() - PAD, 10))

        # Tiles
        for i, pin in enumerate(pins):
            x = PAD + (i % TILE_COLS) * (TILE_W + 8)
            y = HEADER + PAD + (i // TILE_COLS) * (TILE_H + 8)
            sel = (i == cur)
            bg = tuple(min(255, c + 20) for c in p["card"]) if sel else p["card"]
            pygame.draw.rect(screen, bg, (x, y, TILE_W, TILE_H), border_radius=6)
            if sel:
                pygame.draw.rect(screen, p["accent"], (x, y, TILE_W, TILE_H), 2, border_radius=6)
            ic = font_ic.render(pin["icon"], True, p["accent"])
            screen.blit(ic, (x + TILE_W // 2 - ic.get_width() // 2, y + 10))
            nm = font_sm.render(pin["name"][:10], True, p["white"] if sel else p["dim"])
            screen.blit(nm, (x + TILE_W // 2 - nm.get_width() // 2, y + TILE_H - 18))

        # Footer
        pygame.draw.line(screen, p["border"], (0, SCREEN_H - FOOTER), (SCREEN_W, SCREEN_H - FOOTER))
        hx = 6
        for key, act in [("↑↓←→", "MOVE"), ("Z", "LAUNCH"), ("Home", "BACK")]:
            ki = font_sm.render(key, True, p["black"]); kw = ki.get_width() + 8
            pygame.draw.rect(screen, p["accent"], (hx, SCREEN_H - 26, kw, 18))
            screen.blit(ki, (hx + 4, SCREEN_H - 24)); hx += kw + 4
            ai = font_sm.render(act, True, p["dim"])
            screen.blit(ai, (hx, SCREEN_H - 24)); hx += ai.get_width() + 12

        pygame.display.flip()

    pygame.key.set_repeat(400, 60)