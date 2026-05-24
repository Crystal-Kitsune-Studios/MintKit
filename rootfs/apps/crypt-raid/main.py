#!/usr/bin/env python3
# rootfs/apps/crypt-raid/main.py  --  Crypt Raid v1.0
import os, sys, platform, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "launcher"))
import achievements

IS_LINUX = platform.system() == "Linux"
if IS_LINUX:
    os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")
    os.environ.setdefault("SDL_AUDIODRIVER", "alsa")

import pygame

SCREEN_W, SCREEN_H = 640, 480
FPS   = 60
TILE  = 20
COLS  = SCREEN_W // TILE
ROWS  = (SCREEN_H - 80) // TILE

BG     = (5,   10,   8)
ACCENT = (61, 204, 112)
DIM    = (60, 100,  70)
WHITE  = (180, 240, 195)
BORDER = (29, 100,  55)
BAR    = ( 6,  13,   8)
RED    = (200,  50,  50)
GOLD   = (220, 180,  40)

# Tile types
EMPTY = 0; WALL = 1; FLOOR = 2; STAIR = 3; CHEST = 4

def make_dungeon():
    grid = [[WALL] * ROWS for _ in range(COLS)]
    rooms = []
    for _ in range(8):
        w = random.randint(4, 9); h = random.randint(3, 7)
        x = random.randint(1, COLS - w - 1); y = random.randint(1, ROWS - h - 1)
        for rx in range(x, x + w):
            for ry in range(y, y + h):
                grid[rx][ry] = FLOOR
        rooms.append((x + w // 2, y + h // 2))
    for i in range(len(rooms) - 1):
        x1, y1 = rooms[i]; x2, y2 = rooms[i + 1]
        while x1 != x2:
            grid[x1][y1] = FLOOR; x1 += 1 if x2 > x1 else -1
        while y1 != y2:
            grid[x1][y1] = FLOOR; y1 += 1 if y2 > y1 else -1
    # Place stairs and chests
    if rooms:
        sx, sy = rooms[-1]; grid[sx][sy] = STAIR
        for _ in range(3):
            cx, cy = random.choice(rooms[:-1])
            grid[cx + random.randint(-1,1)][cy + random.randint(-1,1)] = CHEST
    return grid, rooms[0] if rooms else (1, 1)

class Enemy:
    def __init__(self, x, y, hp, symbol, color):
        self.x = x; self.y = y; self.hp = hp; self.max_hp = hp
        self.symbol = symbol; self.color = color; self.move_t = 0

class CryptRaid:
    def __init__(self, screen, fonts):
        self.screen = screen; self.fonts = fonts
        self.new_floor(1)
        self.total_kills = 0

    def new_floor(self, floor):
        self.floor = floor
        self.grid, start = make_dungeon()
        self.px, self.py = start
        self.hp = getattr(self, 'hp', 20); self.max_hp = 20
        self.gold = getattr(self, 'gold', 0)
        self.atk = 3 + floor; self.msg = f"Floor {floor}"; self.msg_t = FPS * 2
        if floor >= 5: achievements.unlock("crypt_floor5")
        if floor >= 10: achievements.unlock("crypt_floor10")
        self.enemies = []
        for _ in range(3 + floor):
            for _ in range(50):
                ex = random.randint(1, COLS - 2); ey = random.randint(1, ROWS - 2)
                if self.grid[ex][ey] == FLOOR and (ex, ey) != start:
                    hp = random.randint(3, 5 + floor)
                    sym = random.choice(["g", "s", "o", "d"])
                    col = random.choice([RED, (180,100,60), (100,80,200), DIM])
                    self.enemies.append(Enemy(ex, ey, hp, sym, col)); break

    def move_enemies(self):
        for e in self.enemies:
            e.move_t += 1
            if e.move_t < 30: continue
            e.move_t = 0
            dx = 0; dy = 0
            if abs(e.x - self.px) + abs(e.y - self.py) < 8:
                dx = (1 if self.px > e.x else -1) if e.x != self.px else 0
                dy = (1 if self.py > e.y else -1) if e.y != self.py else 0
            else:
                dx, dy = random.choice([(0,1),(0,-1),(1,0),(-1,0)])
            nx, ny = e.x + dx, e.y + dy
            if nx == self.px and ny == self.py:
                dmg = random.randint(1, 3)
                self.hp -= dmg; self.msg = f"-{dmg} HP!"; self.msg_t = FPS
            elif 0 <= nx < COLS and 0 <= ny < ROWS and self.grid[nx][ny] != WALL:
                e.x = nx; e.y = ny

    def handle(self, ev):
        if self.hp <= 0:
            if ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_RETURN, pygame.K_z): self.__init__(self.screen, self.fonts)
                elif ev.key == pygame.K_ESCAPE: return "back", None
            return None, None
        if self.msg_t > 0: self.msg_t -= 1
        if ev.type == pygame.KEYDOWN:
            dx = dy = 0
            if ev.key in (pygame.K_UP, pygame.K_w):    dy = -1
            elif ev.key in (pygame.K_DOWN, pygame.K_s): dy = 1
            elif ev.key in (pygame.K_LEFT, pygame.K_a): dx = -1
            elif ev.key in (pygame.K_RIGHT, pygame.K_d): dx = 1
            elif ev.key == pygame.K_ESCAPE: return "back", None
            if dx or dy:
                nx, ny = self.px + dx, self.py + dy
                hit = next((e for e in self.enemies if e.x == nx and e.y == ny), None)
                if hit:
                    dmg = random.randint(self.atk - 1, self.atk + 1)
                    hit.hp -= dmg; self.msg = f"Hit! -{dmg}"; self.msg_t = FPS
                    if hit.hp <= 0:
                        self.enemies.remove(hit)
                        self.gold += random.randint(1, 3)
                        self.msg = f"Defeated! +gold"; self.msg_t = FPS
                        self.total_kills += 1
                        achievements.unlock("crypt_first_kill")
                        if self.total_kills >= 100: achievements.unlock("crypt_100_kills")
                elif 0 <= nx < COLS and 0 <= ny < ROWS and self.grid[nx][ny] != WALL:
                    self.px, self.py = nx, ny
                    tile = self.grid[nx][ny]
                    if tile == CHEST:
                        g = random.randint(2, 8); self.gold += g
                        self.msg = f"Chest! +{g}g"; self.msg_t = FPS * 2
                        self.grid[nx][ny] = FLOOR
                        heal = random.randint(2, 5); self.hp = min(self.max_hp, self.hp + heal)
                    elif tile == STAIR:
                        self.new_floor(self.floor + 1); return None, None
                self.move_enemies()
        return None, None

    def draw(self):
        s = self.screen; s.fill(BG)
        cx = max(0, min(COLS - SCREEN_W // TILE, self.px - SCREEN_W // TILE // 2))
        cy = max(0, min(ROWS - (SCREEN_H - 80) // TILE, self.py - (SCREEN_H - 80) // TILE // 2))
        for x in range(SCREEN_W // TILE + 1):
            for y in range((SCREEN_H - 80) // TILE + 1):
                wx, wy = cx + x, cy + y
                if wx >= COLS or wy >= ROWS: continue
                t = self.grid[wx][wy]; px = x * TILE; py = 40 + y * TILE
                if t == WALL:  pygame.draw.rect(s, (20, 40, 25), (px, py, TILE, TILE))
                elif t == FLOOR: pygame.draw.rect(s, (8, 18, 10), (px, py, TILE, TILE))
                elif t == STAIR:
                    pygame.draw.rect(s, (8, 18, 10), (px, py, TILE, TILE))
                    sc = self.fonts["xs"].render(">", True, ACCENT)
                    s.blit(sc, (px + 5, py + 3))
                elif t == CHEST:
                    pygame.draw.rect(s, (8, 18, 10), (px, py, TILE, TILE))
                    cc = self.fonts["xs"].render("$", True, GOLD)
                    s.blit(cc, (px + 5, py + 3))
        for e in self.enemies:
            ex = (e.x - cx) * TILE; ey = 40 + (e.y - cy) * TILE
            if 0 <= ex < SCREEN_W and 40 <= ey < SCREEN_H - 40:
                ec = self.fonts["sm"].render(e.symbol, True, e.color)
                s.blit(ec, (ex + 4, ey + 2))
        ppx = (self.px - cx) * TILE; ppy = 40 + (self.py - cy) * TILE
        pc = self.fonts["sm"].render("@", True, ACCENT)
        s.blit(pc, (ppx + 4, ppy + 2))
        pygame.draw.rect(s, BAR, (0, 0, SCREEN_W, 38))
        pygame.draw.line(s, BORDER, (0, 38), (SCREEN_W, 38), 1)
        s.blit(self.fonts["sm"].render(f"Floor {self.floor}  HP:{self.hp}/{self.max_hp}  Gold:{self.gold}", True, ACCENT), (8, 10))
        if self.msg_t > 0:
            mi = self.fonts["sm"].render(self.msg, True, GOLD)
            s.blit(mi, (SCREEN_W - mi.get_width() - 8, 10))
        if self.hp <= 0:
            ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 180)); s.blit(ov, (0, 0))
            blit_c = lambda img, y: s.blit(img, (SCREEN_W // 2 - img.get_width() // 2, y))
            blit_c(self.fonts["big"].render("GAME OVER", True, RED), SCREEN_H // 2 - 40)
            blit_c(self.fonts["sm"].render(f"Floor {self.floor}  Gold {self.gold}", True, DIM), SCREEN_H // 2 + 10)
            blit_c(self.fonts["sm"].render("Z = Restart   Esc = Exit", True, DIM), SCREEN_H // 2 + 34)
            return
        pygame.draw.line(s, BORDER, (0, SCREEN_H - 34), (SCREEN_W, SCREEN_H - 34), 1)
        x = 6
        for key, act in [("WASD/\u2191\u2191\u2193\u2190\u2192", "MOVE/ATTACK"), ("Esc", "EXIT")]:
            ki = self.fonts["xs"].render(key, True, (5,10,8)); kw = ki.get_width() + 8
            pygame.draw.rect(s, ACCENT, (x, SCREEN_H-26, kw, 18)); s.blit(ki, (x+4, SCREEN_H-24)); x += kw+4
            ai = self.fonts["xs"].render(act, True, DIM); s.blit(ai, (x, SCREEN_H-24)); x += ai.get_width()+16

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Crypt Raid")
    clock = pygame.time.Clock()
    fonts = {
        "big":   pygame.font.SysFont("Courier New", 36, bold=True),
        "title": pygame.font.SysFont("Courier New", 20, bold=True),
        "menu":  pygame.font.SysFont("Courier New", 19, bold=True),
        "sm":    pygame.font.SysFont("Courier New", 13),
        "xs":    pygame.font.SysFont("Courier New", 12),
    }
    game = CryptRaid(screen, fonts)
    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT: pygame.quit(); sys.exit()
            act, _ = game.handle(ev)
            if act == "back": pygame.quit(); sys.exit()
        game.draw()
        pygame.display.flip()
        clock.tick(FPS)

if __name__ == "__main__": main()