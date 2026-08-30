#!/usr/bin/env python3
# rootfs/launcher/screensaver.py -- MintKit screen savers
"""Idle screen savers for MintKit.

Runs when the device has been idle for ``screensaver_secs`` but has not yet
reached ``sleep_timeout_secs``.  Blocking by design: call :func:`run` and it
owns the display until the user touches something or the sleep deadline
arrives.  That avoids fighting the launcher's own draw order, which paints
over anything drawn from inside the frame loop.

Design constraints, learned the hard way on a Pi Zero 2 W:

* 357 MB of visible RAM with ``MemoryMax=300M``, and a launcher that has
  already been OOM-killed once for hoarding surfaces.  So: every surface is
  allocated during ``__init__``, never inside ``draw()``.  Text is re-rendered
  only when the string actually changes.
* The launcher replaces ``pygame.display.flip`` with an RGB565 packer that
  writes straight to ``/dev/fb0``.  Drawing to ``screen`` and calling
  ``flip()`` is therefore all that is required, on any video driver.
* 30 fps, not 60.  An idle device should not be warm.
* Nothing here may raise.  A screen saver that crashes takes the launcher
  with it, and the launcher restarts into a black screen.

Config, in ``~/.mintkit/config.json``::

    "screensaver_secs": 90,          # 0 disables, must be < sleep_timeout_secs
    "screensaver_mode": "bounce"     # see below, or "off"

Modes: ``bounce`` (the DVD one), ``starfield``, ``clock``, ``rain``,
``beams`` (Aqua style light ribbons), ``bubbles`` (the Vista ones) and
``kitsune`` (Crystal chasing butterflies).

Set ``sleep_timeout_secs`` to 0 and ``screensaver_secs`` to something small to
get a screen saver that runs forever and never sleeps.
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
except Exception:          # standalone preview, or themes.py missing
    th = None

try:
    from . import battery as _bat
except Exception:
    _bat = None

try:
    from . import pisugar as _ps      # I2C fallback when sysfs has no battery
except Exception:
    _ps = None

FPS = 30
WARN_SECS = 10
DEFAULT_MODE = "bounce"

_FALLBACK = {
    "bg": (10, 26, 16),
    "accent": (61, 204, 112),
    "text": (180, 240, 195),
    "dim": (90, 150, 105),
    "gold": (240, 200, 60),
}

_FONT_CACHE = {}


def _font(size, bold=False):
    """Cached font. Never allocate a font inside a draw call."""
    key = (size, bold)
    f = _FONT_CACHE.get(key)
    if f is None:
        try:
            if not pygame.font.get_init():
                pygame.font.init()
        except Exception:
            pass
        try:
            f = pygame.font.SysFont("monospace", size, bold=bold)
        except Exception:
            f = pygame.font.Font(None, size)
        _FONT_CACHE[key] = f
    return f


def _palette():
    """Theme colours with fallbacks, so a partial palette cannot KeyError."""
    pal = {}
    if th is not None:
        try:
            pal = th.get() or {}
        except Exception:
            pal = {}
    out = dict(_FALLBACK)
    for key in out:
        val = pal.get(key)
        if isinstance(val, (tuple, list)) and len(val) >= 3:
            try:
                out[key] = (int(val[0]), int(val[1]), int(val[2]))
            except Exception:
                pass
    return out


class Bounce:
    """The one everybody actually wants. Corner hits are counted."""

    NAME = "bounce"
    WORDMARK = "POCKETMINT"

    def __init__(self, w, h, col):
        self.w, self.h, self.col = w, h, col
        font = _font(max(20, int(h * 0.09)), True)
        order = ("accent", "text", "gold", "dim")
        self.imgs = [font.render(self.WORDMARK, True, col[k]) for k in order]
        self.idx = 0
        img = self.imgs[0]
        self.iw, self.ih = img.get_width(), img.get_height()
        self.x = (w - self.iw) * 0.5
        self.y = (h - self.ih) * 0.5
        self.vx = 108.0 * random.choice((1, -1))
        self.vy = 74.0 * random.choice((1, -1))
        self.corners = 0
        self._small = _font(16)
        self._corner_img = None
        self._corner_shown = -1

    def step(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        hit_x = hit_y = False
        if self.x <= 0:
            self.x, self.vx, hit_x = 0.0, abs(self.vx), True
        elif self.x + self.iw >= self.w:
            self.x, self.vx, hit_x = float(self.w - self.iw), -abs(self.vx), True
        if self.y <= 0:
            self.y, self.vy, hit_y = 0.0, abs(self.vy), True
        elif self.y + self.ih >= self.h:
            self.y, self.vy, hit_y = float(self.h - self.ih), -abs(self.vy), True
        if hit_x or hit_y:
            self.idx = (self.idx + 1) % len(self.imgs)
        if hit_x and hit_y:
            self.corners += 1

    def draw(self, screen):
        screen.blit(self.imgs[self.idx], (int(self.x), int(self.y)))
        if self.corners:
            if self.corners != self._corner_shown:
                self._corner_shown = self.corners
                self._corner_img = self._small.render(
                    "corner hits: %d" % self.corners, True, self.col["dim"]
                )
            screen.blit(self._corner_img, (10, self.h - 24))


class Starfield:
    """Cheapest mode. Pure fills, no blits, no text."""

    NAME = "starfield"
    COUNT = 110
    SPEED = 0.55

    def __init__(self, w, h, col):
        self.w, self.h, self.col = w, h, col
        self.cx, self.cy = w * 0.5, h * 0.5
        self.stars = [self._spawn(True) for _ in range(self.COUNT)]

    def _spawn(self, initial=False):
        return [
            random.uniform(-1.0, 1.0),
            random.uniform(-1.0, 1.0),
            random.uniform(0.05, 1.0) if initial else 1.0,
        ]

    def step(self, dt):
        speed = self.SPEED * dt
        for star in self.stars:
            star[2] -= speed
            if star[2] <= 0.02:
                star[0] = random.uniform(-1.0, 1.0)
                star[1] = random.uniform(-1.0, 1.0)
                star[2] = 1.0

    def draw(self, screen):
        near, mid, far = self.col["text"], self.col["accent"], self.col["dim"]
        w, h, cx, cy = self.w, self.h, self.cx, self.cy
        for sx, sy, sz in self.stars:
            k = 0.5 / sz
            px = int(cx + sx * k * cx)
            py = int(cy + sy * k * cy)
            if px < 0 or py < 0 or px >= w or py >= h:
                continue
            if sz < 0.25:
                screen.fill(near, (px, py, 3, 3))
            elif sz < 0.55:
                screen.fill(mid, (px, py, 2, 2))
            else:
                screen.fill(far, (px, py, 1, 1))


class ClockSaver:
    """Big drifting clock. Re-renders once a minute, not once a frame."""

    NAME = "clock"

    def __init__(self, w, h, col):
        self.w, self.h, self.col = w, h, col
        self.big = _font(max(32, int(h * 0.22)), True)
        self.mid = _font(max(14, int(h * 0.06)))
        self.small = _font(16)
        self.t = 0.0
        self._key = None
        self._time_img = None
        self._date_img = None
        self._bat_img = None
        self._bat_at = -999.0

    def step(self, dt):
        self.t += dt

    def draw(self, screen):
        lt = time.localtime()
        key = (lt.tm_hour, lt.tm_min)
        if key != self._key:
            self._key = key
            self._time_img = self.big.render(
                time.strftime("%H:%M", lt), True, self.col["accent"]
            )
            self._date_img = self.mid.render(
                time.strftime("%a %d %b", lt), True, self.col["dim"]
            )
        drift_x = math.sin(self.t * 0.11) * self.w * 0.06
        drift_y = math.sin(self.t * 0.07 + 1.3) * self.h * 0.09
        tw, thh = self._time_img.get_width(), self._time_img.get_height()
        tx = int((self.w - tw) * 0.5 + drift_x)
        ty = int((self.h - thh) * 0.5 + drift_y)
        screen.blit(self._time_img, (tx, ty))
        dw = self._date_img.get_width()
        screen.blit(self._date_img, (int(tx + (tw - dw) * 0.5), ty + thh + 8))

        now = time.monotonic()
        if now - self._bat_at > 30.0:
            self._bat_at = now
            self._bat_img = None
            info = None
            if _bat is not None:
                try:
                    info = _bat.get()
                except Exception:
                    info = None
            if info:
                label = "%s%%" % info.get("pct", "?")
                if info.get("charging"):
                    label += " chg"
                self._bat_img = self.small.render(label, True, self.col["dim"])
        if self._bat_img is not None:
            screen.blit(self._bat_img, (self.w - self._bat_img.get_width() - 10, 10))


class Rain:
    """Falling glyph columns. Glyphs are pre-rendered once per brightness."""

    NAME = "rain"
    GLYPHS = "01MINTKIT<>{}[]#*+.:"
    COLS = 40
    TRAIL = 8

    def __init__(self, w, h, col):
        self.w, self.h, self.col = w, h, col
        font = _font(16, True)
        self.gh = max(8, font.get_height())
        self.colw = max(1, w // self.COLS)
        self.head = [font.render(g, True, col["text"]) for g in self.GLYPHS]
        self.body = [font.render(g, True, col["accent"]) for g in self.GLYPHS]
        self.tail = [font.render(g, True, col["dim"]) for g in self.GLYPHS]
        self.y = [random.uniform(-h, 0.0) for _ in range(self.COLS)]
        self.speed = [random.uniform(70.0, 210.0) for _ in range(self.COLS)]
        self.seed = [random.randrange(len(self.GLYPHS)) for _ in range(self.COLS)]

    def step(self, dt):
        limit = self.h + self.TRAIL * self.gh
        for i in range(self.COLS):
            self.y[i] += self.speed[i] * dt
            if self.y[i] > limit:
                self.y[i] = random.uniform(-4.0 * self.gh, 0.0)
                self.speed[i] = random.uniform(70.0, 210.0)
                self.seed[i] = random.randrange(len(self.GLYPHS))

    def draw(self, screen):
        count = len(self.GLYPHS)
        for i in range(self.COLS):
            x = i * self.colw
            head = self.y[i]
            base = self.seed[i] + i * 3 + int(head / self.gh)
            for k in range(self.TRAIL):
                yy = head - k * self.gh
                if yy < -self.gh or yy > self.h:
                    continue
                idx = (base + k * 7) % count
                if k == 0:
                    img = self.head[idx]
                elif k < 3:
                    img = self.body[idx]
                else:
                    img = self.tail[idx]
                screen.blit(img, (x, int(yy)))


class Beams:
    """Aqua era light ribbons orbiting the centre.

    Each arm keeps a fixed length trail in a ring buffer. The colour and width
    of every trail segment are computed once at init, so a frame is nothing
    but line draws with no maths and no allocation.
    """

    NAME = "beams"
    ARMS = 5
    TRAIL = 26

    def __init__(self, w, h, col):
        self.w, self.h, self.col = w, h, col
        self.cx, self.cy = w * 0.5, h * 0.5
        self.rx, self.ry = w * 0.38, h * 0.38
        keys = ("accent", "text", "gold", "dim", "accent")
        self.pts = []
        self.shades = []
        self.widths = []
        self.phase = []
        self.spin = []
        self.wob = []
        for a in range(self.ARMS):
            base = col[keys[a % len(keys)]]
            self.pts.append([[self.cx, self.cy] for _ in range(self.TRAIL)])
            shade = []
            width = []
            for k in range(self.TRAIL):
                f = 1.0 - (k / float(self.TRAIL))
                f *= f                      # bright head, quick falloff
                shade.append((int(base[0] * f), int(base[1] * f), int(base[2] * f)))
                width.append(1 + int(f * 4))
            self.shades.append(shade)
            self.widths.append(width)
            self.phase.append(random.uniform(0.0, 6.28318))
            self.spin.append(random.uniform(0.45, 0.95) * random.choice((1.0, -1.0)))
            self.wob.append(random.uniform(0.5, 1.3))
        self.head = 0
        self.t = 0.0

    def step(self, dt):
        self.t += dt
        self.head = (self.head + 1) % self.TRAIL
        t = self.t
        for a in range(self.ARMS):
            ang = self.phase[a] + t * self.spin[a]
            r = 0.55 + 0.45 * math.sin(t * self.wob[a] + self.phase[a])
            p = self.pts[a][self.head]
            p[0] = self.cx + math.cos(ang) * self.rx * r
            p[1] = self.cy + math.sin(ang * 1.31 + 0.7) * self.ry * r

    def draw(self, screen):
        n = self.TRAIL
        head = self.head
        for a in range(self.ARMS):
            pts = self.pts[a]
            shade = self.shades[a]
            width = self.widths[a]
            for k in range(n - 1):
                p0 = pts[(head - k) % n]
                p1 = pts[(head - k - 1) % n]
                pygame.draw.line(
                    screen, shade[k],
                    (int(p0[0]), int(p0[1])),
                    (int(p1[0]), int(p1[1])),
                    width[k],
                )


class Bubbles:
    """The Vista ones. Every bubble sprite is baked once at init."""

    NAME = "bubbles"
    COUNT = 16
    RADII = (14, 19, 25, 32, 40)

    def __init__(self, w, h, col):
        self.w, self.h, self.col = w, h, col
        tints = (col["accent"], col["text"], col["gold"])
        self.sprites = []
        for r in self.RADII:
            for tint in tints:
                self.sprites.append(self._bake(r, tint))
        self.items = [self._spawn(None, True) for _ in range(self.COUNT)]

    @staticmethod
    def _bake(r, tint):
        d = r * 2 + 2
        try:
            surf = pygame.Surface((d, d), pygame.SRCALPHA)
        except Exception:
            surf = pygame.Surface((d, d))
        mid = (r + 1, r + 1)
        body = (tint[0], tint[1], tint[2], 42)
        rim = (min(255, tint[0] + 45), min(255, tint[1] + 45),
               min(255, tint[2] + 45), 170)
        pygame.draw.circle(surf, body, mid, r)
        pygame.draw.circle(surf, rim, mid, r, max(2, r // 7))
        pygame.draw.circle(surf, (255, 255, 255, 110),
                           (int(r * 0.62), int(r * 0.55)), max(2, r // 4))
        pygame.draw.circle(surf, (255, 255, 255, 55),
                           (int(r * 1.45), int(r * 1.48)), max(1, r // 8))
        return surf

    def _spawn(self, item=None, initial=False):
        idx = random.randrange(len(self.sprites))
        size = self.sprites[idx].get_width()
        vals = [
            random.uniform(0.0, max(1.0, self.w - size)),                 # 0 base x
            random.uniform(0.0, float(self.h)) if initial
            else float(self.h + size),                                    # 1 y
            random.uniform(20.0, 54.0) * (1.0 + (44 - size) / 220.0),     # 2 rise
            random.uniform(6.0, 26.0),                                    # 3 sway
            random.uniform(0.3, 0.9),                                     # 4 sway rate
            random.uniform(0.0, 6.28318),                                 # 5 phase
            idx,                                                          # 6 sprite
            size,                                                         # 7 size
        ]
        if item is None:
            return vals
        item[:] = vals
        return item

    def step(self, dt):
        for it in self.items:
            it[1] -= it[2] * dt
            it[5] += it[4] * dt
            if it[1] + it[7] < 0.0:
                self._spawn(it)

    def draw(self, screen):
        for base_x, y, _rise, sway, _rate, phase, idx, _size in self.items:
            screen.blit(
                self.sprites[idx],
                (int(base_x + math.sin(phase) * sway), int(y)),
            )


class Kitsune:
    """Crystal chasing butterflies, which is the only correct screen saver.

    The fox is drawn from primitives into four run frames at init, then
    flipped once for the other facing. Butterflies are three wing poses in two
    colours. Sparkles come from a fixed pool of reused slots. Nothing is
    allocated once the loop starts.
    """

    NAME = "kitsune"
    BUTTERFLIES = 4
    SPARKS = 28
    FOX_W = 138
    FOX_H = 58
    BODY_X = 60          # left margin reserved for the tails, do not shrink
    TAIL_SEGS = 6
    TAIL_LEN = 9.0
    SPEED = 128.0
    CATCH = 30.0
    RETARGET_SECS = 5.0

    def __init__(self, w, h, col):
        self.w, self.h, self.col = w, h, col
        right = [self._fox(col, p) for p in range(4)]
        left = []
        for img in right:
            try:
                left.append(pygame.transform.flip(img, True, False))
            except Exception:
                left.append(img)
        self.frames = (right, left)
        wing_cols = (col["gold"], col["text"])
        self.wings = [[self._butterfly(c, p) for p in range(3)] for c in wing_cols]
        self.flies = []
        for i in range(self.BUTTERFLIES):
            self.flies.append([
                random.uniform(80.0, max(90.0, w - 80.0)),   # 0 x
                random.uniform(60.0, max(70.0, h - 120.0)),  # 1 y
                random.uniform(-60.0, 60.0),                 # 2 vx
                random.uniform(-60.0, 60.0),                 # 3 vy
                random.uniform(0.0, 6.28318),                # 4 wing phase
                i % len(wing_cols),                          # 5 colour
                0.0,                                         # 6 startled timer
            ])
        self.fx = w * 0.5 - self.FOX_W * 0.5
        self.fy = h * 0.6
        self.fvx = 0.0
        self.fvy = 0.0
        self.facing = 0
        self.run = 0.0
        self.t = 0.0
        self.since_target = 0.0
        self.target = 0
        self.catches = 0
        self.sparks = [[0.0, 0.0, 0.0] for _ in range(self.SPARKS)]
        self._spark_at = 0

    # ---- sprite baking ---------------------------------------------------
    def _fox(self, col, phase):
        try:
            surf = pygame.Surface((self.FOX_W, self.FOX_H), pygame.SRCALPHA)
        except Exception:
            surf = pygame.Surface((self.FOX_W, self.FOX_H))
        body = col["accent"]
        tip = col["text"]
        flower = col["gold"]
        eye = col["bg"]
        swing = math.sin(phase * 1.5708)
        ox = self.BODY_X
        hx, hy = ox + 18, 36                    # hip, where the tails root

        # Three tails, fanned and curling up behind her, drawn first so their
        # roots tuck under the body. Four tapered segments each, with a pale
        # tip, which is what actually reads as "kitsune" on a 4 inch panel.
        # Every endpoint stays inside the surface. The old version drew these
        # at negative x, so all three were clipped away and she looked like a
        # plain fox.
        for i in range(3):
            ang = math.radians(168 + i * 16) + swing * 0.08 * (i + 1)
            x, y = float(hx), float(hy)
            for seg in range(self.TAIL_SEGS):
                shade = body if seg < self.TAIL_SEGS - 2 else tip
                width = 17 - seg * 2
                nx = x + math.cos(ang) * self.TAIL_LEN
                ny = y + math.sin(ang) * self.TAIL_LEN
                pygame.draw.line(surf, shade, (int(x), int(y)),
                                 (int(nx), int(ny)), width)
                pygame.draw.circle(surf, shade, (int(x), int(y)), width // 2)
                x, y = nx, ny
                ang += 0.06
            pygame.draw.circle(surf, tip, (int(x), int(y)), 5)

        for i in range(4):                      # legs
            lx = ox + 24 + i * 9
            kick = math.sin(phase * 1.5708 + i * 1.2) * 5.0
            pygame.draw.line(surf, body, (lx, 40), (int(lx + kick), 50), 4)
        pygame.draw.ellipse(surf, body, (ox + 18, 20, 42, 22))
        pygame.draw.ellipse(surf, tip, (ox + 26, 30, 26, 10))
        pygame.draw.circle(surf, body, (ox + 60, 20), 12)
        pygame.draw.polygon(surf, body, [(ox + 50, 12), (ox + 55, 0), (ox + 62, 12)])
        pygame.draw.polygon(surf, body, [(ox + 62, 11), (ox + 70, 2), (ox + 72, 15)])
        pygame.draw.polygon(surf, tip, [(ox + 64, 12), (ox + 69, 5), (ox + 70, 14)])
        pygame.draw.polygon(surf, body, [(ox + 66, 18), (ox + 77, 22), (ox + 66, 27)])
        pygame.draw.circle(surf, eye, (ox + 63, 18), 2)
        for k in range(5):                      # the flower, non negotiable
            fa = k * 1.2566
            pygame.draw.circle(
                surf, flower,
                (int(ox + 55 + math.cos(fa) * 4.0), int(6 + math.sin(fa) * 4.0)), 3,
            )
        pygame.draw.circle(surf, tip, (ox + 55, 6), 2)
        return surf

    @staticmethod
    def _butterfly(rgb, phase):
        try:
            surf = pygame.Surface((20, 16), pygame.SRCALPHA)
        except Exception:
            surf = pygame.Surface((20, 16))
        spread = (0.35, 0.72, 1.0)[phase]
        wing = int(7 * spread) + 2
        pygame.draw.polygon(surf, rgb, [(10, 8), (10 - wing, 8 - wing), (9 - wing, 11)])
        pygame.draw.polygon(surf, rgb, [(10, 8), (10 + wing, 8 - wing), (11 + wing, 11)])
        pygame.draw.line(surf, rgb, (10, 4), (10, 12), 2)
        return surf

    # ---- behaviour -------------------------------------------------------
    def _emit(self, x, y):
        s = self.sparks[self._spark_at]
        self._spark_at = (self._spark_at + 1) % self.SPARKS
        s[0] = x + random.uniform(-10.0, 10.0)
        s[1] = y + random.uniform(-10.0, 10.0)
        s[2] = random.uniform(0.4, 0.95)

    def _retarget(self):
        self.since_target = random.uniform(-1.5, 0.0)
        best, best_d = self.target, None
        nose_x = self.fx + (self.FOX_W * 0.86 if self.facing == 0
                            else self.FOX_W * 0.14)
        nose_y = self.fy + self.FOX_H * 0.35
        for i, b in enumerate(self.flies):
            if b[6] > 0.0 and len(self.flies) > 1:
                continue                        # let a startled one get away
            d = (b[0] - nose_x) ** 2 + (b[1] - nose_y) ** 2
            if best_d is None or d < best_d:
                best, best_d = i, d
        self.target = best

    def _flutter(self, b, dt):
        startled = b[6] > 0.0
        b[4] += dt * (20.0 if startled else 12.0)
        speed = 172.0 if startled else 64.0
        b[2] += random.uniform(-1.0, 1.0) * 120.0 * dt
        b[3] += random.uniform(-1.0, 1.0) * 120.0 * dt
        margin = 48.0
        if b[0] < margin:
            b[2] += 140.0 * dt
        elif b[0] > self.w - margin:
            b[2] -= 140.0 * dt
        if b[1] < margin:
            b[3] += 140.0 * dt
        elif b[1] > self.h - margin:
            b[3] -= 140.0 * dt
        mag = math.hypot(b[2], b[3]) or 1.0
        b[2] = b[2] / mag * speed
        b[3] = b[3] / mag * speed
        b[0] += b[2] * dt
        b[1] += (b[3] + math.sin(b[4] * 0.9) * 24.0) * dt
        if b[0] < 12.0:
            b[0], b[2] = 12.0, abs(b[2])
        elif b[0] > self.w - 12.0:
            b[0], b[2] = float(self.w - 12.0), -abs(b[2])
        if b[1] < 12.0:
            b[1], b[3] = 12.0, abs(b[3])
        elif b[1] > self.h - 12.0:
            b[1], b[3] = float(self.h - 12.0), -abs(b[3])
        if startled:
            b[6] -= dt

    def step(self, dt):
        self.t += dt
        self.since_target += dt
        for b in self.flies:
            self._flutter(b, dt)
        for s in self.sparks:
            if s[2] > 0.0:
                s[2] -= dt
                s[1] -= 24.0 * dt
        if self.since_target > self.RETARGET_SECS:
            self._retarget()

        tgt = self.flies[self.target]
        nose_x = self.fx + (self.FOX_W * 0.86 if self.facing == 0
                            else self.FOX_W * 0.14)
        nose_y = self.fy + self.FOX_H * 0.35
        dx, dy = tgt[0] - nose_x, tgt[1] - nose_y
        dist = math.hypot(dx, dy) or 1.0
        want = self.SPEED * (1.35 if dist > 220.0 else 1.0)
        k = min(1.0, dt * 2.8)
        self.fvx += ((dx / dist) * want - self.fvx) * k
        self.fvy += ((dy / dist) * want - self.fvy) * k
        self.fx += self.fvx * dt
        self.fy += self.fvy * dt
        if self.fx < 0.0:
            self.fx, self.fvx = 0.0, abs(self.fvx)
        elif self.fx > self.w - self.FOX_W:
            self.fx, self.fvx = float(self.w - self.FOX_W), -abs(self.fvx)
        if self.fy < 0.0:
            self.fy, self.fvy = 0.0, abs(self.fvy)
        elif self.fy > self.h - self.FOX_H:
            self.fy, self.fvy = float(self.h - self.FOX_H), -abs(self.fvy)
        if self.fvx < -8.0:
            self.facing = 1
        elif self.fvx > 8.0:
            self.facing = 0
        self.run += dt * (4.0 + min(9.0, abs(self.fvx) * 0.06))

        if dist < self.CATCH:
            self.catches += 1
            tgt[6] = 1.4
            away = math.hypot(dx, dy) or 1.0
            tgt[2] = -(dx / away) * 172.0
            tgt[3] = -(dy / away) * 172.0
            for _ in range(8):
                self._emit(tgt[0], tgt[1])
            self._retarget()

    def draw(self, screen):
        gold = self.col["gold"]
        text = self.col["text"]
        for s in self.sparks:
            if s[2] > 0.0:
                size = 3 if s[2] > 0.5 else 2
                screen.fill(gold if s[2] > 0.35 else text,
                            (int(s[0]), int(s[1]), size, size))
        for b in self.flies:
            screen.blit(self.wings[b[5]][int(b[4]) % 3],
                        (int(b[0]) - 10, int(b[1]) - 8))
        frame = self.frames[self.facing][int(self.run) % 4]
        screen.blit(frame, (int(self.fx), int(self.fy + math.sin(self.run * 1.6) * 2.0)))


MODES = {
    Bounce.NAME: Bounce,
    Starfield.NAME: Starfield,
    ClockSaver.NAME: ClockSaver,
    Rain.NAME: Rain,
    Beams.NAME: Beams,
    Bubbles.NAME: Bubbles,
    Kitsune.NAME: Kitsune,
}

OFF_NAMES = ("", "off", "none", "blank", "disabled")


def mode_names():
    """Selectable mode names, for a settings UI."""
    return sorted(MODES)


def _wake_events():
    """Deliberately excludes axis and hat motion so drift cannot wake it."""
    names = ("KEYDOWN", "JOYBUTTONDOWN", "MOUSEBUTTONDOWN")
    out = []
    for name in names:
        val = getattr(pygame, name, None)
        if isinstance(val, int):
            out.append(val)
    return tuple(out)


def run(screen, clock=None, mode=None, max_secs=None, warn_secs=WARN_SECS):
    """Blocking screen saver.

    Returns ``"wake"`` if the user pressed something, ``"timeout"`` if
    ``max_secs`` elapsed first, and ``"skip"`` if the saver could not start.
    The waking event is swallowed on purpose, so waking the device does not
    also activate whatever the cursor was sitting on.
    """
    name = (mode or DEFAULT_MODE)
    name = str(name).strip().lower()
    if name in OFF_NAMES:
        return "skip"
    factory = MODES.get(name, MODES[DEFAULT_MODE])
    col = _palette()

    try:
        width, height = screen.get_size()
        saver = factory(int(width), int(height), col)
    except Exception:
        return "skip"

    wake = _wake_events()
    quit_ev = getattr(pygame, "QUIT", None)
    bg = col["bg"]
    small = _font(16)
    warn_cache = {}

    started = time.monotonic()
    last = started
    while True:
        try:
            events = pygame.event.get()
        except Exception:
            events = []
        for ev in events:
            etype = getattr(ev, "type", None)
            if quit_ev is not None and etype == quit_ev:
                try:
                    pygame.event.post(ev)
                except Exception:
                    pass
                return "wake"
            if etype in wake:
                return "wake"

        now = time.monotonic()
        dt = now - last
        if dt > 0.1:
            dt = 0.1          # clamp, so a stall does not teleport anything
        last = now
        if max_secs is not None and now - started >= max_secs:
            return "timeout"

        try:
            saver.step(dt)
            screen.fill(bg)
            saver.draw(screen)
            if max_secs is not None:
                left = int(max_secs - (now - started)) + 1
                if left <= warn_secs:
                    img = warn_cache.get(left)
                    if img is None:
                        img = small.render(
                            "sleeping in %ds" % left, True, col["dim"]
                        )
                        warn_cache[left] = img
                    screen.blit(
                        img,
                        (saver.w - img.get_width() - 10, saver.h - img.get_height() - 8),
                    )
            pygame.display.flip()
        except Exception:
            return "skip"

        if clock is not None:
            try:
                clock.tick(FPS)
                continue
            except Exception:
                pass
        time.sleep(1.0 / FPS)


def preview(screen, clock=None, mode=None, secs=12):
    """Run a saver briefly, for a settings preview or a menu entry."""
    return run(screen, clock, mode=mode, max_secs=secs, warn_secs=0)


# ---------------------------------------------------------------------------
# config + the sleep_timer hook
#
# sleep_timer.tick() calls hook(self, screen, clock) once per frame.  It must
# never raise and it must be cheap, so the config read is cached.
# ---------------------------------------------------------------------------
DATA_DIR = Path(os.environ.get("MINTKIT_DATA", Path.home() / ".mintkit"))
CONFIG_FILE = DATA_DIR / "config.json"
CONFIG_TTL = 5.0
DEFAULT_SAVER_SECS = 90

# Power aware sleep. Reading the battery is cheap but not free, so it gets its
# own longer TTL. Unplugging is therefore noticed within BATTERY_TTL.
BATTERY_TTL = 20.0
CHARGING_RECHECK = 300.0        # saver chunk length while pinned awake
DEFAULT_CHARGING_TIMEOUT = 0    # 0 means never sleep on wall power
DEFAULT_LOW_PCT = 20
DEFAULT_LOW_TIMEOUT = 90

_BAT_CACHE = {"at": -1e9, "charging": None, "pct": None}

_CFG = {"at": -1e9, "data": {}}


def config():
    """Config dict, re-read at most every CONFIG_TTL seconds. Never raises.

    The cache matters: the old sleep timer re-parsed this file every frame,
    which turned a config write into a live event.
    """
    now = time.monotonic()
    if now - _CFG["at"] < CONFIG_TTL:
        return _CFG["data"]
    data = {}
    try:
        parsed = json.loads(CONFIG_FILE.read_text())
        if isinstance(parsed, dict):
            data = parsed
    except Exception:
        data = {}
    _CFG["at"] = now
    _CFG["data"] = data
    return data


def saver_secs():
    """Idle seconds before the saver starts. 0 or less disables it."""
    try:
        return float(config().get("screensaver_secs", DEFAULT_SAVER_SECS))
    except Exception:
        return float(DEFAULT_SAVER_SECS)


def saver_mode():
    """Selected mode name, falling back to DEFAULT_MODE."""
    try:
        return str(config().get("screensaver_mode", DEFAULT_MODE))
    except Exception:
        return DEFAULT_MODE


def power():
    """``(charging, pct)``, cached for BATTERY_TTL seconds. Never raises.

    ``charging`` is ``None`` when the power state cannot be read at all, which
    is deliberately different from ``False``. Unknown must behave exactly like
    the old code, so a device with no battery driver keeps sleeping normally
    instead of silently pinning itself awake forever.
    """
    now = time.monotonic()
    if now - _BAT_CACHE["at"] < BATTERY_TTL:
        return _BAT_CACHE["charging"], _BAT_CACHE["pct"]
    charging, pct = None, None
    for mod in (_bat, _ps):             # sysfs first, then the PiSugar bus
        if mod is None:
            continue
        try:
            info = mod.get()
            if isinstance(info, dict) and "charging" in info:
                charging = bool(info.get("charging", False))
                raw = info.get("pct")
                pct = float(raw) if raw is not None else None
                break
        except Exception:
            continue
    _BAT_CACHE["at"] = now
    _BAT_CACHE["charging"] = charging
    _BAT_CACHE["pct"] = pct
    return charging, pct


def sleep_timeout(base):
    """Power aware sleep timeout in seconds. 0 or less means never sleep.

    On wall power the device should not doze off mid dashboard, and on a low
    battery it should give up sooner than usual. Set ``power_aware_sleep`` to
    false in the config to get the plain configured timeout back.
    """
    try:
        base = float(base)
    except Exception:
        base = 0.0
    try:
        cfg = config()
        if not cfg.get("power_aware_sleep", True):
            return base
        charging, pct = power()
        if charging is None:
            return base                     # unknown, behave as before
        if charging:
            return float(cfg.get("sleep_timeout_charging_secs",
                                 DEFAULT_CHARGING_TIMEOUT))
        low_pct = float(cfg.get("low_battery_pct", DEFAULT_LOW_PCT))
        if pct is not None and pct <= low_pct:
            return float(cfg.get("sleep_timeout_low_secs", DEFAULT_LOW_TIMEOUT))
        return base
    except Exception:
        return base


def hook(timer, screen, clock=None):
    """Called every frame from SleepTimer.tick().

    Returns ``None`` to fall through and let tick() behave normally, ``True``
    if the device should sleep now, and ``False`` if it should stay awake.
    Wrapped end to end, because anything raised here takes the launcher down.
    """
    try:
        secs = saver_secs()
        if secs <= 0:
            return None
        idle = timer.idle_secs()
        if idle < secs:
            return None

        try:
            base = float(timer.timeout())
        except Exception:
            base = 0.0
        limit = sleep_timeout(base)

        if limit > 0:
            remaining = limit - idle
            if remaining <= 0:
                return True
            result = run(screen, clock, mode=saver_mode(), max_secs=remaining)
            if result == "timeout":
                return True
        else:
            # Pinned awake by policy. Run in chunks rather than forever, so
            # pulling the charger is noticed within CHARGING_RECHECK instead
            # of never. No countdown overlay, because nothing is counting.
            result = run(screen, clock, mode=saver_mode(),
                         max_secs=CHARGING_RECHECK, warn_secs=0)
            if result != "wake":
                return False                # stay awake, re-enter next frame

        if result == "wake":
            try:
                timer.poke()
            except Exception:
                pass
            return False
        return None          # "skip": saver could not start, act as if absent
    except Exception:
        return None
