#!/usr/bin/env python3
# rootfs/launcher/mintos.py  --  MintKit OS launcher v2 (apps + wifi)
import os, sys, json, subprocess, platform, datetime, shutil
from pathlib import Path

IS_LINUX = platform.system() == "Linux"
if IS_LINUX:
    os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")
    os.environ.setdefault("SDL_AUDIODRIVER", "alsa")
else:
    os.environ.setdefault("SDL_VIDEODRIVER", "windows")
    os.environ.setdefault("SDL_AUDIODRIVER", "directsound")

import pygame

# --- Paths ---
if IS_LINUX:
    DATA_DIR  = Path("/home/mintkit/.mintkit")
    GAMES_DIR = Path("/home/mintkit/games")
    MEDIA_DIR = Path("/home/mintkit/Music")
else:
    DATA_DIR  = Path(__file__).parent / "data"
    GAMES_DIR = Path(__file__).parent / "games"
    MEDIA_DIR = Path(__file__).parent / "media"

for d in (DATA_DIR, GAMES_DIR, MEDIA_DIR):
    d.mkdir(parents=True, exist_ok=True)

FRIENDS_FILE = DATA_DIR / "friends.json"
CATALOG_FILE = DATA_DIR / "catalog.json"

VERSION   = "MintKit 1.0-alpha"
STORE_URL = "crystal-kitsune-studios.com"
SCREEN_W, SCREEN_H = 640, 480
FPS = 60

BG       = (10,  26,  16)
CARD     = (13,  32,  16)
CARD_SEL = (18,  45,  22)
BORDER   = (29, 100,  55)
ACCENT   = (61, 204, 112)
DIM      = (90, 150, 105)
WHITE    = (180, 240, 195)
BLACK    = (5,   10,   8)
RED      = (220,  60,  60)
GOLD     = (240, 200,  60)

BUILTIN_CATALOG = [
    {"id": "crystal-browser", "name": "Crystal Browser",  "developer": "CKS",        "category": "app",  "price": 0,    "desc": "Lightweight web browser for PocketMint.",   "icon": "\u{1F310}"},
    {"id": "crypt-raid",      "name": "Crypt Raid",        "developer": "CKS",        "category": "game", "price": 0,    "desc": "Roguelike dungeon crawler.",                "icon": "\u2694"},
    {"id": "pixelcraft",      "name": "PixelCraft",        "developer": "NeonByte",   "category": "game", "price": 2.99, "desc": "Pixel art building sandbox.",              "icon": "\u{1F3D7}"},
    {"id": "chiptune",        "name": "ChipTune Player",   "developer": "RetroAudio", "category": "media","price": 0,    "desc": "Play .xm/.mod tracker files.",             "icon": "\u{1F3B5}"},
    {"id": "retrocore",       "name": "RetroCore",         "developer": "OpenEmu CKS","category": "emu",  "price": 0,    "desc": "NES/GB/GBC/GBA emulator.",                "icon": "\u{1F3AE}"},
    {"id": "pocketdraw",      "name": "PocketDraw",        "developer": "SketchWare", "category": "app",  "price": 1.99, "desc": "Pixel art drawing app.",                  "icon": "\u{1F5BC}"},
    {"id": "mintnotes",       "name": "MintNotes",         "developer": "CKS",        "category": "app",  "price": 0,    "desc": "Simple note-taking app.",                "icon": "\u{1F4DD}"},
]

def load_catalog():
    if CATALOG_FILE.exists():
        try: return json.loads(CATALOG_FILE.read_text())
        except Exception: pass
    return BUILTIN_CATALOG

def load_friends():
    if FRIENDS_FILE.exists():
        try: return json.loads(FRIENDS_FILE.read_text())
        except Exception: pass
    return []

def save_friends(friends): FRIENDS_FILE.write_text(json.dumps(friends, indent=2))

def load_games():
    if not GAMES_DIR.exists(): return []
    games = []
    for p in sorted(GAMES_DIR.iterdir()):
        m = p / "game.json"
        if p.is_dir() and m.exists():
            try:
                info = json.loads(m.read_text()); info["path"] = p; games.append(info)
            except Exception: pass
    return games

def is_installed(app_id): return (GAMES_DIR / app_id).exists()

APP_SERVER = "https://pocketmint.crystal-kitsune-studios.com/apps"

def install_app(app):
    import urllib.request, zipfile, io
    dest = GAMES_DIR / app["id"]
    dest.mkdir(exist_ok=True)
    zip_url = f"{APP_SERVER}/{app['id']}.zip"
    try:
        with urllib.request.urlopen(
            urllib.request.Request(zip_url, headers={"User-Agent": "MintKit/1.0"}),
            timeout=15
        ) as r:
            data = r.read()
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            zf.extractall(dest)
    except Exception as e:
        # Fallback: write stub so the entry exists
        meta = {k: v for k, v in app.items() if k != "icon"}; meta["entry"] = "main.py"
        (dest / "game.json").write_text(json.dumps(meta, indent=2))
        (dest / "main.py").write_text(f'print("Install failed: {e}")')

def uninstall_app(app_id):
    dest = GAMES_DIR / app_id
    if dest.exists(): shutil.rmtree(dest)

def launch(game):
    entry = game["path"] / game.get("entry", "main.py")
    subprocess.Popen([sys.executable, str(entry)])

def scan_media():
    exts = {".mp3", ".ogg", ".wav", ".flac", ".xm", ".mod"}
    return sorted([p for p in MEDIA_DIR.iterdir() if p.suffix.lower() in exts]) if MEDIA_DIR.exists() else []

# --- Drawing helpers ---
def blit_c(surf, img, y):
    surf.blit(img, (SCREEN_W // 2 - img.get_width() // 2, y))

def draw_status_bar(surf, fonts):
    for i in range(3): pygame.draw.rect(surf, ACCENT, (8 + i * 13, 7, 9, 14))
    pygame.draw.rect(surf, ACCENT, (47, 10, 3, 8))
    blit_c(surf, fonts["title"].render("POCKETMINT", True, ACCENT), 4)
    now = datetime.datetime.now().strftime("%H:%M")
    info = fonts["sm"].render(f"WiFi  {now}", True, ACCENT)
    surf.blit(info, (SCREEN_W - info.get_width() - 8, 8))
    pygame.draw.line(surf, BORDER, (0, 28), (SCREEN_W, 28), 1)

def draw_section(surf, fonts, label):
    blit_c(surf, fonts["sm"].render(label, True, ACCENT), 32)
    pygame.draw.line(surf, BORDER, (0, 50), (SCREEN_W, 50), 1)

def draw_hints(surf, fonts, hints):
    pygame.draw.line(surf, BORDER, (0, SCREEN_H - 34), (SCREEN_W, SCREEN_H - 34), 1)
    x = 6
    for key, action in hints:
        ki = fonts["xs"].render(key, True, BLACK)
        kw = ki.get_width() + 8
        pygame.draw.rect(surf, ACCENT, (x, SCREEN_H - 26, kw, 18))
        surf.blit(ki, (x + 4, SCREEN_H - 24)); x += kw + 4
        ai = fonts["xs"].render(action, True, DIM)
        surf.blit(ai, (x, SCREEN_H - 24)); x += ai.get_width() + 16

# ===================== SCREENS =====================

class Boot:
    def __init__(self, screen, fonts):
        self.screen = screen; self.fonts = fonts; self.t = 0
    def update(self):
        self.t += 1; return self.t > FPS * 2
    def draw(self):
        s = self.screen; s.fill(BG)
        blit_c(s, self.fonts["big"].render("POCKETMINT", True, ACCENT), SCREEN_H // 2 - 40)
        blit_c(s, self.fonts["sm"].render(VERSION, True, DIM), SCREEN_H // 2 + 10)
        blit_c(s, self.fonts["sm"].render("." * ((self.t // 10) % 4), True, DIM), SCREEN_H // 2 + 34)

class MainMenu:
    def __init__(self, screen, fonts, games):
        self.screen = screen; self.fonts = fonts; self.games = games; self.cur = 0
    def items(self):
        n = len(self.games)
        return [
            ("LIBRARY",    f"{n} title{'s' if n != 1 else ''} installed"),
            ("POCKETMALL", STORE_URL),
            ("FRIENDS",    None),
            ("MEDIA",      None),
            ("SETTINGS",   VERSION),
        ]
    def handle(self, ev):
        items = self.items()
        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_DOWN, pygame.K_s):   self.cur = (self.cur + 1) % len(items)
            elif ev.key in (pygame.K_UP, pygame.K_w):   self.cur = (self.cur - 1) % len(items)
            elif ev.key in (pygame.K_RETURN, pygame.K_z, pygame.K_SPACE):
                return "select", items[self.cur][0]
        return None, None
    def draw(self):
        s = self.screen; s.fill(BG)
        draw_status_bar(s, self.fonts); draw_section(s, self.fonts, "HOME")
        item_h = min(60, (SCREEN_H - 90) // len(self.items()))
        for i, (label, sub) in enumerate(self.items()):
            y = 54 + i * item_h
            bg = CARD_SEL if i == self.cur else CARD
            pygame.draw.rect(s, bg, (4, y, SCREEN_W - 8, item_h - 3))
            if i == self.cur:
                pygame.draw.rect(s, ACCENT, (4, y, SCREEN_W - 8, item_h - 3), 1)
                s.blit(self.fonts["menu"].render("\u25b6", True, ACCENT), (10, y + (item_h - 3) // 2 - 10))
            s.blit(self.fonts["menu"].render(label, True, ACCENT), (32, y + 6))
            if sub: s.blit(self.fonts["sm"].render(sub, True, DIM), (32, y + 28))
        draw_hints(s, self.fonts, [("Z/Enter", "SELECT"), ("X/Esc", "BACK")])

class Library:
    def __init__(self, screen, fonts, games):
        self.screen = screen; self.fonts = fonts; self.games = games; self.cur = 0
    def handle(self, ev):
        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_DOWN, pygame.K_s):   self.cur = (self.cur + 1) % max(1, len(self.games))
            elif ev.key in (pygame.K_UP, pygame.K_w):   self.cur = (self.cur - 1) % max(1, len(self.games))
            elif ev.key in (pygame.K_RETURN, pygame.K_z, pygame.K_SPACE):
                if self.games: return "launch", self.games[self.cur]
            elif ev.key in (pygame.K_ESCAPE, pygame.K_x): return "back", None
        return None, None
    def draw(self):
        s = self.screen; s.fill(BG)
        draw_status_bar(s, self.fonts); draw_section(s, self.fonts, "LIBRARY")
        if not self.games:
            blit_c(s, self.fonts["menu"].render("No games installed", True, DIM), SCREEN_H // 2 - 14)
            blit_c(s, self.fonts["sm"].render("Browse PocketMall to install titles", True, DIM), SCREEN_H // 2 + 14)
        else:
            item_h = min(60, (SCREEN_H - 90) // len(self.games))
            for i, g in enumerate(self.games):
                y = 54 + i * item_h
                bg = CARD_SEL if i == self.cur else CARD
                pygame.draw.rect(s, bg, (4, y, SCREEN_W - 8, item_h - 3))
                if i == self.cur:
                    pygame.draw.rect(s, ACCENT, (4, y, SCREEN_W - 8, item_h - 3), 1)
                    s.blit(self.fonts["menu"].render("\u25b6", True, ACCENT), (10, y + (item_h - 3) // 2 - 10))
                s.blit(self.fonts["menu"].render(g.get("name", g["path"].name), True, ACCENT), (32, y + 6))
                s.blit(self.fonts["sm"].render(g.get("developer", ""), True, DIM), (32, y + 28))
        draw_hints(s, self.fonts, [("Z/Enter", "LAUNCH"), ("X/Esc", "BACK")])

class PocketMall:
    CATS = ["ALL", "GAME", "APP", "EMU", "MEDIA"]
    def __init__(self, screen, fonts):
        self.screen   = screen; self.fonts = fonts
        self.catalog  = load_catalog()
        self.cat_idx  = 0; self.cur = 0; self.detail = None
        self.msg = ""; self.msg_t = 0
    def filtered(self):
        cat = self.CATS[self.cat_idx]
        return self.catalog if cat == "ALL" else [a for a in self.catalog if a["category"].upper() == cat]
    def handle(self, ev):
        if self.msg_t > 0: self.msg_t -= 1
        if ev.type == pygame.KEYDOWN:
            if self.detail:
                app = self.detail
                if ev.key in (pygame.K_RETURN, pygame.K_z, pygame.K_SPACE):
                    if is_installed(app["id"]):
                        uninstall_app(app["id"]); self.msg = f"Uninstalled {app['name']}"
                    elif app["price"] > 0:
                        self.msg = f"Purchase required (${app['price']:.2f})"
                    else:
                        install_app(app); self.msg = f"Installed {app['name']}"
                    self.msg_t = FPS * 3; self.detail = None
                elif ev.key in (pygame.K_ESCAPE, pygame.K_x): self.detail = None
            else:
                items = self.filtered()
                if ev.key in (pygame.K_DOWN, pygame.K_s):   self.cur = (self.cur + 1) % max(1, len(items))
                elif ev.key in (pygame.K_UP, pygame.K_w):   self.cur = (self.cur - 1) % max(1, len(items))
                elif ev.key in (pygame.K_LEFT, pygame.K_a):  self.cat_idx = (self.cat_idx - 1) % len(self.CATS); self.cur = 0
                elif ev.key in (pygame.K_RIGHT, pygame.K_d): self.cat_idx = (self.cat_idx + 1) % len(self.CATS); self.cur = 0
                elif ev.key in (pygame.K_RETURN, pygame.K_z, pygame.K_SPACE):
                    if items: self.detail = items[self.cur]
                elif ev.key in (pygame.K_ESCAPE, pygame.K_x): return "back", None
        return None, None
    def draw(self):
        s = self.screen; s.fill(BG)
        draw_status_bar(s, self.fonts); draw_section(s, self.fonts, "POCKETMALL")
        if self.detail: self._draw_detail(s)
        else: self._draw_list(s)
        if self.msg_t > 0:
            mi = self.fonts["sm"].render(self.msg, True, ACCENT)
            mx = SCREEN_W // 2 - mi.get_width() // 2
            pygame.draw.rect(s, CARD_SEL, (mx - 8, SCREEN_H - 58, mi.get_width() + 16, 20))
            s.blit(mi, (mx, SCREEN_H - 56))
    def _draw_list(self, s):
        tab_w = SCREEN_W // len(self.CATS)
        for i, cat in enumerate(self.CATS):
            x = i * tab_w
            pygame.draw.rect(s, CARD_SEL if i == self.cat_idx else CARD, (x, 54, tab_w - 1, 18))
            if i == self.cat_idx: pygame.draw.rect(s, ACCENT, (x, 54, tab_w - 1, 18), 1)
            t = self.fonts["xs"].render(cat, True, ACCENT if i == self.cat_idx else DIM)
            s.blit(t, (x + tab_w // 2 - t.get_width() // 2, 57))
        items = self.filtered()
        if not items:
            blit_c(s, self.fonts["menu"].render("No titles in this category", True, DIM), SCREEN_H // 2)
        else:
            item_h = min(52, (SCREEN_H - 110) // len(items))
            for i, app in enumerate(items):
                y = 76 + i * item_h
                bg = CARD_SEL if i == self.cur else CARD
                pygame.draw.rect(s, bg, (4, y, SCREEN_W - 8, item_h - 2))
                if i == self.cur:
                    pygame.draw.rect(s, ACCENT, (4, y, SCREEN_W - 8, item_h - 2), 1)
                    s.blit(self.fonts["menu"].render("\u25b6", True, ACCENT), (10, y + item_h // 2 - 10))
                s.blit(self.fonts["menu"].render(app["name"], True, ACCENT), (32, y + 4))
                price = "FREE" if app["price"] == 0 else f"${app['price']:.2f}"
                pi = self.fonts["xs"].render(price, True, ACCENT if app["price"] == 0 else GOLD)
                s.blit(pi, (SCREEN_W - pi.get_width() - 40, y + 6))
                if is_installed(app["id"]):
                    ci = self.fonts["xs"].render("\u2713", True, ACCENT)
                    s.blit(ci, (SCREEN_W - 26, y + 6))
                s.blit(self.fonts["xs"].render(app["developer"], True, DIM), (32, y + item_h - 16))
        draw_hints(s, self.fonts, [("\u2190/\u2192", "CATEGORY"), ("Z/Enter", "DETAILS"), ("X/Esc", "BACK")])
    def _draw_detail(self, s):
        app = self.detail; y = 60
        s.blit(self.fonts["big"].render(app.get("icon", "?"), True, ACCENT), (16, y))
        s.blit(self.fonts["menu"].render(app["name"], True, WHITE), (72, y + 4))
        s.blit(self.fonts["sm"].render(app["developer"], True, DIM), (72, y + 28))
        ci = self.fonts["xs"].render(app["category"].upper(), True, BLACK)
        cw = ci.get_width() + 8
        pygame.draw.rect(s, ACCENT, (72, y + 46, cw, 16))
        s.blit(ci, (76, y + 48))
        price = "FREE" if app["price"] == 0 else f"${app['price']:.2f}"
        s.blit(self.fonts["sm"].render(price, True, ACCENT if app["price"] == 0 else GOLD), (72 + cw + 8, y + 46))
        pygame.draw.line(s, BORDER, (0, y + 74), (SCREEN_W, y + 74), 1)
        words = app.get("desc", "").split(); line = ""; lines = []
        for w in words:
            test = (line + " " + w).strip()
            if self.fonts["sm"].size(test)[0] < SCREEN_W - 32: line = test
            else: lines.append(line); line = w
        if line: lines.append(line)
        for j, ln in enumerate(lines):
            s.blit(self.fonts["sm"].render(ln, True, WHITE), (16, y + 82 + j * 20))
        installed = is_installed(app["id"])
        btn_text = "Uninstall" if installed else ("Install (FREE)" if app["price"] == 0 else f"Purchase ${app['price']:.2f}")
        btn_col  = RED if installed else ACCENT
        bi = self.fonts["menu"].render(btn_text, True, btn_col)
        bw = bi.get_width() + 24; bx = SCREEN_W // 2 - bw // 2; by = SCREEN_H - 80
        pygame.draw.rect(s, CARD_SEL, (bx, by, bw, 34))
        pygame.draw.rect(s, btn_col,  (bx, by, bw, 34), 1)
        s.blit(bi, (bx + 12, by + 7))
        draw_hints(s, self.fonts, [("Z/Enter", "INSTALL/REMOVE"), ("X/Esc", "BACK")])

class Friends:
    def __init__(self, screen, fonts):
        self.screen  = screen; self.fonts = fonts
        self.friends = load_friends(); self.cur = 0
        self.mode = "list"; self.input = ""
        self.msg = ""; self.msg_t = 0
    def refresh(self): self.friends = load_friends()
    def handle(self, ev):
        if self.msg_t > 0: self.msg_t -= 1
        if self.mode == "add":
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_RETURN:
                    name = self.input.strip()
                    if name and name not in self.friends:
                        self.friends.append(name); save_friends(self.friends)
                        self.msg = f"Added {name}"; self.msg_t = FPS * 2
                    self.input = ""; self.mode = "list"
                elif ev.key == pygame.K_ESCAPE: self.input = ""; self.mode = "list"
                elif ev.key == pygame.K_BACKSPACE: self.input = self.input[:-1]
                elif ev.unicode.isprintable() and len(self.input) < 24: self.input += ev.unicode
            return None, None
        if ev.type == pygame.KEYDOWN:
            items = self.friends + [None]
            if ev.key in (pygame.K_DOWN, pygame.K_s):   self.cur = (self.cur + 1) % len(items)
            elif ev.key in (pygame.K_UP, pygame.K_w):   self.cur = (self.cur - 1) % len(items)
            elif ev.key in (pygame.K_RETURN, pygame.K_z, pygame.K_SPACE):
                if self.cur == len(self.friends): self.mode = "add"
            elif ev.key == pygame.K_DELETE:
                if self.cur < len(self.friends):
                    removed = self.friends.pop(self.cur); save_friends(self.friends)
                    self.cur = max(0, self.cur - 1)
                    self.msg = f"Removed {removed}"; self.msg_t = FPS * 2
            elif ev.key in (pygame.K_ESCAPE, pygame.K_x): return "back", None
        return None, None
    def draw(self):
        s = self.screen; s.fill(BG)
        draw_status_bar(s, self.fonts); draw_section(s, self.fonts, "FRIENDS")
        all_items = self.friends + [None]
        item_h = min(52, (SCREEN_H - 110) // max(len(all_items), 1))
        for i, name in enumerate(all_items):
            y = 54 + i * item_h
            bg = CARD_SEL if i == self.cur else CARD
            pygame.draw.rect(s, bg, (4, y, SCREEN_W - 8, item_h - 2))
            if i == self.cur:
                pygame.draw.rect(s, ACCENT, (4, y, SCREEN_W - 8, item_h - 2), 1)
            if name is None:
                t = self.fonts["menu"].render("[+ Add Friend]", True, DIM)
                s.blit(t, (32, y + item_h // 2 - t.get_height() // 2))
            else:
                online = (sum(ord(c) for c in name) % 3 != 0)
                pygame.draw.circle(s, ACCENT if online else DIM, (38, y + item_h // 2), 5)
                s.blit(self.fonts["menu"].render(name, True, WHITE), (52, y + 6))
                s.blit(self.fonts["xs"].render("Online" if online else "Offline", True, ACCENT if online else DIM), (52, y + 26))
                di = self.fonts["xs"].render("Del = remove", True, BORDER)
                s.blit(di, (SCREEN_W - di.get_width() - 8, y + 6))
        if self.mode == "add":
            ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 160)); s.blit(ov, (0, 0))
            pygame.draw.rect(s, CARD,  (80, 160, SCREEN_W - 160, 120))
            pygame.draw.rect(s, ACCENT,(80, 160, SCREEN_W - 160, 120), 1)
            blit_c(s, self.fonts["menu"].render("Add Friend", True, ACCENT), 172)
            s.blit(self.fonts["sm"].render("Enter username:", True, DIM), (96, 200))
            s.blit(self.fonts["menu"].render(self.input + "_", True, WHITE), (96, 218))
            blit_c(s, self.fonts["xs"].render("Enter = confirm   Esc = cancel", True, DIM), 258)
        if self.msg_t > 0:
            mi = self.fonts["sm"].render(self.msg, True, ACCENT); blit_c(s, mi, SCREEN_H - 56)
        draw_hints(s, self.fonts, [("Z/Enter", "SELECT"), ("Del", "REMOVE"), ("X/Esc", "BACK")])

class Media:
    def __init__(self, screen, fonts):
        self.screen  = screen; self.fonts = fonts
        self.tracks  = scan_media(); self.cur = 0
        self.playing = False; self.paused = False
        self.track_start = 0
        pygame.mixer.init()
    def play(self, idx=None):
        if idx is not None: self.cur = idx
        t = self.tracks[self.cur] if self.tracks else None
        if not t: return
        try:
            pygame.mixer.music.load(str(t)); pygame.mixer.music.play()
            self.playing = True; self.paused = False
            self.track_start = pygame.time.get_ticks()
        except Exception: self.playing = False
    def stop(self):
        pygame.mixer.music.stop(); self.playing = False; self.paused = False
    def toggle_pause(self):
        if self.playing and not self.paused: pygame.mixer.music.pause(); self.paused = True
        elif self.paused: pygame.mixer.music.unpause(); self.paused = False
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
            if ev.key in (pygame.K_DOWN, pygame.K_s):    self.cur = (self.cur + 1) % max(1, len(self.tracks))
            elif ev.key in (pygame.K_UP, pygame.K_w):    self.cur = (self.cur - 1) % max(1, len(self.tracks))
            elif ev.key in (pygame.K_RETURN, pygame.K_z, pygame.K_SPACE):
                if self.playing or self.paused: self.toggle_pause()
                else: self.play(self.cur)
            elif ev.key in (pygame.K_RIGHT, pygame.K_d): self.next_track()
            elif ev.key in (pygame.K_LEFT,  pygame.K_a): self.prev_track()
            elif ev.key == pygame.K_x:       self.stop()
            elif ev.key == pygame.K_ESCAPE:  self.stop(); return "back", None
        return None, None
    def draw(self):
        s = self.screen; s.fill(BG)
        draw_status_bar(s, self.fonts); draw_section(s, self.fonts, "MEDIA")
        if not self.tracks:
            blit_c(s, self.fonts["menu"].render("No media files found", True, DIM), SCREEN_H // 2 - 20)
            blit_c(s, self.fonts["sm"].render(f"Add .mp3/.ogg/.wav to: {MEDIA_DIR.name}/", True, DIM), SCREEN_H // 2 + 14)
            draw_hints(s, self.fonts, [("X/Esc", "BACK")]); return
        y_start = 54
        if self.playing or self.paused:
            t = self.tracks[self.cur]
            np_text = ("\u23f8 " if self.paused else "\u25b6 ") + t.stem[:40]
            pygame.draw.rect(s, CARD_SEL, (0, 54, SCREEN_W, 22))
            pygame.draw.line(s, BORDER, (0, 54), (SCREEN_W, 54), 1)
            pygame.draw.line(s, BORDER, (0, 76), (SCREEN_W, 76), 1)
            blit_c(s, self.fonts["sm"].render(np_text, True, ACCENT), 58)
            elapsed = (pygame.time.get_ticks() - self.track_start) / 1000
            bar_w = int((elapsed % 60) / 60 * (SCREEN_W - 40))
            pygame.draw.rect(s, BORDER, (20, 73, SCREEN_W - 40, 3))
            pygame.draw.rect(s, ACCENT,  (20, 73, bar_w, 3))
            y_start = 80
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
        draw_hints(s, self.fonts, [("Z/Enter", "PLAY/PAUSE"), ("\u2190/\u2192", "PREV/NEXT"), ("X", "STOP"), ("Esc", "BACK")])

class Settings:
    OPTS = [("WiFi", None), ("Brightness", None), ("Volume", None),
            ("About", VERSION), ("Shutdown", None), ("Back", None)]
    def __init__(self, screen, fonts):
        self.screen = screen; self.fonts = fonts; self.cur = 0; self.volume = 80
    def handle(self, ev):
        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_DOWN, pygame.K_s):   self.cur = (self.cur + 1) % len(self.OPTS)
            elif ev.key in (pygame.K_UP, pygame.K_w):   self.cur = (self.cur - 1) % len(self.OPTS)
            elif ev.key in (pygame.K_LEFT, pygame.K_a):
                if self.OPTS[self.cur][0] == "Volume":
                    self.volume = max(0, self.volume - 10); pygame.mixer.music.set_volume(self.volume / 100)
            elif ev.key in (pygame.K_RIGHT, pygame.K_d):
                if self.OPTS[self.cur][0] == "Volume":
                    self.volume = min(100, self.volume + 10); pygame.mixer.music.set_volume(self.volume / 100)
            elif ev.key in (pygame.K_RETURN, pygame.K_z, pygame.K_SPACE):
                label = self.OPTS[self.cur][0]
                if label == "Shutdown":
                    if IS_LINUX: subprocess.run(["poweroff"])
                if label == "Back": return "back", None
            elif ev.key in (pygame.K_ESCAPE, pygame.K_x): return "back", None
        return None, None
    def draw(self):
        s = self.screen; s.fill(BG)
        draw_status_bar(s, self.fonts); draw_section(s, self.fonts, "SETTINGS")
        item_h = min(60, (SCREEN_H - 90) // len(self.OPTS))
        for i, (label, sub) in enumerate(self.OPTS):
            y = 54 + i * item_h
            bg = CARD_SEL if i == self.cur else CARD
            pygame.draw.rect(s, bg, (4, y, SCREEN_W - 8, item_h - 3))
            if i == self.cur:
                pygame.draw.rect(s, ACCENT, (4, y, SCREEN_W - 8, item_h - 3), 1)
                s.blit(self.fonts["menu"].render("\u25b6", True, ACCENT), (10, y + (item_h - 3) // 2 - 10))
            s.blit(self.fonts["menu"].render(label, True, ACCENT), (32, y + 6))
            if label == "Volume":
                bar_filled = int(self.volume / 100 * 160)
                pygame.draw.rect(s, BORDER, (SCREEN_W - 200, y + 14, 160, 8))
                pygame.draw.rect(s, ACCENT,  (SCREEN_W - 200, y + 14, bar_filled, 8))
                s.blit(self.fonts["xs"].render(f"{self.volume}%", True, DIM), (SCREEN_W - 34, y + 12))
            elif sub:
                s.blit(self.fonts["sm"].render(str(sub), True, DIM), (32, y + 28))
        draw_hints(s, self.fonts, [("Z/Enter", "SELECT"), ("\u2190/\u2192", "ADJUST"), ("X/Esc", "BACK")])

# --- Main ---
def main():
    pygame.init(); pygame.joystick.init()
    if pygame.joystick.get_count(): pygame.joystick.Joystick(0).init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("MintKit")
    clock  = pygame.time.Clock()
    fonts  = {
        "big":   pygame.font.SysFont("Courier New", 36, bold=True),
        "title": pygame.font.SysFont("Courier New", 20, bold=True),
        "menu":  pygame.font.SysFont("Courier New", 19, bold=True),
        "sm":    pygame.font.SysFont("Courier New", 13),
        "xs":    pygame.font.SysFont("Courier New", 12),
    }
    games   = load_games()
    boot    = Boot(screen, fonts)
    menu    = MainMenu(screen, fonts, games)
    lib     = Library(screen, fonts, games)
    mall    = PocketMall(screen, fonts)
    friends = Friends(screen, fonts)
    media   = Media(screen, fonts)
    setts   = Settings(screen, fonts)
    state   = "boot"; active = boot

    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT: pygame.quit(); sys.exit()
            if state == "menu":
                act, data = menu.handle(ev)
                if act == "select":
                    if data == "LIBRARY":    lib.games = load_games();   lib.cur = 0;     state = "library"; active = lib
                    elif data == "POCKETMALL": mall.catalog = load_catalog(); mall.cur = 0; state = "mall";    active = mall
                    elif data == "FRIENDS":  friends.refresh(); friends.cur = 0;           state = "friends"; active = friends
                    elif data == "MEDIA":    media.tracks = scan_media(); media.cur = 0;   state = "media";   active = media
                    elif data == "SETTINGS":                                                state = "settings"; active = setts
            elif state in ("library", "mall", "friends", "media", "settings"):
                act, data = active.handle(ev)
                if act == "back": menu.games = load_games(); state = "menu"; active = menu
                elif act == "launch" and state == "library": launch(data)
        if state == "boot":
            if boot.update(): state = "menu"; active = menu
            boot.draw()
        else: active.draw()
        pygame.display.flip()
        clock.tick(FPS)

if __name__ == "__main__": main()