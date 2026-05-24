#!/usr/bin/env python3
# rootfs/launcher/achievements_ui.py -- Achievement viewer (OS built-in)
from . import achievements as ach
from . import themes as th
import pygame

SCREEN_W, SCREEN_H = 640, 480
FPS    = 60
PAD    = 10
HEADER = 36
ROW_H  = 52
COLS   = 2
COL_W  = (SCREEN_W - PAD * 3) // COLS


def run(screen, clock):
    """Called by the launcher. Shows achievement viewer on the shared SDL screen."""
    font_lg = pygame.font.SysFont("monospace", 15, bold=True)
    font_sm = pygame.font.SysFont("monospace", 11)
    font_ic = pygame.font.SysFont("monospace", 22)

    all_ach = ach.get_all()
    all_ach.sort(key=lambda a: (not a["unlocked"], a["game"], a["id"]))
    unlocked_n, total_n = ach.count()

    content_h  = (((len(all_ach) + 1) // COLS) + 1) * ROW_H
    max_scroll = max(0, content_h - (SCREEN_H - HEADER - PAD))
    scroll     = 0

    running = True
    while running:
        clock.tick(FPS)
        p = th.get()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_b):
                    running = False
                elif event.key == pygame.K_DOWN:
                    scroll = min(scroll + ROW_H, max_scroll)
                elif event.key == pygame.K_UP:
                    scroll = max(scroll - ROW_H, 0)
                elif event.key == pygame.K_PAGEDOWN:
                    scroll = min(scroll + SCREEN_H, max_scroll)
                elif event.key == pygame.K_PAGEUP:
                    scroll = max(scroll - SCREEN_H, 0)

        screen.fill(p["bg"])

        # Header
        pygame.draw.rect(screen, p["bar"], (0, 0, SCREEN_W, HEADER))
        pygame.draw.line(screen, p["border"], (0, HEADER), (SCREEN_W, HEADER))
        title = font_lg.render(f"Achievements  —  {unlocked_n} / {total_n}", True, p["accent"])
        screen.blit(title, (PAD, (HEADER - title.get_height()) // 2))
        hint = font_sm.render("↑↓ scroll   Esc back", True, p["dim"])
        screen.blit(hint, (SCREEN_W - hint.get_width() - PAD, (HEADER - hint.get_height()) // 2))

        # Achievement cards
        y_base = HEADER + PAD - scroll
        for i, a in enumerate(all_ach):
            col = i % COLS
            row = i // COLS
            x = PAD + col * (COL_W + PAD)
            y = y_base + row * ROW_H
            if y + ROW_H < HEADER or y > SCREEN_H:
                continue
            unlocked   = a["unlocked"]
            card_col   = p["card"] if unlocked else (8, 18, 12)
            border_col = p["accent"] if unlocked else p["locked"]
            text_col   = p["white"] if unlocked else p["locked"]
            pygame.draw.rect(screen, card_col,  (x, y, COL_W, ROW_H - 4), border_radius=4)
            pygame.draw.rect(screen, border_col,(x, y, COL_W, ROW_H - 4), 1, border_radius=4)
            ic_surf = font_ic.render(a["icon"], True, (240, 200, 60) if unlocked else p["locked"])
            screen.blit(ic_surf, (x + 6, y + (ROW_H - 4 - ic_surf.get_height()) // 2))
            name_surf = font_lg.render(a["name"], True, p["accent"] if unlocked else p["locked"])
            desc_surf = font_sm.render(a["desc"][:38] + ("…" if len(a["desc"]) > 38 else ""), True, text_col)
            screen.blit(name_surf, (x + 38, y + 6))
            screen.blit(desc_surf, (x + 38, y + 24))
            if unlocked and a["unlocked_at"]:
                date_surf = font_sm.render(a["unlocked_at"][:10], True, p["dim"])
                screen.blit(date_surf, (x + COL_W - date_surf.get_width() - 6, y + 6))

        pygame.display.flip()

    pygame.key.set_repeat(400, 60)  # restore launcher repeat