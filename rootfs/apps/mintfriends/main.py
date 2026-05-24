#!/usr/bin/env python3
# rootfs/apps/mintfriends/main.py -- Friends & Leaderboard v1.0
import os, sys, platform, json
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "launcher"))
import scores as sc

IS_LINUX = platform.system() == "Linux"
if IS_LINUX:
    os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")
    os.environ.setdefault("SDL_AUDIODRIVER", "alsa")

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

DATA_DIR     = Path(os.environ.get("MINTKIT_DATA", Path.home() / ".mintkit"))
FRIENDS_FILE = DATA_DIR / "friends.json"

def load_friends():
    if FRIENDS_FILE.exists():
        try: return json.loads(FRIENDS_FILE.read_text())
        except Exception: pass
    return []

def save_friends(friends):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    FRIENDS_FILE.write_text(json.dumps(friends, indent=2))

pygame.init()
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("Friends")
clock  = pygame.time.Clock()
font_lg = pygame.font.SysFont("monospace", 15, bold=True)
font_sm = pygame.font.SysFont("monospace", 11)
font_ic = pygame.font.SysFont("monospace", 18)
pygame.key.set_repeat(400, 60)

TABS = ["FRIENDS", "LEADERBOARD"]
tab  = 0

# ── Friends tab state ──────────────────────────────────────────────────
friends  = load_friends()
fr_cur   = 0
fr_input = ""          # text entry for adding a friend
fr_mode  = "list"      # list | add

# ── Leaderboard tab state ───────────────────────────────────────────────
lb_entries = sc.get_all()
lb_cur     = 0
lb_scroll  = 0

ROW_H   = 48
CONTENT_Y = HEADER + TAB_H + PAD
CONTENT_H = SCREEN_H - CONTENT_Y - 36
VIS       = CONTENT_H // ROW_H

# ── Medal colors helper ───────────────────────────────────────────────────
def rank_color(i): return [GOLD, SILVER, BRONZE][i] if i < 3 else DIM

# ── Draw helpers ────────────────────────────────────────────────────────────
def draw_header():
    pygame.draw.rect(screen, BAR, (0, 0, SCREEN_W, HEADER))
    pygame.draw.line(screen, BORDER, (0, HEADER), (SCREEN_W, HEADER))
    title = font_lg.render("Friends & Leaderboard", True, ACCENT)
    screen.blit(title, (PAD, (HEADER - title.get_height()) // 2))
    hint = font_sm.render("←→ tabs  B back", True, DIM)
    screen.blit(hint, (SCREEN_W - hint.get_width() - PAD, (HEADER - hint.get_height()) // 2))

def draw_tabs():
    tw = SCREEN_W // len(TABS)
    for i, name in enumerate(TABS):
        x = i * tw
        col = ACCENT if i == tab else LOCKED
        pygame.draw.rect(screen, BAR, (x, HEADER, tw, TAB_H))
        if i == tab:
            pygame.draw.rect(screen, ACCENT, (x, HEADER + TAB_H - 2, tw, 2))
        t = font_sm.render(name, True, col)
        screen.blit(t, (x + tw // 2 - t.get_width() // 2, HEADER + (TAB_H - t.get_height()) // 2))
    pygame.draw.line(screen, BORDER, (0, HEADER + TAB_H), (SCREEN_W, HEADER + TAB_H))

def draw_friends():
    global fr_cur, fr_input, fr_mode, friends
    y = CONTENT_Y
    all_items = friends + [None]  # None = add button

    for i, name in enumerate(all_items):
        if y + ROW_H > SCREEN_H - 36: break
        sel = (i == fr_cur)
        bg  = (18, 45, 22) if sel else CARD
        pygame.draw.rect(screen, bg, (PAD, y, SCREEN_W - PAD * 2, ROW_H - 4), border_radius=4)
        if sel:
            pygame.draw.rect(screen, ACCENT, (PAD, y, SCREEN_W - PAD * 2, ROW_H - 4), 1, border_radius=4)

        if name is None:
            t = font_lg.render("[+ Add Friend]", True, DIM)
            screen.blit(t, (PAD + 12, y + (ROW_H - 4 - t.get_height()) // 2))
        else:
            # Deterministic "online" status from name hash
            online = (sum(ord(c) for c in name) % 3 != 0)
            dot_col = GREEN if online else LOCKED
            pygame.draw.circle(screen, dot_col, (PAD + 16, y + (ROW_H - 4) // 2), 5)
            nm = font_lg.render(name[:28], True, WHITE)
            screen.blit(nm, (PAD + 28, y + 6))
            st = font_sm.render("Online" if online else "Offline", True, dot_col)
            screen.blit(st, (PAD + 28, y + 26))
            # Show remove hint for selected
            if sel:
                del_t = font_sm.render("Del = remove", True, DIM)
                screen.blit(del_t, (SCREEN_W - del_t.get_width() - PAD * 2, y + 14))
        y += ROW_H

    # Add friend overlay
    if fr_mode == "add":
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 160))
        screen.blit(ov, (0, 0))
        pygame.draw.rect(screen, CARD, (80, 170, SCREEN_W - 160, 100), border_radius=6)
        pygame.draw.rect(screen, ACCENT, (80, 170, SCREEN_W - 160, 100), 1, border_radius=6)
        hdr = font_lg.render("Add Friend", True, ACCENT)
        screen.blit(hdr, (SCREEN_W // 2 - hdr.get_width() // 2, 182))
        prompt = font_sm.render("Username:", True, DIM)
        screen.blit(prompt, (96, 212))
        inp = font_lg.render(fr_input + "_", True, WHITE)
        screen.blit(inp, (96, 228))

    # Hints
    pygame.draw.line(screen, BORDER, (0, SCREEN_H - 34), (SCREEN_W, SCREEN_H - 34))
    hx = 6
    for key, act in [("Z", "SELECT"), ("Del", "REMOVE"), ("B/Esc", "BACK")]:
        ki = font_sm.render(key, True, BAR); kw = ki.get_width() + 8
        pygame.draw.rect(screen, ACCENT, (hx, SCREEN_H - 26, kw, 18))
        screen.blit(ki, (hx + 4, SCREEN_H - 24)); hx += kw + 4
        ai = font_sm.render(act, True, DIM)
        screen.blit(ai, (hx, SCREEN_H - 24)); hx += ai.get_width() + 12

def draw_leaderboard():
    visible = lb_entries[lb_scroll:lb_scroll + VIS]
    for i, entry in enumerate(visible):
        rank = lb_scroll + i
        y = CONTENT_Y + i * ROW_H
        sel = (rank == lb_cur)
        bg  = (18, 45, 22) if sel else CARD
        pygame.draw.rect(screen, bg, (PAD, y, SCREEN_W - PAD * 2, ROW_H - 4), border_radius=4)
        if sel:
            pygame.draw.rect(screen, ACCENT, (PAD, y, SCREEN_W - PAD * 2, ROW_H - 4), 1, border_radius=4)

        rc = rank_color(rank)
        medal = ["🥇", "🥈", "🥉"][rank] if rank < 3 else f"#{rank + 1}"
        medal_surf = font_ic.render(medal, True, rc)
        screen.blit(medal_surf, (PAD + 6, y + (ROW_H - 4 - medal_surf.get_height()) // 2))

        ic = font_ic.render(entry["icon"], True, ACCENT)
        screen.blit(ic, (PAD + 34, y + (ROW_H - 4 - ic.get_height()) // 2))

        name_surf = font_lg.render(entry["name"], True, WHITE)
        screen.blit(name_surf, (PAD + 60, y + 6))

        if entry["best"] > 0:
            score_str = f"{entry['best']:,} {entry['unit']}"
            score_col = rc if rank < 3 else ACCENT
        else:
            score_str = "no score yet"
            score_col = LOCKED
        sc_surf = font_lg.render(score_str, True, score_col)
        screen.blit(sc_surf, (SCREEN_W - sc_surf.get_width() - PAD * 2, y + 6))

        if entry["best_at"]:
            date_surf = font_sm.render(entry["best_at"][:10], True, DIM)
            screen.blit(date_surf, (SCREEN_W - date_surf.get_width() - PAD * 2, y + 26))

    # Scroll indicators
    if lb_scroll > 0:
        ind = font_sm.render(f"▲ {lb_scroll} more", True, ACCENT)
        screen.blit(ind, (SCREEN_W - ind.get_width() - PAD, CONTENT_Y))
    if lb_scroll + VIS < len(lb_entries):
        ind = font_sm.render(f"▼ {len(lb_entries) - lb_scroll - VIS} more", True, ACCENT)
        screen.blit(ind, (SCREEN_W - ind.get_width() - PAD, SCREEN_H - 50))

    pygame.draw.line(screen, BORDER, (0, SCREEN_H - 34), (SCREEN_W, SCREEN_H - 34))
    hx = 6
    for key, act in [("↑↓", "SCROLL"), ("B/Esc", "BACK")]:
        ki = font_sm.render(key, True, BAR); kw = ki.get_width() + 8
        pygame.draw.rect(screen, ACCENT, (hx, SCREEN_H - 26, kw, 18))
        screen.blit(ki, (hx + 4, SCREEN_H - 24)); hx += kw + 4
        ai = font_sm.render(act, True, DIM)
        screen.blit(ai, (hx, SCREEN_H - 24)); hx += ai.get_width() + 12

# ── Main loop ────────────────────────────────────────────────────────────────
while True:
    clock.tick(FPS)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit(); sys.exit()

        elif event.type == pygame.KEYDOWN:
            # Tab switching
            if event.key == pygame.K_RIGHT and fr_mode == "list":
                tab = (tab + 1) % len(TABS)
            elif event.key == pygame.K_LEFT and fr_mode == "list":
                tab = (tab - 1) % len(TABS)
            elif event.key in (pygame.K_ESCAPE, pygame.K_b) and fr_mode == "list":
                pygame.quit(); sys.exit()

            # Friends tab
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
                            friends.pop(fr_cur)
                            save_friends(friends)
                            fr_cur = max(0, fr_cur - 1)
                elif fr_mode == "add":
                    if event.key == pygame.K_RETURN:
                        name = fr_input.strip()
                        if name and name not in friends:
                            friends.append(name)
                            save_friends(friends)
                        fr_mode = "list"
                    elif event.key == pygame.K_ESCAPE:
                        fr_mode = "list"
                    elif event.key == pygame.K_BACKSPACE:
                        fr_input = fr_input[:-1]
                    elif event.unicode and event.unicode.isprintable() and len(fr_input) < 24:
                        fr_input += event.unicode

            # Leaderboard tab
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
                    lb_entries = sc.get_all()  # refresh

    screen.fill(BG)
    draw_header()
    draw_tabs()
    if tab == 0:
        draw_friends()
    else:
        draw_leaderboard()
    pygame.display.flip()

pygame.quit()