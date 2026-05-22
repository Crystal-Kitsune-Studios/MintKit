#!/usr/bin/env python3
# rootfs/launcher/mintos.py
# MintKit OS launcher — fullscreen pygame UI, no X11
import os, sys, subprocess, json, pygame
from pathlib import Path

GAMES_DIR  = Path("/home/mintkit/games")
SCREEN_W, SCREEN_H = 640, 480
FPS = 60

BG      = (18,  18,  28)
CARD    = (30,  30,  48)
ACCENT  = (130, 80, 220)
SEL     = (160, 100, 255)
WHITE   = (240, 240, 240)
GREY    = (120, 120, 140)

def load_games():
    games = []
    for p in sorted(GAMES_DIR.iterdir()):
        m = p / "game.json"
        if p.is_dir() and m.exists():
            info = json.loads(m.read_text())
            info["path"] = p
            games.append(info)
    return games

def launch(game):
    entry = game["path"] / game.get("entry", "main.py")
    subprocess.Popen([sys.executable, str(entry)])

def txt(surf, text, font, color, x, y, cx=False):
    img = font.render(text, True, color)
    r = img.get_rect()
    r.centerx, r.y = (x, y) if cx else (r.centerx, y)
    if not cx: r.x = x
    surf.blit(img, r)

class Home:
    def __init__(self, screen, fonts, games):
        self.screen, self.fonts, self.games = screen, fonts, games
        self.cur = 0; self.cols = 4
    def handle(self, ev):
        k = getattr(ev, "key", None)
        if ev.type == pygame.KEYDOWN:
            if k == pygame.K_RIGHT:  self.cur = min(self.cur+1, len(self.games)-1)
            elif k == pygame.K_LEFT: self.cur = max(self.cur-1, 0)
            elif k == pygame.K_DOWN: self.cur = min(self.cur+self.cols, len(self.games)-1)
            elif k == pygame.K_UP:   self.cur = max(self.cur-self.cols, 0)
            elif k in (pygame.K_RETURN, pygame.K_SPACE):
                if self.games: return "launch", self.games[self.cur]
        return None, None
    def draw(self):
        s = self.screen; s.fill(BG)
        txt(s, "MintKit", self.fonts["title"], ACCENT, SCREEN_W//2, 12, cx=True)
        CW, CH, M = 130, 100, 16
        sx = (SCREEN_W - (self.cols*(CW+M)-M)) // 2
        for i, g in enumerate(self.games):
            col, row = i%self.cols, i//self.cols
            x, y = sx+col*(CW+M), 60+row*(CH+M)
            pygame.draw.rect(s, SEL if i==self.cur else CARD, (x,y,CW,CH), border_radius=8)
            txt(s, g.get("name",g["path"].name)[:12], self.fonts["sm"], WHITE, x+CW//2, y+CH-22, cx=True)
        txt(s, "A: Launch   Esc: Settings", self.fonts["sm"], GREY, SCREEN_W//2, SCREEN_H-22, cx=True)

class Settings:
    OPTS = ["WiFi", "Brightness", "Volume", "About", "Shutdown", "Back"]
    def __init__(self, screen, fonts):
        self.screen, self.fonts = screen, fonts; self.cur = 0
    def handle(self, ev):
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_DOWN:  self.cur = (self.cur+1)%len(self.OPTS)
            elif ev.key == pygame.K_UP:  self.cur = (self.cur-1)%len(self.OPTS)
            elif ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.OPTS[self.cur] == "Shutdown": subprocess.run(["poweroff"])
                if self.OPTS[self.cur] == "Back": return "back", None
        return None, None
    def draw(self):
        s = self.screen; s.fill(BG)
        txt(s, "Settings", self.fonts["title"], ACCENT, SCREEN_W//2, 20, cx=True)
        for i, o in enumerate(self.OPTS):
            txt(s, o, self.fonts["menu"], SEL if i==self.cur else WHITE, SCREEN_W//2, 90+i*44, cx=True)

def main():
    os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")
    os.environ.setdefault("SDL_AUDIODRIVER", "alsa")
    pygame.init(); pygame.joystick.init()
    if pygame.joystick.get_count(): pygame.joystick.Joystick(0).init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    clock  = pygame.time.Clock()
    fonts  = {
        "title": pygame.font.SysFont("DejaVu Sans", 28, bold=True),
        "menu":  pygame.font.SysFont("DejaVu Sans", 22),
        "sm":    pygame.font.SysFont("DejaVu Sans", 13),
    }
    games  = load_games()
    home   = Home(screen, fonts, games)
    setts  = Settings(screen, fonts)
    active = home
    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT: pygame.quit(); sys.exit()
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                active = setts if active is home else home
            else:
                act, data = active.handle(ev)
                if act == "launch": launch(data)
                elif act == "back": active = home
        active.draw()
        pygame.display.flip()
        clock.tick(FPS)

if __name__ == "__main__": main()
