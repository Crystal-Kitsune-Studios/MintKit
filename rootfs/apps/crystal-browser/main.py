#!/usr/bin/env python3
# rootfs/apps/crystal-browser/main.py  --  Crystal Browser v1.1
import os, sys, platform, urllib.request, html, re
from collections import deque
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
ACCENT = (61, 204, 112)
DIM    = (90, 150, 105)
WHITE  = (180, 240, 195)
BORDER = (29, 100,  55)
BAR    = ( 6,  13,   8)

BOOKMARKS = [
    ("PocketMint",    "pocketmint.crystal-kitsune-studios.com"),
    ("MintKit GitHub", "github.com/Crystal-Kitsune-Studios/MintKit"),
    ("Hacker News",   "news.ycombinator.com"),
    ("Wikipedia",     "en.m.wikipedia.org"),
]

def strip_html(raw):
    raw = re.sub(r'<style[^>]*>.*?</style>', '', raw, flags=re.DOTALL|re.IGNORECASE)
    raw = re.sub(r'<script[^>]*>.*?</script>', '', raw, flags=re.DOTALL|re.IGNORECASE)
    raw = re.sub(r'<br\s*/?>', '\n', raw, flags=re.IGNORECASE)
    raw = re.sub(r'<!(?:--.*?--|DOCTYPE[^>]*)>', '', raw, flags=re.DOTALL|re.IGNORECASE)
    # Block elements -> newlines (div is critical for Wikipedia/most sites)
    raw = re.sub(r'<(?:p|div|article|section|header|footer|nav|main|aside|td|th|tr)[^>]*>', '\n', raw, flags=re.IGNORECASE)
    raw = re.sub(r'</(?:p|div|article|section|header|footer|nav|main|aside|td|th|tr)>', '\n', raw, flags=re.IGNORECASE)
    # List items - simple open/close replacement avoids nested-tag bugs
    raw = re.sub(r'<li[^>]*>', '\n• ', raw, flags=re.IGNORECASE)
    raw = re.sub(r'</li>', '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'<BROKEN_PLACEHOLDER[^>]*>(.*?)</BROKEN_PLACEHOLDER>',
                 lambda m: '\n\u2022 ' + re.sub(r'<[^>]+>', '', m.group(1)).strip(),
                 raw, flags=re.DOTALL|re.IGNORECASE)
    raw = re.sub(r'<[^>]+>', '', raw)
    raw = html.unescape(raw)
    # Collapse whitespace within each line without losing newlines
    raw = '\n'.join(' '.join(ln.split()) for ln in raw.split('\n'))
    return re.sub(r'\n{3,}', '\n\n', raw).strip()

def fetch(url):
    if not url.startswith("http"): url = "https://" + url
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "CrystalBrowser/1.0 PocketMint",
            "Accept-Encoding": "identity",
        })
        with urllib.request.urlopen(req, timeout=8) as r:
            cs = r.headers.get_content_charset() or "utf-8"
            return r.url, strip_html(r.read().decode(cs, errors="replace")), None
    except Exception as e:
        return url, None, str(e)

def wrap(text, font, max_w):
    lines = []
    for para in text.split("\n"):
        if not para.strip(): lines.append(""); continue
        words = para.split(); line = ""
        for w in words:
            t = (line + " " + w).strip()
            if font.size(t)[0] <= max_w: line = t
            else:
                if line: lines.append(line)
                line = w
        if line: lines.append(line)
    return lines

class CrystalBrowser:
    CONTENT_Y = 78; LINE_H = 16
    def __init__(self, screen, fonts):
        self.screen = screen; self.fonts = fonts
        self.url = ""; self.scroll = 0
        self.history = deque(maxlen=20); self.fwd = []
        self.input_mode = False; self.input_text = ""
        self.status = "Ready"
        self.CONTENT_H = SCREEN_H - self.CONTENT_Y - 44
        self.VIS = self.CONTENT_H // self.LINE_H
        self.show_logo = True   # show splash until first navigation
        self.lines = ["",
            "Z / Enter = address bar",
            "← / →  = back / forward",
            "↑ / ↓  = scroll", "",
            "Bookmarks:"] + [f"  [{i+1}] {b[0]}" for i, b in enumerate(BOOKMARKS)]

    def navigate(self, url):
        self.show_logo = False
        if self.url: self.history.append((self.url, self.lines[:], self.scroll))
        self.fwd.clear(); self.url = url; self.status = f"Loading {url}..."
        self.lines = ["Loading..."]; self.scroll = 0
        actual, text, err = fetch(url); self.url = actual
        if err: self.lines = [f"Error: {err}"]; self.status = "Error"
        else:
            self.lines = wrap(text, self.fonts["xs"], SCREEN_W - 24)
            self.status = f"OK  {actual}"
            achievements.unlock("browser_first")
            if "wikipedia.org" in actual: achievements.unlock("browser_wiki")
            if "ycombinator.com" in actual: achievements.unlock("browser_hn")

    def handle(self, ev):
        if ev.type != pygame.KEYDOWN: return None, None
        if self.input_mode:
            if ev.key == pygame.K_RETURN:
                u = self.input_text.strip(); self.input_text = ""; self.input_mode = False
                if u.isdigit() and 1 <= int(u) <= len(BOOKMARKS): self.navigate(BOOKMARKS[int(u)-1][1])
                elif u: self.navigate(u)
            elif ev.key == pygame.K_ESCAPE: self.input_mode = False; self.input_text = ""
            elif ev.key == pygame.K_BACKSPACE: self.input_text = self.input_text[:-1]
            elif ev.unicode.isprintable(): self.input_text += ev.unicode
        else:
            if ev.key in (pygame.K_DOWN, pygame.K_s):
                self.scroll = min(self.scroll + 1, max(0, len(self.lines) - self.VIS))
            elif ev.key in (pygame.K_UP, pygame.K_w): self.scroll = max(0, self.scroll - 1)
            elif ev.key in (pygame.K_RETURN, pygame.K_z):
                self.input_mode = True; self.input_text = self.url
            elif ev.key in (pygame.K_LEFT, pygame.K_a):
                if self.history:
                    self.fwd.append((self.url, self.lines[:], self.scroll))
                    self.url, self.lines, self.scroll = self.history.pop()
            elif ev.key in (pygame.K_RIGHT, pygame.K_d):
                if self.fwd:
                    self.history.append((self.url, self.lines[:], self.scroll))
                    self.url, self.lines, self.scroll = self.fwd.pop()
            elif ev.key in (pygame.K_ESCAPE, pygame.K_x): return "back", None
        return None, None

    def draw(self):
        s = self.screen; s.fill(BG)
        pygame.draw.rect(s, BAR, (0, 0, SCREEN_W, 48))
        pygame.draw.line(s, BORDER, (0, 48), (SCREEN_W, 48), 1)
        # Logo in top-left (small, 2 lines compressed)
        s.blit(self.fonts["xs"].render("♦ CRYSTAL", True, ACCENT), (6, 8))
        s.blit(self.fonts["xs"].render("  BROWSER", True, DIM), (6, 22))
        ab_x, ab_w = 90, SCREEN_W - 180
        ab_col = ACCENT if self.input_mode else BORDER
        pygame.draw.rect(s, (5, 13, 8), (ab_x, 10, ab_w, 26))
        pygame.draw.rect(s, ab_col, (ab_x, 10, ab_w, 26), 1)
        disp = (self.input_text + "_") if self.input_mode else (self.url or "Enter URL or 1-4 for bookmark...")
        s.blit(self.fonts["sm"].render(disp[:60], True, WHITE if self.input_mode else DIM), (ab_x + 6, 16))
        pygame.draw.rect(s, (8, 20, 12), (0, 48, SCREEN_W, 28))
        pygame.draw.line(s, BORDER, (0, 76), (SCREEN_W, 76), 1)
        s.blit(self.fonts["xs"].render(self.status[:80], True, DIM), (8, 56))
        for i, line in enumerate(self.lines[self.scroll:self.scroll + self.VIS]):
            y = self.CONTENT_Y + i * self.LINE_H
            s.blit(self.fonts["xs"].render(line[:90], True, WHITE), (8, y))
        total = max(1, len(self.lines))
        bh = max(20, int(self.VIS / total * self.CONTENT_H))
        by = self.CONTENT_Y + int(self.scroll / total * self.CONTENT_H)
        pygame.draw.rect(s, BORDER, (SCREEN_W - 5, self.CONTENT_Y, 3, self.CONTENT_H))
        pygame.draw.rect(s, ACCENT, (SCREEN_W - 5, by, 3, bh))
        pygame.draw.line(s, BORDER, (0, SCREEN_H - 34), (SCREEN_W, SCREEN_H - 34), 1)
        hx = 6
        for key, act in [("Z", "URL"), ("←/→", "BACK/FWD"), ("↑↓", "SCROLL"), ("X", "EXIT")]:
            ki = self.fonts["xs"].render(key, True, (5, 10, 8)); kw = ki.get_width() + 8
            pygame.draw.rect(s, ACCENT, (hx, SCREEN_H - 26, kw, 18))
            s.blit(ki, (hx + 4, SCREEN_H - 24)); hx += kw + 4
            ai = self.fonts["xs"].render(act, True, DIM)
            s.blit(ai, (hx, SCREEN_H - 24)); hx += ai.get_width() + 16

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Crystal Browser")
    clock = pygame.time.Clock()
    fonts = {
        "big":   pygame.font.SysFont("Courier New", 36, bold=True),
        "title": pygame.font.SysFont("Courier New", 20, bold=True),
        "menu":  pygame.font.SysFont("Courier New", 19, bold=True),
        "sm":    pygame.font.SysFont("Courier New", 14),
        "xs":    pygame.font.SysFont("Courier New", 12),
    }
    app = CrystalBrowser(screen, fonts)
    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT: pygame.quit(); sys.exit()
            act, _ = app.handle(ev)
            if act == "back": pygame.quit(); sys.exit()
        app.draw()
        pygame.display.flip()
        clock.tick(FPS)

if __name__ == "__main__": main()