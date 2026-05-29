#!/usr/bin/env python3
# rootfs/launcher/sleep_timer.py -- Sleep Timer (OS built-in)
import os, time
from pathlib import Path
from . import themes as th
import pygame

DATA_DIR    = Path(os.environ.get("MINTKIT_DATA", Path.home() / ".mintkit"))
CONFIG_FILE = DATA_DIR / "config.json"

DEFAULT_TIMEOUT = 5 * 60   # seconds
WARN_SECS       = 10        # countdown before sleep


class SleepTimer:
    """Drop this into the launcher loop to get automatic sleep."""

    def __init__(self):
        self._last_activity = time.monotonic()
        self._warned        = False
        self._warn_start    = 0.0

    def poke(self):
        """Call on any user input event to reset the idle timer."""
        self._last_activity = time.monotonic()
        self._warned        = False

    def idle_secs(self) -> float:
        return time.monotonic() - self._last_activity

    def timeout(self) -> int:
        try:
            import json
            cfg = json.loads(CONFIG_FILE.read_text())
            return int(cfg.get("sleep_timeout_secs", DEFAULT_TIMEOUT))
        except Exception:
            return DEFAULT_TIMEOUT

    def tick(self, screen, clock) -> bool:
        """
        Call once per frame. Returns True if the device should sleep now.
        Draws a countdown warning overlay when near timeout.
        """
        t = self.timeout()
        if t <= 0:
            return False
        idle = self.idle_secs()
        if idle >= t:
            return True                  # caller should shut down / sleep
        if idle >= t - WARN_SECS:
            if not self._warned:
                self._warned     = True
                self._warn_start = time.monotonic()
            secs_left = max(0, int(t - idle))
            self._draw_warning(screen, secs_left)
        return False

    @staticmethod
    def _draw_warning(screen, secs_left: int):
        p     = th.get()
        font  = pygame.font.SysFont("monospace", 18, bold=True)
        small = pygame.font.SysFont("monospace", 12)
        ov    = pygame.Surface((640, 480), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 160))
        screen.blit(ov, (0, 0))
        msg = font.render(f"Sleeping in {secs_left}s...", True, p["accent"])
        sub = small.render("Press any button to cancel", True, p["dim"])
        screen.blit(msg, (320 - msg.get_width() // 2, 210))
        screen.blit(sub, (320 - sub.get_width() // 2, 240))
        pygame.display.flip()