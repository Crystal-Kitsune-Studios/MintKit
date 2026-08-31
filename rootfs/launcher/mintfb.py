"""Shared PocketMint pygame to /dev/fb0 RGB565 bridge."""

import sys

if sys.platform == "linux":
    import pygame
    import numpy as np
    from pathlib import Path

    def _framebuffer_size():
        try:
            raw = Path(
                "/sys/class/graphics/fb0/virtual_size"
            ).read_text().strip()
            width, height = raw.split(",", 1)
            return int(width), int(height)
        except Exception:
            return 800, 480

    FB_W, FB_H = _framebuffer_size()
    _fb0 = open("/dev/fb0", "wb", buffering=0)
    _canvas = None

    def _fit_to_framebuffer(surface):
        global _canvas

        if surface.get_size() == (FB_W, FB_H):
            return surface

        src_w, src_h = surface.get_size()
        scale = min(FB_W / src_w, FB_H / src_h)
        dst_w = max(1, int(src_w * scale))
        dst_h = max(1, int(src_h * scale))

        if _canvas is None:
            _canvas = pygame.Surface((FB_W, FB_H))

        _canvas.fill((0, 0, 0))

        if (dst_w, dst_h) == (src_w, src_h):
            scaled = surface
        else:
            scaled = pygame.transform.scale(
                surface, (dst_w, dst_h)
            )

        _canvas.blit(
            scaled,
            ((FB_W - dst_w) // 2, (FB_H - dst_h) // 2),
        )
        return _canvas

    def flip(*_args, **_kwargs):
        surface = pygame.display.get_surface()
        if surface is None:
            return

        frame = _fit_to_framebuffer(surface)
        pixels = (
            pygame.surfarray.array3d(frame)
            .transpose(1, 0, 2)
            .astype(np.uint16)
        )

        rgb565 = (
            ((pixels[:, :, 0] & 0xF8) << 8)
            | ((pixels[:, :, 1] & 0xFC) << 3)
            | (pixels[:, :, 2] >> 3)
        )

        _fb0.seek(0)
        _fb0.write(rgb565.astype("<u2").tobytes())

    pygame.display.flip = flip
    pygame.display.update = flip
