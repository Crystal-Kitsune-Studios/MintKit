#!/usr/bin/env python3
# rootfs/apps/mintnotes/main.py  --  MintNotes v1.0
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
    NOTES_DIR = Path("/home/mintkit/.mintkit/notes")
else:
    NOTES_DIR = Path(__file__).parent / "notes"
NOTES_DIR.mkdir(parents=True, exist_ok=True)

def list_notes(): return sorted(NOTES_DIR.glob("*.txt"))
def load_note(p): return p.read_text(encoding="utf-8") if p.exists() else ""
def save_note(p, text): p.write_text(text, encoding="utf-8")

def blit_c(surf, img, y):
    surf.blit(img, (SCREEN_W // 2 - img.get_width() // 2, y))

class MintNotes:
    LINE_H = 16; PAD = 8; CONTENT_Y = 50

    def __init__(self, screen, fonts):
        self.screen = screen; self.fonts = fonts
        self.mode = "list"  # list | edit | new_name
        self.notes = list_notes(); self.cur = 0
        self.lines = [""]; self.cursor_line = 0; self.cursor_col = 0
        self.scroll = 0; self.cur_path = None
        self.new_name = ""; self.msg = ""; self.msg_t = 0
        self.CONTENT_H = SCREEN_H - self.CONTENT_Y - 44
        self.VIS = self.CONTENT_H // self.LINE_H

    def open_note(self, path):
        self.cur_path = path
        text = load_note(path)
        self.lines = text.split("\n") if text else [""]
        self.cursor_line = 0; self.cursor_col = 0; self.scroll = 0
        self.mode = "edit"

    def save_current(self):
        if self.cur_path:
            save_note(self.cur_path, "\n".join(self.lines))
            self.msg = "Saved"; self.msg_t = FPS * 2

    def handle(self, ev):
        if self.msg_t > 0: self.msg_t -= 1
        if ev.type != pygame.KEYDOWN: return None, None

        if self.mode == "list":
            if ev.key in (pygame.K_UP, pygame.K_w):    self.cur = max(0, self.cur - 1)
            elif ev.key in (pygame.K_DOWN, pygame.K_s): self.cur = min(len(self.notes), self.cur + 1)
            elif ev.key in (pygame.K_RETURN, pygame.K_z):
                if self.cur < len(self.notes): self.open_note(self.notes[self.cur])
                else: self.mode = "new_name"; self.new_name = ""
            elif ev.key == pygame.K_DELETE:
                if self.cur < len(self.notes):
                    self.notes[self.cur].unlink()
                    self.notes = list_notes(); self.cur = max(0, self.cur - 1)
            elif ev.key == pygame.K_ESCAPE: return "back", None

        elif self.mode == "new_name":
            if ev.key == pygame.K_RETURN:
                name = self.new_name.strip()
                if name:
                    if not name.endswith(".txt"): name += ".txt"
                    p = NOTES_DIR / name
                    p.touch()
                    self.notes = list_notes()
                    self.open_note(p)
                    achievements.unlock("notes_first")
                    if len(self.notes) >= 10: achievements.unlock("notes_10")
                else: self.mode = "list"
            elif ev.key == pygame.K_ESCAPE: self.mode = "list"
            elif ev.key == pygame.K_BACKSPACE: self.new_name = self.new_name[:-1]
            elif ev.unicode.isprintable(): self.new_name += ev.unicode

        elif self.mode == "edit":
            line = self.lines[self.cursor_line]
            if ev.key == pygame.K_ESCAPE:   self.save_current(); self.notes = list_notes(); self.mode = "list"
            elif ev.key == pygame.K_F5:     self.save_current()
            elif ev.key == pygame.K_RETURN:
                rest = line[self.cursor_col:]
                self.lines[self.cursor_line] = line[:self.cursor_col]
                self.cursor_line += 1; self.cursor_col = 0
                self.lines.insert(self.cursor_line, rest)
            elif ev.key == pygame.K_BACKSPACE:
                if self.cursor_col > 0:
                    self.lines[self.cursor_line] = line[:self.cursor_col-1] + line[self.cursor_col:]
                    self.cursor_col -= 1
                elif self.cursor_line > 0:
                    prev = self.lines[self.cursor_line - 1]
                    self.cursor_col = len(prev)
                    self.lines[self.cursor_line - 1] = prev + line
                    self.lines.pop(self.cursor_line); self.cursor_line -= 1
            elif ev.key == pygame.K_DELETE:
                if self.cursor_col < len(line):
                    self.lines[self.cursor_line] = line[:self.cursor_col] + line[self.cursor_col+1:]
                elif self.cursor_line < len(self.lines) - 1:
                    self.lines[self.cursor_line] += self.lines.pop(self.cursor_line + 1)
            elif ev.key == pygame.K_LEFT:  self.cursor_col = max(0, self.cursor_col - 1)
            elif ev.key == pygame.K_RIGHT: self.cursor_col = min(len(self.lines[self.cursor_line]), self.cursor_col + 1)
            elif ev.key == pygame.K_UP:
                if self.cursor_line > 0:
                    self.cursor_line -= 1
                    self.cursor_col = min(self.cursor_col, len(self.lines[self.cursor_line]))
            elif ev.key == pygame.K_DOWN:
                if self.cursor_line < len(self.lines) - 1:
                    self.cursor_line += 1
                    self.cursor_col = min(self.cursor_col, len(self.lines[self.cursor_line]))
            elif ev.unicode.isprintable():
                self.lines[self.cursor_line] = line[:self.cursor_col] + ev.unicode + line[self.cursor_col:]
                self.cursor_col += 1
            # Scroll to cursor
            if self.cursor_line < self.scroll: self.scroll = self.cursor_line
            if self.cursor_line >= self.scroll + self.VIS: self.scroll = self.cursor_line - self.VIS + 1
        return None, None

    def draw(self):
        s = self.screen; s.fill(BG)
        pygame.draw.rect(s, BAR, (0, 0, SCREEN_W, self.CONTENT_Y - 2))
        pygame.draw.line(s, BORDER, (0, self.CONTENT_Y - 2), (SCREEN_W, self.CONTENT_Y - 2), 1)

        if self.mode == "list":
            blit_c(s, self.fonts["title"].render("MINTNOTES", True, ACCENT), 14)
            items = [p.stem for p in self.notes] + ["[ + New Note ]"]
            for i, name in enumerate(items):
                y = self.CONTENT_Y + i * 28
                if y > SCREEN_H - 44: break
                bg = CARD_SEL if i == self.cur else CARD
                pygame.draw.rect(s, bg, (4, y, SCREEN_W - 8, 26))
                if i == self.cur: pygame.draw.rect(s, ACCENT, (4, y, SCREEN_W - 8, 26), 1)
                col = DIM if i == len(self.notes) else WHITE
                s.blit(self.fonts["menu"].render(name, True, col), (16, y + 4))
            pygame.draw.line(s, BORDER, (0, SCREEN_H-34), (SCREEN_W, SCREEN_H-34), 1)
            x = 6
            for key, act in [("Z", "OPEN"), ("Del", "DELETE"), ("Esc", "EXIT")]:
                ki = self.fonts["xs"].render(key, True, (5,10,8)); kw = ki.get_width()+8
                pygame.draw.rect(s, ACCENT, (x, SCREEN_H-26, kw, 18)); s.blit(ki, (x+4, SCREEN_H-24)); x += kw+4
                ai = self.fonts["xs"].render(act, True, DIM); s.blit(ai, (x, SCREEN_H-24)); x += ai.get_width()+16

        elif self.mode == "new_name":
            blit_c(s, self.fonts["title"].render("MINTNOTES", True, ACCENT), 14)
            ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            ov.fill((0,0,0,160)); s.blit(ov, (0,0))
            pygame.draw.rect(s, CARD, (80, 170, SCREEN_W-160, 100))
            pygame.draw.rect(s, ACCENT, (80, 170, SCREEN_W-160, 100), 1)
            blit_c(s, self.fonts["menu"].render("New Note", True, ACCENT), 182)
            s.blit(self.fonts["sm"].render("Filename:", True, DIM), (96, 210))
            s.blit(self.fonts["menu"].render(self.new_name + "_", True, WHITE), (96, 228))

        elif self.mode == "edit":
            title = self.cur_path.stem[:30] if self.cur_path else "untitled"
            s.blit(self.fonts["title"].render(title, True, ACCENT), (8, 14))
            hint = self.fonts["xs"].render("F5=Save  Esc=Save&Back", True, DIM)
            s.blit(hint, (SCREEN_W - hint.get_width() - 8, 18))
            for i, line in enumerate(self.lines[self.scroll:self.scroll + self.VIS]):
                li = self.scroll + i; y = self.CONTENT_Y + i * self.LINE_H
                color = WHITE
                s.blit(self.fonts["xs"].render(line[:78], True, color), (self.PAD, y))
                if li == self.cursor_line:
                    cx = self.PAD + self.fonts["xs"].size(line[:self.cursor_col])[0]
                    pygame.draw.rect(s, ACCENT, (cx, y, 2, self.LINE_H))
            if self.msg_t > 0:
                mi = self.fonts["xs"].render(self.msg, True, ACCENT)
                s.blit(mi, (SCREEN_W - mi.get_width() - 8, SCREEN_H - 30))

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("MintNotes")
    clock = pygame.time.Clock()
    fonts = {
        "big":   pygame.font.SysFont("Courier New", 36, bold=True),
        "title": pygame.font.SysFont("Courier New", 20, bold=True),
        "menu":  pygame.font.SysFont("Courier New", 19, bold=True),
        "sm":    pygame.font.SysFont("Courier New", 13),
        "xs":    pygame.font.SysFont("Courier New", 12),
    }
    app = MintNotes(screen, fonts)
    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT: pygame.quit(); sys.exit()
            act, _ = app.handle(ev)
            if act == "back": pygame.quit(); sys.exit()
        app.draw()
        pygame.display.flip()
        clock.tick(FPS)

if __name__ == "__main__": main()