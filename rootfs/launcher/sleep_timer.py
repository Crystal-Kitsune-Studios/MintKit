#!/usr/bin/env python3
# rootfs/launcher/sleep_timer.py -- Sleep Timer (OS built-in)
"""Idle sleep for MintKit.

The Pi Zero 2 W has no suspend-to-RAM, so "sleep" here means: blank the
framebuffer, cut power to the HDMI panel, and idle at a low poll rate until
the user presses something. State is preserved and wake is instant.

Powering the device off on an idle timeout loses all state and costs a 15
second cold boot on a board with no RTC, which is why this module now sleeps
instead of asking the caller to shut down.

Public API:

    t = SleepTimer()
    t.poke()                       # call on any input event
    if t.tick(screen, clock):      # call once per frame
        t.sleep_and_wake(screen, clock)
"""
import os
import subprocess
import time
from pathlib import Path

from . import themes as th
import pygame

try:
    from . import screensaver as _saver
except Exception:
    # screensaver.py not deployed: degrade to plain sleep, never crash.
    _saver = None

DATA_DIR = Path(os.environ.get("MINTKIT_DATA", Path.home() / ".mintkit"))
CONFIG_FILE = DATA_DIR / "config.json"

DEFAULT_TIMEOUT = 5 * 60  # seconds. 0 or less disables sleep entirely.
WARN_SECS = 10            # countdown shown before sleeping
POLL_HZ = 8               # input poll rate while asleep
CONFIG_TTL = 5.0          # seconds to cache config.json for

# Analog axes and hats are deliberately excluded so a drifting stick cannot
# wake the device on its own.
WAKE_EVENTS = (pygame.KEYDOWN, pygame.JOYBUTTONDOWN, pygame.MOUSEBUTTONDOWN)

_FONT_CACHE = {}


def _font(size, bold=False):
    key = (size, bold)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = pygame.font.SysFont("monospace", size, bold=bold)
    return _FONT_CACHE[key]


def display_power(state):
    """Turn the HDMI panel on (1) or off (0). True if a method worked."""
    try:
        subprocess.run(
            ["vcgencmd", "display_power", str(int(state))],
            check=True,
            timeout=5,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        pass
    # KMS fallback. Only works if the dpms node is writable by this user.
    try:
        import glob

        for node in glob.glob("/sys/class/drm/card*-HDMI-A-*/dpms"):
            with open(node, "w") as fh:
                fh.write("on" if state else "off")
            return True
    except Exception:
        pass
    return False


def sleep_now(screen, clock=None):
    """Blank the panel and idle until the user presses something.

    Returns when woken. Does not shut anything down and does not lose state.
    """
    pygame.event.clear()
    try:
        screen.fill((0, 0, 0))
        pygame.display.flip()
    except Exception:
        pass

    powered_off = display_power(0)
    delay = max(1, int(1000 / POLL_HZ))

    try:
        while True:
            woke = False
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT or ev.type in WAKE_EVENTS:
                    woke = True
                    break
            if woke:
                break
            pygame.time.wait(delay)
    finally:
        if powered_off:
            display_power(1)
        pygame.event.clear()


class SleepTimer:
    """Drop this into the launcher loop to get automatic sleep."""

    def __init__(self):
        self._last_activity = time.monotonic()
        self._warned = False
        self._warn_start = 0.0
        self._cfg_timeout = DEFAULT_TIMEOUT
        self._cfg_read_at = -1e9

    def poke(self):
        """Call on any user input event to reset the idle timer."""
        self._last_activity = time.monotonic()
        self._warned = False

    def idle_secs(self) -> float:
        return time.monotonic() - self._last_activity

    def timeout(self) -> int:
        """Configured idle timeout in seconds, cached for CONFIG_TTL.

        tick() runs every frame, so reading and parsing config.json here
        uncached meant 60 SD card reads per second.
        """
        now = time.monotonic()
        if now - self._cfg_read_at < CONFIG_TTL:
            return self._cfg_timeout
        self._cfg_read_at = now
        try:
            import json

            cfg = json.loads(CONFIG_FILE.read_text())
            self._cfg_timeout = int(cfg.get("sleep_timeout_secs", DEFAULT_TIMEOUT))
        except Exception:
            self._cfg_timeout = DEFAULT_TIMEOUT
        return self._cfg_timeout

    def tick(self, screen, clock) -> bool:
        """Call once per frame. True means the device should sleep now.

        Draws a countdown warning overlay when near the timeout.
        """
        # Screen saver phase. Owns its own frames, so it must run
        # before anything else in the tick.
        if _saver is not None:
            _hooked = _saver.hook(self, screen, clock)
            if _hooked is not None:
                return _hooked
        t = self.timeout()
        if t <= 0:
            return False
        idle = self.idle_secs()
        if idle >= t:
            return True
        if idle >= t - WARN_SECS:
            if not self._warned:
                self._warned = True
                self._warn_start = time.monotonic()
            secs_left = max(0, int(t - idle))
            self._draw_warning(screen, secs_left)
        return False

    def sleep_and_wake(self, screen, clock=None) -> None:
        """Sleep, then reset the idle timer so we do not immediately re-sleep."""
        sleep_now(screen, clock)
        self.poke()

    @staticmethod
    def _draw_warning(screen, secs_left: int):
        try:
            p = th.get() or {}
        except Exception:
            p = {}
        accent = p.get("accent", (61, 204, 112))
        dim = p.get("dim", (90, 150, 105))

        w, h = screen.get_size()
        font = _font(18, bold=True)
        small = _font(12)

        ov = pygame.Surface((w, h), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 160))
        screen.blit(ov, (0, 0))

        msg = font.render("Sleeping in %ds..." % secs_left, True, accent)
        sub = small.render("Press any button to wake", True, dim)
        screen.blit(msg, (w // 2 - msg.get_width() // 2, h // 2 - 30))
        screen.blit(sub, (w // 2 - sub.get_width() // 2, h // 2))
        pygame.display.flip()
