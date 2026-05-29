#!/usr/bin/env python3
# rootfs/apps/pocketcast/main.py -- PocketCast v1.0
import os, sys, json, time
from pathlib import Path

IS_LINUX = sys.platform == "linux"
if IS_LINUX:
    os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")
    os.environ.setdefault("SDL_AUDIODRIVER", "alsa")

import pygame

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "launcher"))
import themes as th

SCREEN_W, SCREEN_H = 640, 480
FPS    = 30
PAD    = 12
HEADER = 36
ROW_H  = 52

DATA_DIR    = Path(os.environ.get("MINTKIT_DATA", Path.home() / ".mintkit"))
POD_DIR     = DATA_DIR / "podcasts"
FEEDS_FILE  = DATA_DIR / "podcast_feeds.json"
PROG_FILE   = DATA_DIR / "podcast_progress.json"

def load_feeds():
    if FEEDS_FILE.exists():
        try: return json.loads(FEEDS_FILE.read_text())
        except Exception: pass
    return []

def load_progress():
    if PROG_FILE.exists():
        try: return json.loads(PROG_FILE.read_text())
        except Exception: pass
    return {}

def save_progress(prog):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROG_FILE.write_text(json.dumps(prog, indent=2))

pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("PocketCast")
clock  = pygame.time.Clock()
font_lg = pygame.font.SysFont("monospace", 15, bold=True)
font_sm = pygame.font.SysFont("monospace", 11)
pygame.key.set_repeat(400, 60)

feeds    = load_feeds()
progress = load_progress()
cur      = 0
playing  = None
paused   = False

VIEW_FEEDS   = "feeds"
VIEW_EPISODES = "episodes"
view = VIEW_FEEDS
sel_feed = 0
sel_ep   = 0
episodes = []

def load_local_episodes(feed):
    feed_dir = POD_DIR / feed.get("id", "unknown")
    if not feed_dir.exists():
        return []
    eps = []
    for f in sorted(feed_dir.glob("*.mp3")) + sorted(feed_dir.glob("*.ogg")):
        prog = progress.get(str(f), {"pos": 0, "done": False})
        eps.append({"title": f.stem, "path": str(f), "progress": prog})
    return eps

def draw():
    p = th.get()
    screen.fill(p["bg"])
    pygame.draw.rect(screen, p["bar"], (0, 0, SCREEN_W, HEADER))
    pygame.draw.line(screen, p["border"], (0, HEADER), (SCREEN_W, HEADER))
    title = font_lg.render("PocketCast", True, p["accent"])
    screen.blit(title, (PAD, (HEADER - title.get_height()) // 2))
    if playing:
        now = pygame.mixer.music.get_pos() // 1000
        status = font_sm.render(f"{'❚❚' if paused else '▶'} {playing['title'][:28]} {now//60}:{now%60:02d}", True, p["dim"])
        screen.blit(status, (SCREEN_W - status.get_width() - PAD, (HEADER - status.get_height()) // 2))

    if view == VIEW_FEEDS:
        y = HEADER + PAD
        for i, feed in enumerate(feeds or [{"name": "No feeds — add via MintShell"}]):
            sel = (i == sel_feed)
            bg  = tuple(min(255, c + 10) for c in p["card"]) if sel else p["card"]
            pygame.draw.rect(screen, bg, (PAD, y, SCREEN_W - PAD * 2, ROW_H - 4), border_radius=4)
            if sel:
                pygame.draw.rect(screen, p["accent"], (PAD, y, SCREEN_W - PAD * 2, ROW_H - 4), 1, border_radius=4)
            screen.blit(font_lg.render(feed.get("name", "Feed")[:36], True, p["white"]), (PAD + 10, y + 8))
            screen.blit(font_sm.render(feed.get("url", "")[:48], True, p["dim"]), (PAD + 10, y + 28))
            y += ROW_H
    else:
        y = HEADER + PAD
        for i, ep in enumerate(episodes):
            sel = (i == sel_ep)
            done = ep["progress"].get("done", False)
            bg   = tuple(min(255, c + 10) for c in p["card"]) if sel else p["card"]
            pygame.draw.rect(screen, bg, (PAD, y, SCREEN_W - PAD * 2, ROW_H - 4), border_radius=4)
            if sel:
                pygame.draw.rect(screen, p["accent"], (PAD, y, SCREEN_W - PAD * 2, ROW_H - 4), 1, border_radius=4)
            check = font_sm.render("✓" if done else " ", True, p["accent"])
            screen.blit(check, (PAD + 6, y + 14))
            screen.blit(font_lg.render(ep["title"][:36], True, p["dim"] if done else p["white"]), (PAD + 24, y + 8))
            pos = ep["progress"].get("pos", 0)
            if pos > 0:
                pt = font_sm.render(f"{pos//60}:{pos%60:02d}", True, p["dim"])
                screen.blit(pt, (SCREEN_W - pt.get_width() - PAD * 2, y + 14))
            y += ROW_H
        if not episodes:
            msg = font_lg.render("No downloaded episodes", True, p["dim"])
            screen.blit(msg, (SCREEN_W // 2 - msg.get_width() // 2, SCREEN_H // 2))

    # Bottom bar
    pygame.draw.line(screen, p["border"], (0, SCREEN_H - 34), (SCREEN_W, SCREEN_H - 34))
    hints = [("Z", "PLAY"), ("P", "PAUSE"), ("Esc", "BACK")] if view == VIEW_EPISODES else [("Z", "OPEN"), ("Esc", "QUIT")]
    hx = 6
    for key, act in hints:
        ki = font_sm.render(key, True, p["black"]); kw = ki.get_width() + 8
        pygame.draw.rect(screen, p["accent"], (hx, SCREEN_H - 26, kw, 18))
        screen.blit(ki, (hx + 4, SCREEN_H - 24)); hx += kw + 4
        ai = font_sm.render(act, True, p["dim"])
        screen.blit(ai, (hx, SCREEN_H - 24)); hx += ai.get_width() + 12

running = True
while running:
    clock.tick(FPS)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if view == VIEW_FEEDS:
                if event.key in (pygame.K_UP, pygame.K_w): sel_feed = max(0, sel_feed - 1)
                elif event.key in (pygame.K_DOWN, pygame.K_s): sel_feed = min(len(feeds) - 1, sel_feed + 1)
                elif event.key in (pygame.K_RETURN, pygame.K_z):
                    if feeds:
                        episodes = load_local_episodes(feeds[sel_feed])
                        sel_ep = 0; view = VIEW_EPISODES
                elif event.key in (pygame.K_ESCAPE, pygame.K_b): running = False
            else:
                if event.key in (pygame.K_UP, pygame.K_w): sel_ep = max(0, sel_ep - 1)
                elif event.key in (pygame.K_DOWN, pygame.K_s): sel_ep = min(len(episodes) - 1, sel_ep + 1)
                elif event.key in (pygame.K_RETURN, pygame.K_z):
                    if episodes:
                        ep = episodes[sel_ep]
                        pygame.mixer.music.load(ep["path"])
                        start = ep["progress"].get("pos", 0)
                        pygame.mixer.music.play(start=start)
                        playing = ep; paused = False
                elif event.key == pygame.K_p:
                    if playing:
                        if paused: pygame.mixer.music.unpause()
                        else: pygame.mixer.music.pause()
                        paused = not paused
                elif event.key in (pygame.K_ESCAPE, pygame.K_b):
                    if playing:
                        pos = pygame.mixer.music.get_pos() // 1000
                        progress[playing["path"]] = {"pos": pos, "done": False}
                        save_progress(progress)
                        pygame.mixer.music.stop(); playing = None
                    view = VIEW_FEEDS
    draw()
    pygame.display.flip()

if playing:
    pos = pygame.mixer.music.get_pos() // 1000
    progress[playing["path"]] = {"pos": pos, "done": False}
    save_progress(progress)
pygame.quit()