#!/usr/bin/env python3
# rootfs/launcher/screenshot.py -- Screenshot & clip capture
import pygame, os, datetime
from pathlib import Path

SCREENSHOT_DIR = Path("/home/mintkit/.mintkit/screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

# Ring buffer for clip capture (last N frames at 15fps effective)
# IMPORTANT: push_frame throttles to every 4th frame (15fps) to prevent OOM.
# At 60fps, surface.copy() at 640x480 = ~1.2MB/frame. Without throttling,
# GC can't free old surfaces fast enough -> 72MB/s allocation -> OOM in ~30s.
# 15fps * 30 frames = 9MB max buffer, safe on Pi Zero 2W.
MAX_CLIP_FRAMES = 15 * 30  # 30 s @ 15 fps
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