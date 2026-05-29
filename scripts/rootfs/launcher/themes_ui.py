#!/usr/bin/env python3
# rootfs/apps/mintthemes/main.py -- Theme Picker v1.0
import os, sys, platform
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "launcher"))
import themes as th

IS_LINUX = platform.system() == "Linux"
if IS_LINUX:
    os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")
    os.environ.setdefault("SDL_AUDIODRIVER", "alsa")

import pygame

SCREEN_W, SCREEN_H = 640, 480
FPS    = 60
PAD    = 12
HEADER = 36
ROW_H  = 62


def run(screen, clock):
    """Called by the launcher. Shows theme picker on the shared SDL screen."""
    font_lg = pygame.font.SysFont("monospace", 15, bold=True)
    font_sm = pygame.font.SysFont("monospace", 11)
    pygame.key.set_repeat(400, 60)

    all_themes = th.list_themes()
    cur        = [next((i for i, (tid, _) in enumerate(all_themes)
                        if tid == th.get_active_id()), 0)]
    preview_t  = [all_themes[cur[0]][1]]

    def p(): return preview_t[0]

    running = True
    while running:
        clock.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_w):
                    cur[0] = (cur[0] - 1) % len(all_themes)
                    preview_t[0] = all_themes[cur[0]][1]
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    cur[0] = (cur[0] + 1) % len(all_themes)
                    preview_t[0] = all_themes[cur[0]][1]
                elif event.key in (pygame.K_RETURN, pygame.K_z):
                    th.set_theme(all_themes[cur[0]][0])
                    preview_t[0] = all_themes[cur[0]][1]
                elif event.key in (pygame.K_ESCAPE, pygame.K_b):
                    running = False

        screen.fill(p()["bg"])

        # Header
        pygame.draw.rect(screen, p()["bar"], (0, 0, SCREEN_W, HEADER))
        pygame.draw.line(screen, p()["border"], (0, HEADER), (SCREEN_W, HEADER))
        hdr = font_lg.render("Theme Picker", True, p()["accent"])
        screen.blit(hdr, (PAD, (HEADER - hdr.get_height()) // 2))
        hint = font_sm.render("Z apply  Esc back", True, p()["dim"])
        screen.blit(hint, (SCREEN_W - hint.get_width() - PAD,
                            (HEADER - hint.get_height()) // 2))

        # Theme rows
        for i, (tid, td) in enumerate(all_themes):
            y   = HEADER + PAD + i * ROW_H
            sel = (i == cur[0])
            active = (tid == th.get_active_id())
            bg  = tuple(min(255, c + 10) for c in p()["card"]) if sel else p()["card"]
            pygame.draw.rect(screen, bg, (PAD, y, SCREEN_W - PAD * 2, ROW_H - 4), border_radius=5)
            if sel:
                pygame.draw.rect(screen, p()["accent"],
                                 (PAD, y, SCREEN_W - PAD * 2, ROW_H - 4), 1, border_radius=5)

            sw_x = PAD + 10
            swatch_colors = [td["accent"], td["dim"], td["border"], td["card"]]
            for si, sc in enumerate(swatch_colors):
                pygame.draw.rect(screen, sc, (sw_x + si * 18, y + 10, 16, 16), border_radius=3)
            pygame.draw.circle(screen, td["preview"], (sw_x + 8, y + ROW_H - 18), 6)

            name_surf = font_lg.render(td["name"], True,
                                        p()["accent"] if sel else p()["white"])
            screen.blit(name_surf, (PAD + 90, y + 10))

            if active:
                badge = font_sm.render("ACTIVE", True, p()["black"])
                bw = badge.get_width() + 10
                pygame.draw.rect(screen, p()["accent"],
                                 (SCREEN_W - PAD * 2 - bw, y + 12, bw, 16), border_radius=3)
                screen.blit(badge, (SCREEN_W - PAD * 2 - bw + 5, y + 14))

            strip_y = y + 30
            pygame.draw.rect(screen, td["bg"],    (PAD + 90, strip_y, 30, 10), border_radius=2)
            pygame.draw.rect(screen, td["accent"],(PAD + 90, strip_y, 30, 10), 1, border_radius=2)
            pygame.draw.rect(screen, td["bar"],   (PAD + 124, strip_y, 20, 10), border_radius=2)

        # Bottom hint bar
        pygame.draw.line(screen, p()["border"], (0, SCREEN_H - 34), (SCREEN_W, SCREEN_H - 34))
        hx = 6
        for key, act in [("↑↓", "SELECT"), ("Z", "APPLY"), ("Esc", "BACK")]:
            ki = font_sm.render(key, True, p()["black"])
            kw = ki.get_width() + 8
            pygame.draw.rect(screen, p()["accent"], (hx, SCREEN_H - 26, kw, 18))
            screen.blit(ki, (hx + 4, SCREEN_H - 24)); hx += kw + 4
            ai = font_sm.render(act, True, p()["dim"])
            screen.blit(ai, (hx, SCREEN_H - 24)); hx += ai.get_width() + 12

        pygame.display.flip()

    pygame.key.set_repeat(400, 60)  # restore launcher repeat