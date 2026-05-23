#!/usr/bin/env python3
# rootfs/apps/pixelcraft/main.py  --  PixelCraft v1.0
import os, sys, platform, json, random
from pathlib import Path

IS_LINUX = platform.system() == "Linux"
if IS_LINUX:
    os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")
    os.environ.setdefault("SDL_AUDIODRIVER", "alsa")

import pygame

SCREEN_W, SCREEN_H = 640, 480
FPS    = 60
TILE   = 16
COLS   = SCREEN_W  // TILE
ROWS   = (SCREEN_H - 80) // TILE

BG     = (10,  26,  16)
ACCENT = (61, 204, 112)
DIM    = (90, 150, 105)
WHITE  = (180, 240, 195)
BORDER = (29, 100,  55)
BLACK  = (5,   10,   8)
BAR    = (6,   13,   8)

BLOCKS = [
    ("Air",      None,              False),
    ("Grass",    (34, 139,  34),    True),
    ("Dirt",     (101,  67,  33),   True),
    ("Stone",    (128, 128, 128),   True),
    ("Wood",     (139, 115,  85),   True),
    ("Leaves",   ( 34, 100,  34),   True),
    ("Sand",     (210, 180, 140),   True),
    ("Water",    ( 30,  80, 200),   False),
    ("Lava",     (220,  60,  10),   False),
    ("Glass",    (180, 220, 230),   True),
    ("Gold",     (220, 180,  30),   True),
    ("Brick",    (178,  34,  34),   True),
]

SAVE_DIR  = Path(os.environ.get("HOME", ".")) / ".mintkit"
SAVE_FILE = SAVE_DIR / "pixelcraft_world.json"

def make_world():
    world = [[0] * ROWS for _ in range(COLS)]
    sky_h = ROWS // 3
    for x in range(COLS):
        surface = sky_h + random.randint(-2, 2)
        for y in range(ROWS):
            if y < surface:       world[x][y] = 0
            elif y == surface:    world[x][y] = 1
            elif y < surface + 4: world[x][y] = 2
            else:                 world[x][y] = 3
        for _ in range(4):
            oy = random.randint(surface + 5, ROWS - 1)
            world[x][oy] = random.choice([10, 3, 3, 3])
    return world

def save_world(world):
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    SAVE_FILE.write_text(json.dumps(world))

def load_world():
    if SAVE_FILE.exists():
        try: return json.loads(SAVE_FILE.read_text())
        except Exception: pass
    return make_world()

class PixelCraft:
    def __init__(self, screen, fonts):
        self.screen = screen; self.fonts = fonts
        self.world  = load_world()
        self.cam_x  = COLS // 2 - SCREEN_W // TILE // 2
        self.cam_y  = 0
        self.cur_block = 1
        self.cursor_x  = COLS // 2
        self.cursor_y  = ROWS  // 3
        self.msg = ""; self.msg_t = 0

    def get(self, x, y):
        if 0 <= x < COLS and 0 <= y < ROWS: return self.world[x][y]
        return 3

    def set(self, x, y, b):
        if 0 <= x < COLS and 0 <= y < ROWS: self.world[x][y] = b

    def handle(self, ev):
        if self.msg_t > 0: self.msg_t -= 1
        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_UP, pygame.K_w):    self.cursor_y = max(0, self.cursor_y - 1)
            elif ev.key in (pygame.K_DOWN, pygame.K_s): self.cursor_y = min(ROWS-1, self.cursor_y+1)
            elif ev.key in (pygame.K_LEFT, pygame.K_a): self.cursor_x = max(0, self.cursor_x-1)
            elif ev.key in (pygame.K_RIGHT, pygame.K_d): self.cursor_x = min(COLS-1, self.cursor_x+1)
            elif ev.key in (pygame.K_z, pygame.K_RETURN, pygame.K_SPACE):
                self.set(self.cursor_x, self.cursor_y, self.cur_block)
            elif ev.key == pygame.K_x:
                self.set(self.cursor_x, self.cursor_y, 0)
            elif ev.key == pygame.K_q:
                self.cur_block = (self.cur_block - 1) % len(BLOCKS)
                if self.cur_block == 0: self.cur_block = len(BLOCKS) - 1
            elif ev.key == pygame.K_e:
                self.cur_block = (self.cur_block + 1) % len(BLOCKS)
                if self.cur_block == 0: self.cur_block = 1
            elif ev.key == pygame.K_F5:
                save_world(self.world)
                self.msg = "World saved!"; self.msg_t = FPS * 2
            elif ev.key == pygame.K_ESCAPE:
                save_world(self.world); return "back", None
            vx = SCREEN_W // TILE; vy = (SCREEN_H - 80) // TILE
            if self.cursor_x < self.cam_x + 4:        self.cam_x = max(0, self.cursor_x - 4)
            if self.cursor_x > self.cam_x + vx - 5:   self.cam_x = min(COLS-vx, self.cursor_x-vx+5)
            if self.cursor_y < self.cam_y + 3:         self.cam_y = max(0, self.cursor_y - 3)
            if self.cursor_y > self.cam_y + vy - 4:   self.cam_y = min(ROWS-vy, self.cursor_y-vy+4)
        return None, None

    def draw(self):
        s = self.screen; s.fill((8, 20, 30))
        for sx in range(SCREEN_W // TILE + 1):
            for sy in range((SCREEN_H - 80) // TILE + 1):
                wx = self.cam_x + sx; wy = self.cam_y + sy
                b  = self.get(wx, wy)
                px = sx * TILE; py = 40 + sy * TILE
                if b != 0:
                    pygame.draw.rect(s, BLOCKS[b][1], (px, py, TILE, TILE))
                    pygame.draw.rect(s, (0,0,0), (px, py, TILE, TILE), 1)
        cx = (self.cursor_x - self.cam_x) * TILE
        cy = 40 + (self.cursor_y - self.cam_y) * TILE
        pygame.draw.rect(s, ACCENT, (cx, cy, TILE, TILE), 2)
        pygame.draw.rect(s, BAR, (0, 0, SCREEN_W, 40))
        pygame.draw.line(s, BORDER, (0, 40), (SCREEN_W, 40), 1)
        s.blit(self.fonts["title"].render("PIXELCRAFT", True, ACCENT), (8, 8))
        pygame.draw.rect(s, BAR, (0, SCREEN_H-40, SCREEN_W, 40))
        pygame.draw.line(s, BORDER, (0, SCREEN_H-40), (SCREEN_W, SCREEN_H-40), 1)
        for i, (name, col, _) in enumerate(BLOCKS[1:], 1):
            bx = 8 + (i-1)*36; by = SCREEN_H - 32; sel = (i == self.cur_block)
            pygame.draw.rect(s, col, (bx, by, 20, 20))
            pygame.draw.rect(s, ACCENT if sel else BORDER, (bx, by, 20, 20), 2 if sel else 1)
            if sel: s.blit(self.fonts["xs"].render(name, True, ACCENT), (8, SCREEN_H-40))
        hints = [("Z","PLACE"),("X","BREAK"),("Q/E","BLOCK"),("F5","SAVE"),("Esc","EXIT")]
        hx = SCREEN_W - 8
        for key, act in reversed(hints):
            ai = self.fonts["xs"].render(act, True, DIM)
            ki = self.fonts["xs"].render(key, True, BLACK)
            kw = ki.get_width() + 6
            hx -= ai.get_width() + 4; s.blit(ai, (hx, SCREEN_H-26)); hx -= 4
            hx -= kw; pygame.draw.rect(s, ACCENT, (hx, SCREEN_H-28, kw, 16))
            s.blit(ki, (hx+3, SCREEN_H-26)); hx -= 6
        if self.msg_t > 0:
            mi = self.fonts["sm"].render(self.msg, True, ACCENT)
            s.blit(mi, (SCREEN_W//2 - mi.get_width()//2, 12))

def main():
    pygame.init(); screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("PixelCraft"); clock = pygame.time.Clock()
    fonts = {"big": pygame.font.SysFont("Courier New",36,bold=True),
             "title": pygame.font.SysFont("Courier New",20,bold=True),
             "menu": pygame.font.SysFont("Courier New",19,bold=True),
             "sm": pygame.font.SysFont("Courier New",13),
             "xs": pygame.font.SysFont("Courier New",11)}
    game = PixelCraft(screen, fonts)
    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT: pygame.quit(); sys.exit()
            act, _ = game.handle(ev)
            if act == "back": pygame.quit(); sys.exit()
        game.draw(); pygame.display.flip(); clock.tick(FPS)

if __name__ == "__main__": main()