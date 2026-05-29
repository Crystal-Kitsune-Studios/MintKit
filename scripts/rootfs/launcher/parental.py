#!/usr/bin/env python3
# rootfs/launcher/parental.py -- Parental Controls (OS built-in)
import json, os, hashlib, time
from pathlib import Path
from . import themes as th
import pygame

DATA_DIR      = Path(os.environ.get("MINTKIT_DATA", Path.home() / ".mintkit"))
PARENTAL_FILE = DATA_DIR / "parental.json"
CONFIG_FILE   = DATA_DIR / "config.json"

SCREEN_W, SCREEN_H = 640, 480
FPS    = 60
PAD    = 14
HEADER = 36
FOOTER = 34


def _hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode()).hexdigest()

def load_parental() -> dict:
    if PARENTAL_FILE.exists():
        try: return json.loads(PARENTAL_FILE.read_text())
        except Exception: pass
    return {"locked_apps": [], "time_limit_mins": 0, "pin_hash": ""}

def save_parental(data: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PARENTAL_FILE.write_text(json.dumps(data, indent=2))

def is_locked(app_id: str) -> bool:
    return app_id in load_parental().get("locked_apps", [])

def check_time_limit() -> bool:
    """Returns True if daily limit is exceeded."""
    data = load_parental()
    limit = data.get("time_limit_mins", 0)
    if limit <= 0:
        return False
    today = time.strftime("%Y-%m-%d")
    played = data.get("play_minutes", {}).get(today, 0)
    return played >= limit

def record_session(minutes: float):
    data = load_parental()
    today = time.strftime("%Y-%m-%d")
    pm = data.setdefault("play_minutes", {})
    pm[today] = pm.get(today, 0) + minutes
    save_parental(data)


def prompt_pin(screen, clock) -> bool:
    """Show PIN entry overlay. Returns True if correct PIN entered."""
    font_lg = pygame.font.SysFont("monospace", 16, bold=True)
    font_sm = pygame.font.SysFont("monospace", 11)
    pygame.key.set_repeat(400, 60)

    data    = load_parental()
    entered = ""
    error   = False

    while True:
        clock.tick(FPS)
        p = th.get()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                elif event.key == pygame.K_BACKSPACE:
                    entered = entered[:-1]; error = False
                elif event.unicode and event.unicode.isdigit() and len(entered) < 4:
                    entered += event.unicode
                    if len(entered) == 4:
                        if _hash_pin(entered) == data.get("pin_hash", ""):
                            return True
                        else:
                            entered = ""; error = True

        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 180))
        screen.blit(ov, (0, 0))
        bx, by, bw, bh = 160, 140, 320, 160
        pygame.draw.rect(screen, p["card"], (bx, by, bw, bh), border_radius=8)
        pygame.draw.rect(screen, p["accent"] if not error else (220, 60, 60), (bx, by, bw, bh), 1, border_radius=8)
        title = font_lg.render("Enter PIN", True, p["accent"])
        screen.blit(title, (bx + bw // 2 - title.get_width() // 2, by + 16))
        dots  = font_lg.render("● " * len(entered) + "○ " * (4 - len(entered)), True,
                                (220, 60, 60) if error else p["white"])
        screen.blit(dots, (bx + bw // 2 - dots.get_width() // 2, by + 60))
        if error:
            err = font_sm.render("Incorrect PIN", True, (220, 60, 60))
            screen.blit(err, (bx + bw // 2 - err.get_width() // 2, by + 100))
        hint = font_sm.render("Esc cancel", True, p["dim"])
        screen.blit(hint, (bx + bw // 2 - hint.get_width() // 2, by + 128))
        pygame.display.flip()


def settings_ui(screen, clock):
    """Parental controls settings screen (called from System Settings)."""
    font_lg = pygame.font.SysFont("monospace", 15, bold=True)
    font_sm = pygame.font.SysFont("monospace", 11)
    pygame.key.set_repeat(400, 60)

    data     = load_parental()
    options  = [
        ("Set PIN",          "set_pin"),
        ("Time limit",       "time_limit"),
        ("Locked apps",      "locked_apps"),
    ]
    cur = 0

    running = True
    while running:
        clock.tick(FPS)
        p = th.get()
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_w): cur = max(0, cur - 1)
                elif event.key in (pygame.K_DOWN, pygame.K_s): cur = min(len(options) - 1, cur + 1)
                elif event.key in (pygame.K_ESCAPE, pygame.K_b): running = False

        screen.fill(p["bg"])
        pygame.draw.rect(screen, p["bar"], (0, 0, SCREEN_W, HEADER))
        screen.blit(font_lg.render("Parental Controls", True, p["accent"]), (PAD, 10))
        for i, (label, _) in enumerate(options):
            y   = HEADER + PAD + i * 52
            sel = (i == cur)
            bg  = tuple(min(255, c + 12) for c in p["card"]) if sel else p["card"]
            pygame.draw.rect(screen, bg, (PAD, y, SCREEN_W - PAD * 2, 44), border_radius=4)
            if sel:
                pygame.draw.rect(screen, p["accent"], (PAD, y, SCREEN_W - PAD * 2, 44), 1, border_radius=4)
            screen.blit(font_lg.render(label, True, p["white"]), (PAD + 12, y + 12))
        pygame.display.flip()

    pygame.key.set_repeat(400, 60)