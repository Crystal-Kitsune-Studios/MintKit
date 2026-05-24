#!/usr/bin/env python3
# rootfs/apps/mintachievements/main.py -- Achievement viewer v1.0
import os, sys, platform
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "launcher"))
import achievements as ach

IS_LINUX = platform.system() == "Linux"
if IS_LINUX:
    os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")
    os.environ.setdefault("SDL_AUDIODRIVER", "alsa")

import pygame

# ── Theme ────────────────────────────────────────────────────────────────
SCREEN_W, SCREEN_H = 640, 480
FPS     = 60
BG      = (10,  26,  16)
CARD    = (13,  32,  20)
ACCENT  = (61, 204, 112)
DIM     = (50, 130,  75)
WHITE   = (180, 240, 195)
LOCKED  = (50,  70,  55)
BAR     = ( 6,  13,   8)
BORDER  = (29, 100,  55)
GOLD    = (240, 200,  60)

PAD     = 10
HEADER  = 36
ROW_H   = 52
COLS    = 2
COL_W   = (SCREEN_W - PAD * 3) // COLS

pygame.init()
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("Achievements")
clock  = pygame.time.Clock()
font_lg = pygame.font.SysFont("monospace", 15, bold=True)
font_sm = pygame.font.SysFont("monospace", 11)
font_ic = pygame.font.SysFont("monospace", 22)

# Group achievements by game
all_ach   = ach.get_all()
unlocked_n, total_n = ach.count()

# Build flat list for display (sorted: unlocked first, then by game)
all_ach.sort(key=lambda a: (not a["unlocked"], a["game"], a["id"]))

scroll = 0   # pixel scroll offset

# Calculate total content height
ROWS_PER_PAGE = (SCREEN_H - HEADER - PAD) // ROW_H

def draw():
    screen.fill(BG)

    # Header
    pygame.draw.rect(screen, BAR, (0, 0, SCREEN_W, HEADER))
    pygame.draw.line(screen, BORDER, (0, HEADER), (SCREEN_W, HEADER))
    title = font_lg.render(f"Achievements  —  {unlocked_n} / {total_n}", True, ACCENT)
    screen.blit(title, (PAD, (HEADER - title.get_height()) // 2))
    hint = font_sm.render("\u2191\u2193 scroll   B back", True, DIM)
    screen.blit(hint, (SCREEN_W - hint.get_width() - PAD, (HEADER - hint.get_height()) // 2))

    # Achievement cards
    y_base = HEADER + PAD - scroll
    for i, a in enumerate(all_ach):
        col = i % COLS
        row = i // COLS
        x = PAD + col * (COL_W + PAD)
        y = y_base + row * ROW_H

        if y + ROW_H < HEADER or y > SCREEN_H:
            continue  # off-screen

        unlocked = a["unlocked"]
        card_col  = CARD if unlocked else (8, 18, 12)
        border_col = ACCENT if unlocked else LOCKED
        text_col   = WHITE if unlocked else LOCKED

        pygame.draw.rect(screen, card_col,  (x, y, COL_W, ROW_H - 4), border_radius=4)
        pygame.draw.rect(screen, border_col,(x, y, COL_W, ROW_H - 4), 1, border_radius=4)

        # Icon
        ic_surf = font_ic.render(a["icon"], True, GOLD if unlocked else LOCKED)
        screen.blit(ic_surf, (x + 6, y + (ROW_H - 4 - ic_surf.get_height()) // 2))

        # Name + desc
        name_surf = font_lg.render(a["name"], True, ACCENT if unlocked else LOCKED)
        desc_surf = font_sm.render(a["desc"][:38] + ("…" if len(a["desc"]) > 38 else ""), True, text_col)
        tx = x + 38
        screen.blit(name_surf, (tx, y + 6))
        screen.blit(desc_surf, (tx, y + 24))

        # Unlock date
        if unlocked and a["unlocked_at"]:
            date_surf = font_sm.render(a["unlocked_at"][:10], True, DIM)
            screen.blit(date_surf, (x + COL_W - date_surf.get_width() - 6, y + 6))

    pygame.display.flip()

# ── Main loop ────────────────────────────────────────────────────────────────
content_h = (((len(all_ach) + 1) // COLS) + 1) * ROW_H
max_scroll = max(0, content_h - (SCREEN_H - HEADER - PAD))

while True:
    clock.tick(FPS)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit(); sys.exit()
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_b):
                pygame.quit(); sys.exit()
            elif event.key == pygame.K_DOWN:
                scroll = min(scroll + ROW_H, max_scroll)
            elif event.key == pygame.K_UP:
                scroll = max(scroll - ROW_H, 0)
            elif event.key == pygame.K_PAGEDOWN:
                scroll = min(scroll + SCREEN_H, max_scroll)
            elif event.key == pygame.K_PAGEUP:
                scroll = max(scroll - SCREEN_H, 0)
    draw()