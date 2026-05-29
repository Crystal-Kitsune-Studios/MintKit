#!/usr/bin/env python3
# rootfs/apps/pocketdraw/main.py  --  PocketDraw v1.0
import os, sys, platform, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "launcher"))
import achievements
from pathlib import Path

IS_LINUX = platform.system() == "Linux"
if IS_LINUX:
    os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")
    os.environ.setdefault("SDL_AUDIODRIVER", "alsa")

import pygame

SCREEN_W, SCREEN_H = 640, 480
FPS = 60
CANVAS_W, CANVAS_H = 32, 32
ZOOM = 12  # pixels per canvas pixel (32*12=384)
CANVAS_OX = (SCREEN_W - CANVAS_W * ZOOM) // 2
CANVAS_OY = 48

BG     = (10,  26,  16)
ACCENT = (61, 204, 112)
DIM    = (90, 150, 105)
WHITE  = (180, 240, 195)
BORDER = (29, 100,  55)
BAR    = ( 6,  13,   8)

PALETTE = [
    (0,   0,   0),   (255, 255, 255), (200,  50,  50), (50,  180,  50),
    (50,  80,  220), (220, 180,  40), (180,  50, 180), (50,  200, 200),
    (180, 100,  40), (120, 120, 120), (61,  204, 112), (10,   26,  16),
]
TRANSPARENT = (0, 0, 0, 0)

if IS_LINUX:
    SAVE_DIR = Path("/home/mintkit/.mintkit/pocketdraw")
else:
    SAVE_DIR = Path(__file__).parent / "saves"
SAVE_DIR.mkdir(parents=True, exist_ok=True)
SAVE_FILE = SAVE_DIR / "canvas.json"

def new_canvas(): return [[None] * CANVAS_H for _ in range(CANVAS_W)]

def save_canvas(canvas):
    data = [[(list(c) if c else None) for c in row] for row in canvas]
    SAVE_FILE.write_text(json.dumps(data))

def load_canvas():
    if SAVE_FILE.exists():
        try:
            data = json.loads(SAVE_FILE.read_text())
            return [[(tuple(c) if c else None) for c in row] for row in data]
        except Exception: pass
    return new_canvas()

class PocketDraw:
    def __init__(self, screen, fonts):
        self.screen = screen; self.fonts = fonts
        self.canvas = load_canvas()
        self.cx, self.cy = CANVAS_W // 2, CANVAS_H // 2  # cursor
        self.color_idx = 0; self.tool = "draw"  # draw | erase
        self.msg = ""; self.msg_t = 0

    def draw_pixel(self):
        self.canvas[self.cx][self.cy] = PALETTE[self.color_idx]

    def erase_pixel(self):
        self.canvas[self.cx][self.cy] = None

    def handle(self, ev):
        if self.msg_t > 0: self.msg_t -= 1
        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_UP, pygame.K_w):    self.cy = max(0, self.cy - 1)
            elif ev.key in (pygame.K_DOWN, pygame.K_s): self.cy = min(CANVAS_H - 1, self.cy + 1)
            elif ev.key in (pygame.K_LEFT, pygame.K_a): self.cx = max(0, self.cx - 1)
            elif ev.key in (pygame.K_RIGHT, pygame.K_d): self.cx = min(CANVAS_W - 1, self.cx + 1)
            elif ev.key in (pygame.K_z, pygame.K_RETURN, pygame.K_SPACE):
                if self.tool == "draw": self.draw_pixel()
                else: self.erase_pixel()
            elif ev.key == pygame.K_x: self.erase_pixel()
            elif ev.key == pygame.K_q:
                self.color_idx = (self.color_idx - 1) % len(PALETTE)
            elif ev.key == pygame.K_e:
                self.color_idx = (self.color_idx + 1) % len(PALETTE)
            elif ev.key == pygame.K_TAB:
                self.tool = "erase" if self.tool == "draw" else "draw"
            elif ev.key == pygame.K_F5:
                save_canvas(self.canvas); self.msg = "Saved!"; self.msg_t = FPS * 2
                achievements.unlock("draw_first")
            elif ev.key == pygame.K_F1:
                self.canvas = new_canvas(); self.msg = "Cleared"; self.msg_t = FPS * 2
            elif ev.key == pygame.K_ESCAPE:
                save_canvas(self.canvas); return "back", None
        return None, None

    def draw(self):
        s = self.screen; s.fill(BG)
        # Checkerboard for transparent
        for x in range(CANVAS_W):
            for y in range(CANVAS_H):
                px = CANVAS_OX + x * ZOOM; py = CANVAS_OY + y * ZOOM
                checker = (30, 30, 30) if (x + y) % 2 == 0 else (50, 50, 50)
                pygame.draw.rect(s, checker, (px, py, ZOOM, ZOOM))
                c = self.canvas[x][y]
                if c: pygame.draw.rect(s, c, (px, py, ZOOM, ZOOM))
        # Grid
        for x in range(CANVAS_W + 1):
            lx = CANVAS_OX + x * ZOOM
            pygame.draw.line(s, (20, 40, 25), (lx, CANVAS_OY), (lx, CANVAS_OY + CANVAS_H * ZOOM))
        for y in range(CANVAS_H + 1):
            ly = CANVAS_OY + y * ZOOM
            pygame.draw.line(s, (20, 40, 25), (CANVAS_OX, ly), (CANVAS_OX + CANVAS_W * ZOOM, ly))
        # Cursor
        cx = CANVAS_OX + self.cx * ZOOM; cy = CANVAS_OY + self.cy * ZOOM
        pygame.draw.rect(s, ACCENT, (cx, cy, ZOOM, ZOOM), 2)
        # Top bar
        pygame.draw.rect(s, BAR, (0, 0, SCREEN_W, 46))
        pygame.draw.line(s, BORDER, (0, 46), (SCREEN_W, 46), 1)
        s.blit(self.fonts["title"].render("POCKETDRAW", True, ACCENT), (8, 12))
        # Palette swatch
        for i, col in enumerate(PALETTE):
            px = SCREEN_W - len(PALETTE) * 18 + i * 18 - 8; py = 12
            pygame.draw.rect(s, col, (px, py, 16, 20))
            if i == self.color_idx: pygame.draw.rect(s, ACCENT, (px, py, 16, 20), 2)
        # Tool indicator
        tool_col = ACCENT if self.tool == "draw" else (200, 80, 80)
        s.blit(self.fonts["xs"].render(f"[{self.tool.upper()}]", True, tool_col), (8, 30))
        # Hints
        pygame.draw.line(s, BORDER, (0, SCREEN_H - 34), (SCREEN_W, SCREEN_H - 34), 1)
        hx = 6
        for key, act in [("Z", "DRAW"), ("X", "ERASE"), ("Q/E", "COLOR"), ("Tab", "TOOL"), ("F5", "SAVE"), ("F1", "CLEAR"), ("Esc", "EXIT")]:
            ki = self.fonts["xs"].render(key, True, (5,10,8)); kw = ki.get_width()+8
            pygame.draw.rect(s, ACCENT, (hx, SCREEN_H-26, kw, 18)); s.blit(ki, (hx+4, SCREEN_H-24)); hx += kw+4
            ai = self.fonts["xs"].render(act, True, DIM); s.blit(ai, (hx, SCREEN_H-24)); hx += ai.get_width()+16
        if self.msg_t > 0:
            mi = self.fonts["xs"].render(self.msg, True, ACCENT)
            s.blit(mi, (SCREEN_W - mi.get_width() - 8, SCREEN_H - 30))

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("PocketDraw")
    clock = pygame.time.Clock()
    fonts = {
        "big":   pygame.font.SysFont("Courier New", 36, bold=True),
        "title": pygame.font.SysFont("Courier New", 20, bold=True),
        "menu":  pygame.font.SysFont("Courier New", 19, bold=True),
        "sm":    pygame.font.SysFont("Courier New", 13),
        "xs":    pygame.font.SysFont("Courier New", 12),
    }
    app = PocketDraw(screen, fonts)
    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT: pygame.quit(); sys.exit()
            act, _ = app.handle(ev)
            if act == "back": pygame.quit(); sys.exit()
        app.draw()
        pygame.display.flip()
        clock.tick(FPS)

if __name__ == "__main__": main()