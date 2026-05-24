#!/usr/bin/env python3
# rootfs/apps/retrocore/main.py  --  RetroCore v1.0
import os, sys, platform
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "launcher"))
import achievements

IS_LINUX = platform.system() == "Linux"
if IS_LINUX:
    os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")
    os.environ.setdefault("SDL_AUDIODRIVER", "alsa")

import pygame

SCREEN_W, SCREEN_H = 640, 480
FPS = 60
BG     = (10,  26,  16)
CARD   = (13,  32,  16)
CARD_SEL = (18, 45, 22)
ACCENT = (61, 204, 112)
DIM    = (90, 150, 105)
WHITE  = (180, 240, 195)
BORDER = (29, 100,  55)
BAR    = ( 6,  13,   8)

if IS_LINUX:
    ROMS_DIR = Path("/home/mintkit/roms")
else:
    ROMS_DIR = Path(__file__).parent / "roms"

EXT_MAP = {
    ".nes":  "NES",
    ".gb":   "GB",
    ".gbc":  "GBC",
    ".gba":  "GBA",
}

def scan_roms():
    if not ROMS_DIR.exists(): return []
    return sorted([p for p in ROMS_DIR.iterdir() if p.suffix.lower() in EXT_MAP])

def blit_c(surf, img, y):
    surf.blit(img, (SCREEN_W // 2 - img.get_width() // 2, y))

class RetroCore:
    def __init__(self, screen, fonts):
        self.screen = screen; self.fonts = fonts
        self.roms = scan_roms(); self.cur = 0
        self.msg = ""; self.msg_t = 0

    def launch_rom(self, path):
        # RetroCore delegates to system emulator backends.
        # On a real device this would exec into a libretro core.
        # For now, display a placeholder screen.
        self.msg = f"Loading {path.name}..."
        self.msg_t = FPS * 3
        achievements.unlock("retro_first_rom")

    def handle(self, ev):
        if self.msg_t > 0: self.msg_t -= 1
        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_UP, pygame.K_w):    self.cur = max(0, self.cur - 1)
            elif ev.key in (pygame.K_DOWN, pygame.K_s): self.cur = min(max(0, len(self.roms) - 1), self.cur + 1)
            elif ev.key in (pygame.K_RETURN, pygame.K_z, pygame.K_SPACE):
                if self.roms: self.launch_rom(self.roms[self.cur])
            elif ev.key == pygame.K_ESCAPE: return "back", None
        return None, None

    def draw(self):
        s = self.screen; s.fill(BG)
        pygame.draw.rect(s, BAR, (0, 0, SCREEN_W, 38))
        pygame.draw.line(s, BORDER, (0, 38), (SCREEN_W, 38), 1)
        blit_c(s, self.fonts["title"].render("RETROCORE", True, ACCENT), 10)

        if not self.roms:
            blit_c(s, self.fonts["menu"].render("No ROMs found", True, DIM), SCREEN_H // 2 - 30)
            blit_c(s, self.fonts["sm"].render(f"Add .nes .gb .gbc .gba to: {ROMS_DIR.name}/", True, DIM), SCREEN_H // 2)
            blit_c(s, self.fonts["sm"].render("or load from cartridge slot", True, DIM), SCREEN_H // 2 + 20)
        else:
            item_h = min(48, (SCREEN_H - 80) // max(len(self.roms), 1))
            for i, rom in enumerate(self.roms):
                y = 42 + i * item_h
                if y + item_h > SCREEN_H - 40: break
                bg = CARD_SEL if i == self.cur else CARD
                pygame.draw.rect(s, bg, (4, y, SCREEN_W - 8, item_h - 2))
                if i == self.cur: pygame.draw.rect(s, ACCENT, (4, y, SCREEN_W - 8, item_h - 2), 1)
                s.blit(self.fonts["menu"].render(rom.stem[:40], True, ACCENT if i == self.cur else WHITE), (16, y + 6))
                system = EXT_MAP.get(rom.suffix.lower(), "?")
                si = self.fonts["xs"].render(system, True, DIM)
                s.blit(si, (SCREEN_W - si.get_width() - 12, y + 8))

        if self.msg_t > 0:
            mi = self.fonts["sm"].render(self.msg, True, ACCENT)
            s.blit(mi, (SCREEN_W // 2 - mi.get_width() // 2, SCREEN_H - 50))

        pygame.draw.line(s, BORDER, (0, SCREEN_H - 34), (SCREEN_W, SCREEN_H - 34), 1)
        hx = 6
        for key, act in [("Z", "LAUNCH"), ("Esc", "EXIT")]:
            ki = self.fonts["xs"].render(key, True, (5,10,8)); kw = ki.get_width()+8
            pygame.draw.rect(s, ACCENT, (hx, SCREEN_H-26, kw, 18)); s.blit(ki, (hx+4, SCREEN_H-24)); hx += kw+4
            ai = self.fonts["xs"].render(act, True, DIM); s.blit(ai, (hx, SCREEN_H-24)); hx += ai.get_width()+16

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("RetroCore")
    clock = pygame.time.Clock()
    fonts = {
        "big":   pygame.font.SysFont("Courier New", 36, bold=True),
        "title": pygame.font.SysFont("Courier New", 20, bold=True),
        "menu":  pygame.font.SysFont("Courier New", 19, bold=True),
        "sm":    pygame.font.SysFont("Courier New", 13),
        "xs":    pygame.font.SysFont("Courier New", 12),
    }
    app = RetroCore(screen, fonts)
    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT: pygame.quit(); sys.exit()
            act, _ = app.handle(ev)
            if act == "back": pygame.quit(); sys.exit()
        app.draw()
        pygame.display.flip()
        clock.tick(FPS)

if __name__ == "__main__": main()