#!/usr/bin/env python3
# rootfs/launcher/overlay.py -- Split-screen overlay (OS built-in)
from . import themes as th
import pygame

SCREEN_W, SCREEN_H = 640, 480
OVERLAY_W = 320
FPS       = 60
PAD       = 10
HEADER    = 28
FOOTER    = 28


def run(screen, clock, content_cb=None, title="Overlay"):
    """
    Overlay panel on the right half of the screen.
    content_cb(surface, rect) is called each frame to draw custom content
    into the panel area (e.g. a browser or notes view).
    """
    font_lg = pygame.font.SysFont("monospace", 13, bold=True)
    font_sm = pygame.font.SysFont("monospace", 10)
    pygame.key.set_repeat(400, 60)

    panel_x = SCREEN_W - OVERLAY_W
    content_rect = pygame.Rect(panel_x, HEADER, OVERLAY_W, SCREEN_H - HEADER - FOOTER)

    running = True
    while running:
        clock.tick(FPS)
        p = th.get()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif content_cb:
                    content_cb(screen, content_rect, event)

        # Semi-transparent panel background
        panel = pygame.Surface((OVERLAY_W, SCREEN_H), pygame.SRCALPHA)
        panel.fill((p["bg"][0], p["bg"][1], p["bg"][2], 230))
        screen.blit(panel, (panel_x, 0))

        # Left-edge separator
        pygame.draw.line(screen, p["border"], (panel_x, 0), (panel_x, SCREEN_H), 2)

        # Header
        pygame.draw.rect(screen, p["bar"], (panel_x, 0, OVERLAY_W, HEADER))
        ht = font_lg.render(title[:22], True, p["accent"])
        screen.blit(ht, (panel_x + PAD, (HEADER - ht.get_height()) // 2))

        # Content area
        if content_cb:
            content_cb(screen, content_rect, None)
        else:
            msg = font_sm.render("No content", True, p["dim"])
            screen.blit(msg, (panel_x + PAD, SCREEN_H // 2))

        # Footer
        pygame.draw.rect(screen, p["bar"], (panel_x, SCREEN_H - FOOTER, OVERLAY_W, FOOTER))
        cl = font_sm.render("Esc close", True, p["dim"])
        screen.blit(cl, (panel_x + PAD, SCREEN_H - FOOTER + (FOOTER - cl.get_height()) // 2))

        pygame.display.flip()

    pygame.key.set_repeat(400, 60)