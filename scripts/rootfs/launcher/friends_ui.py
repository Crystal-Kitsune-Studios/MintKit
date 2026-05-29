#!/usr/bin/env python3
# rootfs/launcher/friends_ui.py -- Friends & Leaderboard (OS built-in)
import json
from pathlib import Path
from . import scores as sc
from . import themes as th
import pygame

# ── Theme ──────────────────────────────────────────────────────────────
SCREEN_W, SCREEN_H = 640, 480
FPS    = 60
BG     = (10,  26,  16)
CARD   = (13,  32,  20)
ACCENT = (61, 204, 112)
DIM    = (50, 130,  75)
WHITE  = (180, 240, 195)
LOCKED = (50,  70,  55)
BAR    = ( 6,  13,   8)
BORDER = (29, 100,  55)
GOLD   = (240, 200,  60)
SILVER = (180, 190, 200)
BRONZE = (180, 110,  50)
RED    = (220,  60,  60)
GREEN  = ( 40, 200,  90)

PAD    = 10
HEADER = 36
TAB_H  = 26

import os
from pathlib import Path

SCREEN_W, SCREEN_H = 640, 480
FPS       = 60
PAD       = 10
HEADER    = 36
TAB_H     = 26
ROW_H     = 48
CONTENT_Y = HEADER + TAB_H + PAD
CONTENT_H = SCREEN_H - CONTENT_Y - 36
VIS       = CONTENT_H // ROW_H

DATA_DIR     = Path(os.environ.get("MINTKIT_DATA", Path.home() / ".mintkit"))
FRIENDS_FILE = DATA_DIR / "friends.json"

GOLD   = (240, 200,  60)
SILVER = (180, 190, 200)
BRONZE = (180, 110,  50)
GREEN  = ( 40, 200,  90)

TABS = ["FRIENDS", "LEADERBOARD"]


def load_friends():
    if FRIENDS_FILE.exists():
        try: return json.loads(FRIENDS_FILE.read_text())
        except Exception: pass
    return []

def save_friends(friends):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    FRIENDS_FILE.write_text(json.dumps(friends, indent=2))

def rank_color(i): return [GOLD, SILVER, BRONZE][i] if i < 3 else None


def run(screen, clock):
    """Called by the launcher. Shows friends & leaderboard on the shared SDL screen."""
    font_lg = pygame.font.SysFont("monospace", 15, bold=True)
    font_sm = pygame.font.SysFont("monospace", 11)
    font_ic = pygame.font.SysFont("monospace", 18)
    pygame.key.set_repeat(400, 60)

    tab      = 0
    friends  = load_friends()
    fr_cur   = 0
    fr_input = ""
    fr_mode  = "list"
    lb_entries = sc.get_all()
    lb_cur   = 0
    lb_scroll = 0

    running = True
    while running:
        clock.tick(FPS)
        p = th.get()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RIGHT and fr_mode == "list":
                    tab = (tab + 1) % len(TABS)
                elif event.key == pygame.K_LEFT and fr_mode == "list":
                    tab = (tab - 1) % len(TABS)
                elif event.key in (pygame.K_ESCAPE, pygame.K_b) and fr_mode == "list":
                    running = False
                elif tab == 0:
                    all_items = friends + [None]
                    if fr_mode == "list":
                        if event.key in (pygame.K_UP, pygame.K_w):
                            fr_cur = max(0, fr_cur - 1)
                        elif event.key in (pygame.K_DOWN, pygame.K_s):
                            fr_cur = min(len(all_items) - 1, fr_cur + 1)
                        elif event.key in (pygame.K_RETURN, pygame.K_z):
                            if fr_cur == len(friends):
                                fr_mode = "add"; fr_input = ""
                        elif event.key == pygame.K_DELETE:
                            if fr_cur < len(friends):
                                friends.pop(fr_cur); save_friends(friends)
                                fr_cur = max(0, fr_cur - 1)
                    elif fr_mode == "add":
                        if event.key == pygame.K_RETURN:
                            name = fr_input.strip()
                            if name and name not in friends:
                                friends.append(name); save_friends(friends)
                            fr_mode = "list"
                        elif event.key == pygame.K_ESCAPE:
                            fr_mode = "list"
                        elif event.key == pygame.K_BACKSPACE:
                            fr_input = fr_input[:-1]
                        elif event.unicode and event.unicode.isprintable() and len(fr_input) < 24:
                            fr_input += event.unicode
                elif tab == 1:
                    if event.key in (pygame.K_DOWN, pygame.K_s):
                        if lb_cur < len(lb_entries) - 1:
                            lb_cur += 1
                            if lb_cur >= lb_scroll + VIS: lb_scroll += 1
                    elif event.key in (pygame.K_UP, pygame.K_w):
                        if lb_cur > 0:
                            lb_cur -= 1
                            if lb_cur < lb_scroll: lb_scroll -= 1
                    elif event.key == pygame.K_r:
                        lb_entries = sc.get_all()

        screen.fill(p["bg"])

        # Header
        pygame.draw.rect(screen, p["bar"], (0, 0, SCREEN_W, HEADER))
        pygame.draw.line(screen, p["border"], (0, HEADER), (SCREEN_W, HEADER))
        title = font_lg.render("Friends & Leaderboard", True, p["accent"])
        screen.blit(title, (PAD, (HEADER - title.get_height()) // 2))
        hint = font_sm.render("←→ tabs  Esc back", True, p["dim"])
        screen.blit(hint, (SCREEN_W - hint.get_width() - PAD, (HEADER - hint.get_height()) // 2))

        # Tabs
        tw = SCREEN_W // len(TABS)
        for i, name in enumerate(TABS):
            x = i * tw
            col = p["accent"] if i == tab else p["locked"]
            pygame.draw.rect(screen, p["bar"], (x, HEADER, tw, TAB_H))
            if i == tab:
                pygame.draw.rect(screen, p["accent"], (x, HEADER + TAB_H - 2, tw, 2))
            t = font_sm.render(name, True, col)
            screen.blit(t, (x + tw // 2 - t.get_width() // 2, HEADER + (TAB_H - t.get_height()) // 2))
        pygame.draw.line(screen, p["border"], (0, HEADER + TAB_H), (SCREEN_W, HEADER + TAB_H))

        if tab == 0:
            # Friends list
            y = CONTENT_Y
            all_items = friends + [None]
            for i, name in enumerate(all_items):
                if y + ROW_H > SCREEN_H - 36: break
                sel = (i == fr_cur)
                bg  = tuple(min(255, c + 12) for c in p["card"]) if sel else p["card"]
                pygame.draw.rect(screen, bg, (PAD, y, SCREEN_W - PAD * 2, ROW_H - 4), border_radius=4)
                if sel:
                    pygame.draw.rect(screen, p["accent"], (PAD, y, SCREEN_W - PAD * 2, ROW_H - 4), 1, border_radius=4)
                if name is None:
                    t = font_lg.render("[+ Add Friend]", True, p["dim"])
                    screen.blit(t, (PAD + 12, y + (ROW_H - 4 - t.get_height()) // 2))
                else:
                    online = (sum(ord(c) for c in name) % 3 != 0)
                    dot_col = GREEN if online else p["locked"]
                    pygame.draw.circle(screen, dot_col, (PAD + 16, y + (ROW_H - 4) // 2), 5)
                    screen.blit(font_lg.render(name[:28], True, p["white"]), (PAD + 28, y + 6))
                    screen.blit(font_sm.render("Online" if online else "Offline", True, dot_col), (PAD + 28, y + 26))
                    if sel:
                        del_t = font_sm.render("Del = remove", True, p["dim"])
                        screen.blit(del_t, (SCREEN_W - del_t.get_width() - PAD * 2, y + 14))
                y += ROW_H
            if fr_mode == "add":
                ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
                ov.fill((0, 0, 0, 160)); screen.blit(ov, (0, 0))
                pygame.draw.rect(screen, p["card"],  (80, 170, SCREEN_W - 160, 100), border_radius=6)
                pygame.draw.rect(screen, p["accent"],(80, 170, SCREEN_W - 160, 100), 1, border_radius=6)
                hdr2 = font_lg.render("Add Friend", True, p["accent"])
                screen.blit(hdr2, (SCREEN_W // 2 - hdr2.get_width() // 2, 182))
                screen.blit(font_sm.render("Username:", True, p["dim"]), (96, 212))
                screen.blit(font_lg.render(fr_input + "_", True, p["white"]), (96, 228))
        else:
            # Leaderboard
            visible = lb_entries[lb_scroll:lb_scroll + VIS]
            for i, entry in enumerate(visible):
                rank = lb_scroll + i
                y = CONTENT_Y + i * ROW_H
                sel = (rank == lb_cur)
                bg  = tuple(min(255, c + 12) for c in p["card"]) if sel else p["card"]
                pygame.draw.rect(screen, bg, (PAD, y, SCREEN_W - PAD * 2, ROW_H - 4), border_radius=4)
                if sel:
                    pygame.draw.rect(screen, p["accent"], (PAD, y, SCREEN_W - PAD * 2, ROW_H - 4), 1, border_radius=4)
                rc = rank_color(rank) or p["dim"]
                medal = ["🥇", "🥈", "🥉"][rank] if rank < 3 else f"#{rank + 1}"
                screen.blit(font_ic.render(medal, True, rc), (PAD + 6, y + (ROW_H - 4 - font_ic.get_linesize()) // 2))
                screen.blit(font_ic.render(entry["icon"], True, p["accent"]), (PAD + 34, y + (ROW_H - 4 - font_ic.get_linesize()) // 2))
                screen.blit(font_lg.render(entry["name"], True, p["white"]), (PAD + 60, y + 6))
                score_str = f"{entry['best']:,} {entry['unit']}" if entry["best"] > 0 else "no score yet"
                score_col = rc if rank < 3 and entry["best"] > 0 else (p["accent"] if entry["best"] > 0 else p["locked"])
                sc_surf = font_lg.render(score_str, True, score_col)
                screen.blit(sc_surf, (SCREEN_W - sc_surf.get_width() - PAD * 2, y + 6))
                if entry["best_at"]:
                    ds = font_sm.render(entry["best_at"][:10], True, p["dim"])
                    screen.blit(ds, (SCREEN_W - ds.get_width() - PAD * 2, y + 26))

        # Bottom hint bar
        pygame.draw.line(screen, p["border"], (0, SCREEN_H - 34), (SCREEN_W, SCREEN_H - 34))
        hx = 6
        hints = [("Z", "SELECT"), ("Del", "REMOVE"), ("Esc", "BACK")] if tab == 0 else [("↑↓", "SCROLL"), ("R", "REFRESH"), ("Esc", "BACK")]
        for key, act in hints:
            ki = font_sm.render(key, True, p["black"]); kw = ki.get_width() + 8
            pygame.draw.rect(screen, p["accent"], (hx, SCREEN_H - 26, kw, 18))
            screen.blit(ki, (hx + 4, SCREEN_H - 24)); hx += kw + 4
            ai = font_sm.render(act, True, p["dim"])
            screen.blit(ai, (hx, SCREEN_H - 24)); hx += ai.get_width() + 12

        pygame.display.flip()

    pygame.key.set_repeat(400, 60)  # restore launcher repeat