"""MintKit screen saver.

Runs after a period of idle, before the sleep timer blanks the panel.

Design constraints, all of them load bearing on a Pi Zero 2 W:

  * 357 MB visible RAM and MemoryMax=300M on mintkit.service, so every
    surface is allocated once in __init__ and never inside draw().
  * pygame.display.flip is overridden by mintos.py to pack the surface into
    RGB565 and write /dev/fb0, so all we may do is fill/blit then flip.
  * 30 fps, not 60. Nothing here is worth the extra frames.
  * Nothing here may raise. A screen saver that crashes takes the launcher
    down with it, and a crash loop on a handheld is unrecoverable without
    pulling the card.

This module blocks while it runs. It owns its own frames. That is deliberate:
mintos.py ticks the sleep timer at the top of the frame and then paints the
active app over the top, so anything drawn from inside tick() is discarded.
Owning the loop also means sleep_timer.py needs no rework beyond a two line
hook, and mintos.py needs no change at all.

Config, in ~/.mintkit/config.json:

  "screensaver_secs": 90        idle seconds before it starts, 0 disables
  "screensaver_mode": "bounce"  bounce | starfield | clock | rain | off

screensaver_secs must be smaller than sleep_timeout_secs or the device sleeps
before the saver is ever seen. Setting sleep_timeout_secs to 0 and
screensaver_secs to something small gives a saver that runs forever and never
sleeps, which is the right setting on a desk with a charger.
"""
import json
import math
import os
import random
import time
from pathlib import Path

import pygame

try:
    from . import themes as th
except Exception:
    th = None

try:
    from . import battery as _bat
except Exception:
    _bat = None

DATA_DIR = Path(os.environ.get("MINTKIT_DATA", Path.home() / ".mintkit"))
CONFIG_FILE = DATA_DIR / "config.json"

FPS = 30
WARN_SECS = 10                # countdown shown before sleep takes over
CONFIG_TTL = 5.0              # seconds to cache config.json for
DEFAULT_SAVER_SECS = 90
DEFAULT_MODE = "bounce"
OFF_NAMES = ("", "off", "none", "blank", "disabled")

_FALLBACK = {
    "bg": (10, 26, 16),
    "accent": (61, 204, 112),
    "text": (180, 240, 195),
    "dim": (90, 150, 105),
    "gold": (240, 200, 60),
}

_FONT_CACHE = {}


def _font(size, bold=False):
    """Cached font. Two SysFont calls per frame is a real cost at 800x480."""
    key = (int(size), bool(bold))
    hit = _FONT_CACHE.get(key)
    if hit is not None:
        return hit
    try:
        if not pygame.font.get_init():
            pygame.font.init()
    except Exception:
        pass
    try:
        f = pygame.font.SysFont("monospace", int(size), bold=bool(bold))
    except Exception:
        f = pygame.font.Font(None, int(size))
    _FONT_CACHE[key] = f
    return f


def _palette():
    """Theme colours, with every key validated. A partial theme must not
    KeyError three frames into a saver nobody is watching."""
    col = dict(_FALLBACK)
    if th is None:
        return col
    try:
        pal = th.get()
    except Exception:
        return col
    if not isinstance(pal, dict):
        return col
    for key in _FALLBACK:
        val = pal.get(key)
        if isinstance(val, (tuple, list)) and len(val) >= 3:
            col[key] = tuple(int(c) for c in val[:3])
    return col


# --------------------------------------------------------------------------
# modes
# --------------------------------------------------------------------------
class Bounce:
    """The DVD logo. Non negotiable."""

    WORDMARK = "POCKETMINT"
    SPEED = 92.0

    def __init__(self, w, h, col):
        self.w, self.h, self.col = w, h, col
        big = _font(46, bold=True)
        self.variants = [
            big.render(self.WORDMARK, True, col[k])
            for k in ("accent", "text", "gold", "dim")
        ]
        self.idx = 0
        self.img = self.variants[0]
        self.iw = self.img.get_width()
        self.ih = self.img.get_height()
        self.x = (w - self.iw) / 2.0
        self.y = (h - self.ih) / 2.0
        self.vx = self.SPEED
        self.vy = self.SPEED * 0.62
        self.corners = 0
        self.small = _font(16)
        self.label = self.small.render("corner hits: 0", True, col["dim"])

    def step(self, dt):
        hit_x = hit_y = False
        self.x += self.vx * dt
        self.y += self.vy * dt
        if self.x <= 0:
            self.x = 0.0
            self.vx = abs(self.vx)
            hit_x = True
        elif self.x + self.iw >= self.w:
            self.x = float(self.w - self.iw)
            self.vx = -abs(self.vx)
            hit_x = True
        if self.y <= 0:
            self.y = 0.0
            self.vy = abs(self.vy)
            hit_y = True
        elif self.y + self.ih >= self.h:
            self.y = float(self.h - self.ih)
            self.vy = -abs(self.vy)
            hit_y = True
        if hit_x or hit_y:
            self.idx = (self.idx + 1) % len(self.variants)
            self.img = self.variants[self.idx]
        if hit_x and hit_y:
            self.corners += 1
            self.label = self.small.render(
                "corner hits: %d" % self.corners, True, self.col["dim"]
            )

    def draw(self, screen):
        screen.fill(self.col["bg"])
        screen.blit(self.img, (int(self.x), int(self.y)))
        screen.blit(self.label, (10, self.h - 26))


class Starfield:
    """Cheapest mode. Rect fills only, no blits, no text, no allocation."""

    COUNT = 110
    SPEED = 0.55

    def __init__(self, w, h, col):
        self.w, self.h, self.col = w, h, col
        self.cx = w / 2.0
        self.cy = h / 2.0
        self.shades = (col["dim"], col["text"], col["accent"])
        self.stars = [
            [random.uniform(-1.0, 1.0), random.uniform(-1.0, 1.0),
             random.uniform(0.08, 1.0)]
            for _ in range(self.COUNT)
        ]

    def step(self, dt):
        for s in self.stars:
            s[2] -= self.SPEED * dt
            if s[2] <= 0.05:
                s[0] = random.uniform(-1.0, 1.0)
                s[1] = random.uniform(-1.0, 1.0)
                s[2] = 1.0

    def draw(self, screen):
        screen.fill(self.col["bg"])
        for s in self.stars:
            z = s[2]
            x = int(self.cx + s[0] / z * self.cx)
            y = int(self.cy + s[1] / z * self.cy)
            if 0 <= x < self.w and 0 <= y < self.h:
                if z > 0.6:
                    size, shade = 1, self.shades[0]
                elif z > 0.3:
                    size, shade = 2, self.shades[1]
                else:
                    size, shade = 3, self.shades[2]
                screen.fill(shade, (x, y, size, size))


class ClockSaver:
    """Big drifting clock. Useful, since the Pi Zero has no RTC and this is
    the only place the time is ever large enough to read across a room."""

    DRIFT = 26.0
    BAT_TTL = 30.0

    def __init__(self, w, h, col):
        self.w, self.h, self.col = w, h, col
        self.big = _font(96, bold=True)
        self.mid = _font(26)
        self.t = 0.0
        self._stamp = None
        self._time_img = None
        self._date_img = None
        self._bat_img = None
        self._bat_at = -1e9
        self._refresh()
        self._poll_battery()

    def _refresh(self):
        now = time.localtime()
        stamp = (now.tm_hour, now.tm_min)
        if stamp == self._stamp and self._time_img is not None:
            return
        self._stamp = stamp
        try:
            self._time_img = self.big.render(
                time.strftime("%H:%M", now), True, self.col["accent"]
            )
            self._date_img = self.mid.render(
                time.strftime("%a %d %b", now), True, self.col["dim"]
            )
        except Exception:
            self._time_img = None
            self._date_img = None

    def _poll_battery(self):
        now = time.monotonic()
        if now - self._bat_at < self.BAT_TTL:
            return
        self._bat_at = now
        if _bat is None:
            self._bat_img = None
            return
        try:
            info = _bat.get()
            if not info:
                self._bat_img = None
                return
            self._bat_img = self.mid.render(
                "%d%%" % int(info.get("pct", 0)), True, self.col["dim"]
            )
        except Exception:
            self._bat_img = None

    def step(self, dt):
        self.t += dt
        self._refresh()
        self._poll_battery()

    def draw(self, screen):
        screen.fill(self.col["bg"])
        ox = math.sin(self.t * 0.35) * self.DRIFT
        oy = math.sin(self.t * 0.21) * self.DRIFT * 0.5
        if self._time_img is not None:
            screen.blit(
                self._time_img,
                (int(self.w / 2 - self._time_img.get_width() / 2 + ox),
                 int(self.h / 2 - self._time_img.get_height() / 2 + oy)),
            )
        if self._date_img is not None:
            screen.blit(
                self._date_img,
                (int(self.w / 2 - self._date_img.get_width() / 2 + ox),
                 int(self.h / 2 + self.big.get_height() * 0.55 + oy)),
            )
        if self._bat_img is not None:
            screen.blit(self._bat_img, (12, 12))


class Rain:
    """Falling glyph columns. Every glyph is pre rendered at three
    brightnesses in __init__, so a frame is pure blitting."""

    GLYPHS = "01MINTKIT<>{}[]#*+.:"
    COLS = 40
    TRAIL = 8

    def __init__(self, w, h, col):
        self.w, self.h, self.col = w, h, col
        self.cw = max(8, w // self.COLS)
        self.font = _font(max(12, int(self.cw * 1.5)))
        shades = (col["text"], col["accent"], col["dim"])
        self.cells = [
            [self.font.render(g, True, s) for g in self.GLYPHS] for s in shades
        ]
        self.rowh = max(1, self.font.get_height())
        self.rows = max(1, h // self.rowh + 1)
        self.heads = [random.uniform(-self.rows, 0.0) for _ in range(self.COLS)]
        self.speeds = [random.uniform(6.0, 18.0) for _ in range(self.COLS)]
        self.grid = [
            [random.randrange(len(self.GLYPHS)) for _ in range(self.rows)]
            for _ in range(self.COLS)
        ]

    def step(self, dt):
        for i in range(self.COLS):
            self.heads[i] += self.speeds[i] * dt
            if self.heads[i] - self.TRAIL > self.rows:
                self.heads[i] = random.uniform(-self.rows * 0.5, 0.0)
                self.speeds[i] = random.uniform(6.0, 18.0)
        # churn a few glyphs. Index swap only, no allocation.
        for _ in range(3):
            i = random.randrange(self.COLS)
            r = random.randrange(self.rows)
            self.grid[i][r] = random.randrange(len(self.GLYPHS))

    def draw(self, screen):
        screen.fill(self.col["bg"])
        for i in range(self.COLS):
            head = int(self.heads[i])
            x = i * self.cw
            row = self.grid[i]
            for k in range(self.TRAIL):
                r = head - k
                if r < 0 or r >= self.rows:
                    continue
                shade = 0 if k == 0 else (1 if k < 3 else 2)
                screen.blit(self.cells[shade][row[r]], (x, r * self.rowh))


MODES = {
    "bounce": Bounce,
    "starfield": Starfield,
    "clock": ClockSaver,
    "rain": Rain,
}


def mode_names():
    """For a settings picker."""
    return sorted(MODES.keys())


def _wake_events():
    """Real input only. Analog axes and hats are excluded on purpose: a stick
    that drifts one count would wake the saver instantly and forever."""
    out = []
    for name in ("KEYDOWN", "JOYBUTTONDOWN", "MOUSEBUTTONDOWN", "FINGERDOWN"):
        val = getattr(pygame, name, None)
        if isinstance(val, int):
            out.append(val)
    return tuple(out)


# --------------------------------------------------------------------------
# config
# --------------------------------------------------------------------------
_cfg = {"at": -1e9, "secs": DEFAULT_SAVER_SECS, "mode": DEFAULT_MODE}


def config():
    """(idle_secs_before_saver, mode). Cached, so this is free per frame.

    The old sleep timer re-read and re-parsed config.json every single frame,
    which is how writing the config file became a shutdown trigger. Not again.
    """
    now = time.monotonic()
    if now - _cfg["at"] < CONFIG_TTL:
        return _cfg["secs"], _cfg["mode"]
    _cfg["at"] = now
    try:
        raw = json.loads(CONFIG_FILE.read_text())
        if not isinstance(raw, dict):
            raw = {}
    except Exception:
        raw = {}
    try:
        _cfg["secs"] = int(raw.get("screensaver_secs", DEFAULT_SAVER_SECS))
    except Exception:
        _cfg["secs"] = DEFAULT_SAVER_SECS
    mode = raw.get("screensaver_mode", DEFAULT_MODE)
    _cfg["mode"] = mode if isinstance(mode, str) else DEFAULT_MODE
    return _cfg["secs"], _cfg["mode"]


# --------------------------------------------------------------------------
# main loop
# --------------------------------------------------------------------------
def run(screen, clock=None, mode=None, max_secs=None, warn_secs=WARN_SECS):
    """Block until input or deadline.

    Returns:
      "wake"     real input arrived. The event is consumed on purpose so the
                 keypress that woke the panel does not also press a button.
      "timeout"  max_secs elapsed. The caller should sleep now.
      "skip"     disabled, or something went wrong. Caller carries on as if
                 the saver did not exist.
    """
    name = (mode if isinstance(mode, str) else DEFAULT_MODE).strip().lower()
    if name in OFF_NAMES:
        return "skip"
    factory = MODES.get(name, MODES[DEFAULT_MODE])
    try:
        w, h = screen.get_size()
        col = _palette()
        saver = factory(w, h, col)
        wake = _wake_events()
        quit_type = getattr(pygame, "QUIT", None)
        small = _font(16)
        warn_img = None
        warn_left = None
        started = time.monotonic()
        last = started
        while True:
            now = time.monotonic()
            dt = now - last
            last = now
            if dt > 0.1:            # a stall must not teleport the wordmark
                dt = 0.1

            for ev in pygame.event.get():
                if quit_type is not None and ev.type == quit_type:
                    pygame.event.post(ev)     # QUIT belongs to the launcher
                    return "wake"
                if ev.type in wake:
                    return "wake"

            elapsed = now - started
            if max_secs is not None and elapsed >= max_secs:
                return "timeout"

            saver.step(dt)
            saver.draw(screen)

            if max_secs is not None:
                left = int(max_secs - elapsed)
                if left <= warn_secs:
                    if left != warn_left:
                        warn_left = left
                        warn_img = small.render(
                            "sleeping in %ds" % max(0, left), True, col["gold"]
                        )
                    if warn_img is not None:
                        screen.blit(warn_img, (w - warn_img.get_width() - 10, 10))

            pygame.display.flip()
            if clock is not None:
                clock.tick(FPS)
            else:
                pygame.time.wait(int(1000 / FPS))
    except Exception:
        return "skip"


def hook(timer, screen, clock=None):
    """Called from SleepTimer.tick(). Holds all the screen saver policy so
    sleep_timer.py never has to learn about config keys or modes.

    Returns None to fall through to normal sleep behaviour, True if the device
    should sleep now, False if the user came back.
    """
    try:
        secs, mode = config()
        if secs <= 0:
            return None
        idle = timer.idle_secs()
        if idle < secs:
            return None
        try:
            t = int(timer.timeout())
        except Exception:
            t = 0
        # With sleep disabled (timeout 0) the saver runs with no deadline.
        remaining = (t - idle) if t > 0 else None
        if remaining is not None and remaining <= 0:
            return True
        result = run(screen, clock, mode=mode, max_secs=remaining)
        if result == "timeout":
            return True
        if result == "wake":
            timer.poke()
            return False
        return None
    except Exception:
        return None


def preview(screen, clock=None, mode=None, secs=12):
    """Show a mode for a few seconds, for the settings picker."""
    return run(screen, clock, mode=mode, max_secs=secs, warn_secs=0)
