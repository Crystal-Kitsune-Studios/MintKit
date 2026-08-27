#!/usr/bin/env python3
# rootfs/launcher/screenshot.py -- Screenshot & clip capture
import pygame, os, datetime
from pathlib import Path

SCREENSHOT_DIR = Path("/home/mintkit/.mintkit/screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

# Ring buffer for clip capture (last N frames at 15fps effective)
# push_frame throttles to every 4th frame (15fps).
#
# MEMORY MATH, corrected. Pi Zero 2W has 512MB of SoC RAM and only ~357MB is
# visible to Linux once gpu_mem=128 is taken. The panel is 800x480, not 640x480,
# and pygame surfaces here are 32bpp, so every surface.copy() costs
#     800 * 480 * 4 = 1,536,000 bytes = 1.46 MB
# The old value of 15 * 30 = 450 frames meant the deque could not start
# evicting until it held 450 * 1.46 MB = 658 MB, which is larger than the
# entire machine. The cap was therefore unreachable, the process paged out to
# the SD card, and the OOM killer took it at ~186MB anon RSS.
#     30 frames * 1.46 MB = ~44 MB, which the Pi can actually hold.
#
# TODO: for genuinely long clips, buffer downscaled RGB565 bytes instead of
# full Surfaces. 400x240x2 = 192 KB/frame, so 50 frames is ~9.6 MB, which is
# what the original 9MB comment was reaching for.
MAX_CLIP_FRAMES = 30  # ~2 s @ 15 fps; 30 * 1.46 MB = ~44 MB at 800x480
_frame_buffer: list[pygame.Surface] = []
_pf_counter = 0

def push_frame(surface: pygame.Surface):
    """Call once per frame from the main loop to keep the clip buffer fresh.
    Throttled to every 4th frame (15fps) to prevent OOM on Pi Zero 2W.
    """
    global _pf_counter
    _pf_counter += 1
    if _pf_counter % 4 != 0:
        return
    _frame_buffer.append(surface.copy())
    if len(_frame_buffer) > MAX_CLIP_FRAMES:
        _frame_buffer.pop(0)

def save_screenshot(surface: pygame.Surface) -> Path:
    """Save current frame as PNG. Returns the saved path."""
    ts  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = SCREENSHOT_DIR / f"screenshot_{ts}.png"
    pygame.image.save(surface, str(out))
    return out

def save_clip(fps: int = 30) -> Path | None:
    """Save buffered frames as GIF. Returns path or None if Pillow missing."""
    try:
        from PIL import Image
    except ImportError:
        return None
    if not _frame_buffer:
        return None
    ts     = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out    = SCREENSHOT_DIR / f"clip_{ts}.gif"
    frames = []
    for surf in _frame_buffer:
        raw  = pygame.image.tostring(surf, "RGB")
        img  = Image.frombytes("RGB", surf.get_size(), raw)
        frames.append(img.convert("P", palette=Image.ADAPTIVE, colors=256))
    frames[0].save(
        str(out), save_all=True, append_images=frames[1:],
        loop=0, duration=int(1000 / fps), optimize=False
    )
    return out