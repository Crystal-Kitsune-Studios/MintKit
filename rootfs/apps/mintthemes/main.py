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

pygame.init()
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("Themes")
clock  = pygame.time.Clock()
font_lg = pygame.font.SysFont("monospace", 15, bold=True)
font_sm = pygame.font.SysFont("monospace", 11)
pygame.key.set_repeat(400, 60)

all_themes = th.list_themes()   # [(id, dict), ...]
cur        = next((i for i, (tid, _) in enumerate(all_themes)
                   if tid == th.get_active_id()), 0)
preview_t  = th.get()           # live preview palette

def t(): return preview_t      # shorthand

def draw():
    screen.fill(t()["bg"])

    # Header
    pygame.draw.rect(screen, t()["bar"], (0, 0, SCREEN_W, HEADER))
    pygame.draw.line(screen, t()["border"], (0, HEADER), (SCREEN_W, HEADER))
    hdr = font_lg.render("Theme Picker", True, t()["accent"])
    screen.blit(hdr, (PAD, (HEADER - hdr.get_height()) // 2))
    hint = font_sm.render("Z apply  Esc back", True, t()["dim"])
    screen.blit(hint, (SCREEN_W - hint.get_width() - PAD,
                        (HEADER - hint.get_height()) // 2))

    # Theme rows
    for i, (tid, td) in enumerate(all_themes):
        y   = HEADER + PAD + i * ROW_H
        sel = (i == cur)
        active = (tid == th.get_active_id())
        bg  = (t()["card"][0]+8, t()["card"][1]+12, t()["card"][2]+8) if sel else t()["card"]
        pygame.draw.rect(screen, bg, (PAD, y, SCREEN_W - PAD * 2, ROW_H - 4),
                         border_radius=5)
        if sel:
            pygame.draw.rect(screen, t()["accent"],
                             (PAD, y, SCREEN_W - PAD * 2, ROW_H - 4), 1, border_radius=5)

        # Color swatch
        sw_x = PAD + 10
        swatch_colors = [td["accent"], td["dim"], td["border"], td["card"]]
        for si, sc in enumerate(swatch_colors):
            pygame.draw.rect(screen, sc, (sw_x + si * 18, y + 10, 16, 16), border_radius=3)
        # Large preview dot
        pygame.draw.circle(screen, td["preview"], (sw_x + 8, y + ROW_H - 18), 6)

        # Name
        name_surf = font_lg.render(td["name"], True,
                                    t()["accent"] if sel else t()["white"])
        screen.blit(name_surf, (PAD + 90, y + 10))

        # Active badge
        if active:
            badge = font_sm.render("ACTIVE", True, t()["black"])
            bw = badge.get_width() + 10
            pygame.draw.rect(screen, t()["accent"],
                             (SCREEN_W - PAD * 2 - bw, y + 12, bw, 16), border_radius=3)
            screen.blit(badge, (SCREEN_W - PAD * 2 - bw + 5, y + 14))

        # BG/accent preview mini-strip
        strip_y = y + 30
        pygame.draw.rect(screen, td["bg"],    (PAD + 90, strip_y, 30, 10), border_radius=2)
        pygame.draw.rect(screen, td["accent"],(PAD + 90, strip_y, 30, 10), 1, border_radius=2)
        pygame.draw.rect(screen, td["bar"],   (PAD + 124, strip_y, 20, 10), border_radius=2)

    # Bottom hint bar
    pygame.draw.line(screen, t()["border"], (0, SCREEN_H - 34), (SCREEN_W, SCREEN_H - 34))
    hx = 6
    for key, act in [("↑↓", "SELECT"), ("Z", "APPLY"), ("Esc", "BACK")]:
        ki = font_sm.render(key, True, t()["black"])
        kw = ki.get_width() + 8
        pygame.draw.rect(screen, t()["accent"], (hx, SCREEN_H - 26, kw, 18))
        screen.blit(ki, (hx + 4, SCREEN_H - 24)); hx += kw + 4
        ai = font_sm.render(act, True, t()["dim"])
        screen.blit(ai, (hx, SCREEN_H - 24)); hx += ai.get_width() + 12

while True:
    clock.tick(FPS)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit(); sys.exit()
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                cur = (cur - 1) % len(all_themes)
                preview_t = all_themes[cur][1]  # live preview
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                cur = (cur + 1) % len(all_themes)
                preview_t = all_themes[cur][1]  # live preview
            elif event.key in (pygame.K_RETURN, pygame.K_z):
                th.set_theme(all_themes[cur][0])
                preview_t = all_themes[cur][1]
            elif event.key in (pygame.K_ESCAPE, pygame.K_b):
                pygame.quit(); sys.exit()

    draw()
    pygame.display.flip()

pygame.quit()