#!/usr/bin/env python3
# rootfs/launcher/screenshot.py -- Screenshot & clip capture
import pygame, os, datetime
from pathlib import Path

SCREENSHOT_DIR = Path("/home/mintkit/.mintkit/screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

# Ring buffer for clip capture (last N frames)
MAX_CLIP_FRAMES = 30 * 30  # 30 s @ 30 fps
_frame_buffer: list[pygame.Surface] = []

def push_frame(surface: pygame.Surface):
    """Call once per frame from the main loop to keep the clip buffer fresh."""
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