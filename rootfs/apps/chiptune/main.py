#!/usr/bin/env python3
# rootfs/apps/chiptune/main.py  --  ChipTune Player v1.0
import os, sys, platform, random
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
BG     = (10,  26,  16)
CARD   = (13,  32,  16)
CARD_SEL = (18, 45, 22)
ACCENT = (61, 204, 112)
DIM    = (90, 150, 105)
WHITE  = (180, 240, 195)
BORDER = (29, 100,  55)
BAR    = ( 6,  13,   8)

if IS_LINUX:
    MUSIC_DIR = Path("/home/mintkit/Music")
else:
    MUSIC_DIR = Path(__file__).parent / "music"

EXTS = {".mp3", ".ogg", ".wav", ".flac", ".xm", ".mod"}

def scan(): return sorted([p for p in MUSIC_DIR.iterdir() if p.suffix.lower() in EXTS]) if MUSIC_DIR.exists() else []

def blit_c(surf, img, y):
    surf.blit(img, (SCREEN_W // 2 - img.get_width() // 2, y))

def draw_hints(s, fonts, hints):
    pygame.draw.line(s, BORDER, (0, SCREEN_H - 34), (SCREEN_W, SCREEN_H - 34), 1)
    x = 6
    for key, act in hints:
        ki = fonts["xs"].render(key, True, (5, 10, 8)); kw = ki.get_width() + 8
        pygame.draw.rect(s, ACCENT, (x, SCREEN_H - 26, kw, 18))
        s.blit(ki, (x + 4, SCREEN_H - 24)); x += kw + 4
        ai = fonts["xs"].render(act, True, DIM)
        s.blit(ai, (x, SCREEN_H - 24)); x += ai.get_width() + 16

class ChipTune:
    def __init__(self, screen, fonts):
        self.screen = screen; self.fonts = fonts
        pygame.mixer.init()
        self.tracks = scan(); self.cur = 0
        self.playing = False; self.paused = False
        self.track_start = 0
        self.tracks_played = 0

    def play(self, idx=None):
        if idx is not None: self.cur = idx
        if not self.tracks: return
        try:
            pygame.mixer.music.load(str(self.tracks[self.cur]))
            pygame.mixer.music.play()
            self.playing = True; self.paused = False
            self.track_start = pygame.time.get_ticks()
            self.tracks_played += 1
            achievements.unlock("chip_first_track")
            if self.tracks_played >= 10: achievements.unlock("chip_full_album")
        except Exception: self.playing = False

    def stop(self):
        pygame.mixer.music.stop(); self.playing = False; self.paused = False

    def toggle_pause(self):
        if self.playing and not self.paused:
            pygame.mixer.music.pause(); self.paused = True
        elif self.paused:
            pygame.mixer.music.unpause(); self.paused = False

    def next_track(self):
        if not self.tracks: return
        self.cur = (self.cur + 1) % len(self.tracks); self.play()

    def prev_track(self):
        if not self.tracks: return
        self.cur = (self.cur - 1) % len(self.tracks); self.play()

    def handle(self, ev):
        if self.playing and not self.paused and not pygame.mixer.music.get_busy():
            self.next_track()
        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_UP, pygame.K_w):      self.cur = (self.cur - 1) % max(1, len(self.tracks))
            elif ev.key in (pygame.K_DOWN, pygame.K_s):  self.cur = (self.cur + 1) % max(1, len(self.tracks))
            elif ev.key in (pygame.K_RETURN, pygame.K_z, pygame.K_SPACE):
                if self.playing or self.paused: self.toggle_pause()
                else: self.play(self.cur)
            elif ev.key in (pygame.K_RIGHT, pygame.K_d): self.next_track()
            elif ev.key in (pygame.K_LEFT, pygame.K_a):  self.prev_track()
            elif ev.key == pygame.K_x:      self.stop()
            elif ev.key == pygame.K_ESCAPE: self.stop(); return "back", None
        return None, None

    def draw(self):
        s = self.screen; s.fill(BG)
        pygame.draw.rect(s, BAR, (0, 0, SCREEN_W, 30))
        blit_c(s, self.fonts["title"].render("CHIPTUNE PLAYER", True, ACCENT), 6)
        pygame.draw.line(s, BORDER, (0, 30), (SCREEN_W, 30), 1)

        if not self.tracks:
            blit_c(s, self.fonts["menu"].render("No music files found", True, DIM), SCREEN_H // 2 - 20)
            blit_c(s, self.fonts["sm"].render(f"Add .mp3/.ogg/.xm/.mod to: {MUSIC_DIR.name}/", True, DIM), SCREEN_H // 2 + 14)
            draw_hints(s, self.fonts, [("Esc", "EXIT")]); return

        # Now playing bar
        if self.playing or self.paused:
            t = self.tracks[self.cur]
            icon = "\u23f8" if self.paused else "\u25b6"
            pygame.draw.rect(s, CARD_SEL, (0, 32, SCREEN_W, 44))
            pygame.draw.line(s, BORDER, (0, 76), (SCREEN_W, 76), 1)
            blit_c(s, self.fonts["menu"].render(f"{icon}  {t.stem[:40]}", True, ACCENT), 38)
            elapsed = (pygame.time.get_ticks() - self.track_start) / 1000
            bar_w = int((elapsed % 120) / 120 * (SCREEN_W - 40))
            pygame.draw.rect(s, BORDER, (20, 72, SCREEN_W - 40, 3))
            pygame.draw.rect(s, ACCENT,  (20, 72, bar_w, 3))
            y_start = 80
        else:
            y_start = 34

        item_h = min(44, (SCREEN_H - y_start - 40) // max(len(self.tracks), 1))
        for i, t in enumerate(self.tracks):
            y = y_start + i * item_h
            if y + item_h > SCREEN_H - 40: break
            bg = CARD_SEL if i == self.cur else CARD
            pygame.draw.rect(s, bg, (4, y, SCREEN_W - 8, item_h - 2))
            if i == self.cur: pygame.draw.rect(s, ACCENT, (4, y, SCREEN_W - 8, item_h - 2), 1)
            icon = "\u25b6" if (i == self.cur and self.playing) else "\u266a"
            ic = self.fonts["sm"].render(icon, True, ACCENT if i == self.cur else DIM)
            s.blit(ic, (12, y + (item_h - ic.get_height()) // 2))
            ni = self.fonts["sm"].render(t.stem[:44], True, WHITE)
            s.blit(ni, (32, y + (item_h - ni.get_height()) // 2))
            ei = self.fonts["xs"].render(t.suffix[1:].upper(), True, DIM)
            s.blit(ei, (SCREEN_W - ei.get_width() - 8, y + (item_h - ei.get_height()) // 2))

        draw_hints(s, self.fonts, [("Z/Spc", "PLAY/PAUSE"), ("\u2190/\u2192", "PREV/NEXT"), ("X", "STOP"), ("Esc", "EXIT")])

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("ChipTune Player")
    clock = pygame.time.Clock()
    fonts = {
        "big":   pygame.font.SysFont("Courier New", 36, bold=True),
        "title": pygame.font.SysFont("Courier New", 20, bold=True),
        "menu":  pygame.font.SysFont("Courier New", 19, bold=True),
        "sm":    pygame.font.SysFont("Courier New", 13),
        "xs":    pygame.font.SysFont("Courier New", 12),
    }
    app = ChipTune(screen, fonts)
    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT: pygame.quit(); sys.exit()
            act, _ = app.handle(ev)
            if act == "back": pygame.quit(); sys.exit()
        app.draw()
        pygame.display.flip()
        clock.tick(FPS)

if __name__ == "__main__": main()