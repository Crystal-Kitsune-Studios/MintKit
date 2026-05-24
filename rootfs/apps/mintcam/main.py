#!/usr/bin/env python3
# rootfs/apps/mintcam/main.py -- MintCam v1.0
import os, sys, time, datetime
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
FOOTER = 34

DATA_DIR   = Path(os.environ.get("MINTKIT_DATA", Path.home() / ".mintkit"))
PHOTO_DIR  = DATA_DIR / "photos"
VIDEO_DIR  = DATA_DIR / "videos"

PHOTO_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

# Try to import picamera2 (Raspberry Pi camera)
try:
    from picamera2 import Picamera2
    cam = Picamera2()
    cam.configure(cam.create_preview_configuration(
        main={"size": (SCREEN_W, SCREEN_H - HEADER - FOOTER)}))
    cam.start()
    HAS_CAM = True
except Exception:
    HAS_CAM = False
    cam = None

pygame.init()
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("MintCam")
clock  = pygame.font.SysFont("monospace", 15, bold=True)
clock  = pygame.time.Clock()
font_lg = pygame.font.SysFont("monospace", 15, bold=True)
font_sm = pygame.font.SysFont("monospace", 11)
pygame.key.set_repeat(400, 60)

MODE_PHOTO = "photo"
MODE_VIDEO = "video"
mode       = MODE_PHOTO
recording  = False
flash_frames = 0

def stamp():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

def capture_photo():
    global flash_frames
    if not HAS_CAM:
        return
    path = str(PHOTO_DIR / f"photo_{stamp()}.jpg")
    cam.capture_file(path)
    flash_frames = 6

def draw():
    p = th.get()
    screen.fill(p["bg"])
    # Viewfinder
    vf_rect = pygame.Rect(0, HEADER, SCREEN_W, SCREEN_H - HEADER - FOOTER)
    if HAS_CAM:
        try:
            frame = cam.capture_array()
            surf  = pygame.surfarray.make_surface(frame.swapaxes(0, 1))
            screen.blit(surf, (0, HEADER))
        except Exception:
            pygame.draw.rect(screen, (20, 20, 20), vf_rect)
            no_cam = font_lg.render("Camera error", True, p["dim"])
            screen.blit(no_cam, (SCREEN_W // 2 - no_cam.get_width() // 2, SCREEN_H // 2))
    else:
        pygame.draw.rect(screen, (10, 10, 10), vf_rect)
        msg = font_lg.render("No camera module detected", True, p["dim"])
        sub = font_sm.render("Install Raspberry Pi Camera Module 3", True, p["dim"])
        screen.blit(msg, (SCREEN_W // 2 - msg.get_width() // 2, SCREEN_H // 2 - 16))
        screen.blit(sub, (SCREEN_W // 2 - sub.get_width() // 2, SCREEN_H // 2 + 8))
    # Flash overlay
    if flash_frames > 0:
        fl = pygame.Surface((SCREEN_W, SCREEN_H))
        fl.set_alpha(min(200, flash_frames * 40))
        fl.fill((255, 255, 255))
        screen.blit(fl, (0, 0))
    # Header
    pygame.draw.rect(screen, p["bar"], (0, 0, SCREEN_W, HEADER))
    pygame.draw.line(screen, p["border"], (0, HEADER), (SCREEN_W, HEADER))
    mode_t = font_lg.render(f"{'📷 PHOTO' if mode == MODE_PHOTO else '🔴 VIDEO'}", True, p["accent"])
    screen.blit(mode_t, (PAD, (HEADER - mode_t.get_height()) // 2))
    if recording:
        rec_t = font_sm.render("● REC", True, (220, 60, 60))
        screen.blit(rec_t, (SCREEN_W - rec_t.get_width() - PAD, (HEADER - rec_t.get_height()) // 2))
    # Footer
    pygame.draw.line(screen, p["border"], (0, SCREEN_H - FOOTER), (SCREEN_W, SCREEN_H - FOOTER))
    hints = [("Z", "SHOOT"), ("M", "MODE"), ("Esc", "QUIT")]
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
    if flash_frames > 0:
        flash_frames -= 1
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_z):
                if mode == MODE_PHOTO:
                    capture_photo()
            elif event.key == pygame.K_m:
                mode = MODE_VIDEO if mode == MODE_PHOTO else MODE_PHOTO
            elif event.key in (pygame.K_ESCAPE, pygame.K_b):
                running = False
    draw()
    pygame.display.flip()

if cam: cam.stop()
pygame.quit()