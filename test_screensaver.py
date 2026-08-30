#!/usr/bin/env python3
"""Behavioural tests for launcher/screensaver.py and the sleep_timer hook.

No pygame, no display, no SD card, no network. A fake pygame is installed into
sys.modules before the modules under test are imported, so every surface
allocation, text render, event and flip is observable and countable.

Run:  python3 test_screensaver.py
"""
import importlib.util
import json
import sys
import time
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAUNCHER = HERE / "rootfs" / "launcher"

STATS = {"surfaces": 0, "renders": 0, "fonts": 0, "flips": 0, "fills": 0,
         "blits": 0, "draws": 0, "transforms": 0}
PALETTE = {
    "bg": (10, 26, 16),
    "accent": (61, 204, 112),
    "text": (180, 240, 195),
    "dim": (90, 150, 105),
    "gold": (240, 200, 60),
}


# --------------------------------------------------------------------------
# fake pygame
# --------------------------------------------------------------------------
class FakeRect:
    def __init__(self, size, **kw):
        self.w, self.h = size
        self.x = self.y = 0
        for key, val in kw.items():
            if key == "center":
                self.x, self.y = int(val[0] - self.w / 2), int(val[1] - self.h / 2)
            elif key == "topleft":
                self.x, self.y = int(val[0]), int(val[1])
        self.centerx = self.x + self.w // 2
        self.centery = self.y + self.h // 2
        self.bottom = self.y + self.h
        self.right = self.x + self.w


class FakeSurface:
    def __init__(self, size=(800, 480), flags=0):
        STATS["surfaces"] += 1
        self._size = (int(size[0]), int(size[1]))

    def get_size(self):
        return self._size

    def get_width(self):
        return self._size[0]

    def get_height(self):
        return self._size[1]

    def get_rect(self, **kw):
        return FakeRect(self._size, **kw)

    def fill(self, color, rect=None):
        STATS["fills"] += 1

    def blit(self, img, pos):
        STATS["blits"] += 1

    def set_alpha(self, alpha):
        pass

    def convert(self, *a):
        return self


class FakeFont:
    def __init__(self, height, bold=False):
        STATS["fonts"] += 1
        self._h = max(1, int(height))

    def render(self, text, aa, color, bg=None):
        STATS["renders"] += 1
        return FakeSurface((max(1, int(len(str(text)) * self._h * 0.6)), self._h))

    def get_height(self):
        return self._h

    def size(self, text):
        return (max(1, int(len(str(text)) * self._h * 0.6)), self._h)


class FakeEvent:
    def __init__(self, etype, **kw):
        self.type = etype
        for key, val in kw.items():
            setattr(self, key, val)


class FakeClock:
    """No-op clock, so tests spin at full speed instead of sleeping."""

    def __init__(self):
        self.ticks = 0

    def tick(self, fps=0):
        self.ticks += 1
        return 0

    def get_fps(self):
        return 30.0


def install_fake_pygame():
    pg = types.ModuleType("pygame")
    pg.KEYDOWN = 768
    pg.KEYUP = 769
    pg.MOUSEBUTTONDOWN = 1025
    pg.JOYAXISMOTION = 1536
    pg.JOYHATMOTION = 1538
    pg.JOYBUTTONDOWN = 1539
    pg.QUIT = 256
    pg.SRCALPHA = 65536
    pg.K_ESCAPE = 27
    pg.Surface = FakeSurface

    queue = []

    ev = types.ModuleType("pygame.event")
    ev.QUEUE = queue

    def _get():
        out = list(queue)
        del queue[:]
        return out

    ev.get = _get
    ev.post = lambda e: queue.append(e)
    ev.clear = lambda: queue.clear()
    ev.pump = lambda: None
    pg.event = ev

    font = types.ModuleType("pygame.font")
    font._inited = True
    font.init = lambda: None
    font.get_init = lambda: True
    font.SysFont = lambda name, size, bold=False, italic=False: FakeFont(size, bold)
    font.Font = lambda name, size: FakeFont(size)
    pg.font = font

    display = types.ModuleType("pygame.display")

    def _flip():
        STATS["flips"] += 1

    display.flip = _flip
    display.update = _flip
    display.set_mode = lambda size, flags=0: FakeSurface(size)
    pg.display = display

    ptime = types.ModuleType("pygame.time")
    ptime.wait = lambda ms: None
    ptime.get_ticks = lambda: int(time.monotonic() * 1000)
    ptime.Clock = FakeClock
    pg.time = ptime

    # pygame.draw, strict on purpose. Real pygame raises on a float colour
    # component, an out of range channel, or a malformed point, and this stub
    # does too, so a bad primitive fails here instead of on the panel.
    def _color(c):
        if not isinstance(c, (tuple, list)) or len(c) not in (3, 4):
            raise TypeError("bad colour %r" % (c,))
        for v in c:
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError("non int colour channel %r" % (c,))
            if v < 0 or v > 255:
                raise ValueError("colour channel out of range %r" % (c,))

    def _point(p):
        if not isinstance(p, (tuple, list)) or len(p) != 2:
            raise TypeError("bad point %r" % (p,))
        for v in p:
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise TypeError("bad point %r" % (p,))

    def _rect4(r):
        if not isinstance(r, (tuple, list)) or len(r) != 4:
            raise TypeError("bad rect %r" % (r,))

    draw = types.ModuleType("pygame.draw")

    def _line(surface, color, start, end, width=1):
        _color(color)
        _point(start)
        _point(end)
        if isinstance(width, bool) or not isinstance(width, int) or width < 1:
            raise TypeError("bad line width %r" % (width,))
        STATS["draws"] += 1

    def _circle(surface, color, center, radius, width=0):
        _color(color)
        _point(center)
        if radius < 0:
            raise ValueError("negative radius %r" % (radius,))
        STATS["draws"] += 1

    def _polygon(surface, color, points, width=0):
        _color(color)
        if not isinstance(points, (tuple, list)) or len(points) < 3:
            raise TypeError("bad polygon %r" % (points,))
        for p in points:
            _point(p)
        STATS["draws"] += 1

    def _ellipse(surface, color, rect, width=0):
        _color(color)
        _rect4(rect)
        STATS["draws"] += 1

    def _drect(surface, color, rect, width=0):
        _color(color)
        _rect4(rect)
        STATS["draws"] += 1

    draw.line = _line
    draw.aaline = _line
    draw.circle = _circle
    draw.polygon = _polygon
    draw.ellipse = _ellipse
    draw.rect = _drect
    pg.draw = draw

    transform = types.ModuleType("pygame.transform")

    def _flip_surf(surf, xaxis, yaxis):
        STATS["transforms"] += 1
        return FakeSurface(surf.get_size())

    transform.flip = _flip_surf
    transform.scale = lambda s, size: FakeSurface(size)
    pg.transform = transform

    for name, mod in (
        ("pygame", pg),
        ("pygame.event", ev),
        ("pygame.font", font),
        ("pygame.display", display),
        ("pygame.time", ptime),
        ("pygame.draw", draw),
        ("pygame.transform", transform),
    ):
        sys.modules[name] = mod
    return pg


def install_fake_launcher():
    pkg = types.ModuleType("launcher")
    pkg.__path__ = [str(LAUNCHER)]
    sys.modules["launcher"] = pkg

    themes = types.ModuleType("launcher.themes")
    themes.get = lambda: dict(PALETTE)
    sys.modules["launcher.themes"] = themes

    battery = types.ModuleType("launcher.battery")
    battery.get = lambda: {"pct": 88, "charging": False}
    sys.modules["launcher.battery"] = battery
    return themes, battery


def load(module_name, filename):
    path = LAUNCHER / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


class CountingConfig:
    """Stands in for CONFIG_FILE so config reads can be counted."""

    def __init__(self, payload):
        self.payload = json.dumps(payload)
        self.reads = 0

    def read_text(self):
        self.reads += 1
        return self.payload


class StubSaver:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def run(self, screen, clock=None, mode=None, max_secs=None, warn_secs=10):
        self.calls.append({"mode": mode, "max_secs": max_secs})
        return self.result


# --------------------------------------------------------------------------
# harness
# --------------------------------------------------------------------------
RESULTS = []


def check(label, ok, detail=""):
    RESULTS.append((label, bool(ok), detail))
    print("%-4s %s%s" % ("PASS" if ok else "FAIL", label, ("  -- " + detail) if detail and not ok else ""))


def main():
    install_fake_pygame()
    themes, battery = install_fake_launcher()
    ss = load("launcher.screensaver", "screensaver.py")
    st = load("launcher.sleep_timer", "sleep_timer.py")

    screen = FakeSurface((800, 480))
    clock = FakeClock()

    # 1. every mode survives 90 frames and allocates nothing per frame
    check(
        "all modes registered",
        sorted(ss.mode_names()) == ["beams", "bounce", "bubbles", "clock",
                                    "kitsune", "rain", "starfield"],
        str(ss.mode_names()),
    )
    for name in ss.mode_names():
        col = ss._palette()
        saver = ss.MODES[name](800, 480, col)
        saver.step(1.0 / 30)
        saver.draw(screen)
        before_r, before_s = STATS["renders"], STATS["surfaces"]
        try:
            for _ in range(90):
                saver.step(1.0 / 30)
                saver.draw(screen)
            ok, why = True, ""
        except Exception as exc:
            ok, why = False, "%s: %s" % (type(exc).__name__, exc)
        check("mode %s runs 90 frames" % name, ok, why)
        renders = STATS["renders"] - before_r
        surfaces = STATS["surfaces"] - before_s
        check(
            "mode %s allocates nothing per frame" % name,
            renders <= 1 and surfaces <= 1,
            "renders=%d surfaces=%d over 90 frames" % (renders, surfaces),
        )

    # 1b. the early 2000s trio, in detail
    col = ss._palette()

    bm = ss.Beams(800, 480, col)
    draws_before = STATS["draws"]
    for _ in range(120):
        bm.step(1.0 / 30)
        bm.draw(screen)
    check("beams draw a line per trail segment",
          STATS["draws"] - draws_before == 120 * ss.Beams.ARMS * (ss.Beams.TRAIL - 1),
          "draws=%d" % (STATS["draws"] - draws_before))
    check("beam shade and width tables are baked once",
          len(bm.shades) == ss.Beams.ARMS and len(bm.shades[0]) == ss.Beams.TRAIL
          and len(bm.widths[0]) == ss.Beams.TRAIL)
    check("beam trails stay near the screen",
          all(-80 <= p[0] <= 880 and -80 <= p[1] <= 560
              for arm in bm.pts for p in arm))
    check("beam ring buffer never grows",
          all(len(arm) == ss.Beams.TRAIL for arm in bm.pts))

    bub = ss.Bubbles(800, 480, col)
    check("bubble sprites are baked once",
          len(bub.sprites) == len(ss.Bubbles.RADII) * 3, str(len(bub.sprites)))
    start_y = [it[1] for it in bub.items]
    for _ in range(150):
        bub.step(1.0 / 30)
        bub.draw(screen)
    check("bubbles rise", any(it[1] < y0 for it, y0 in zip(bub.items, start_y)))
    bub.items[0][1] = -999.0
    surf_before = STATS["surfaces"]
    bub.step(1.0 / 30)
    check("a bubble off the top respawns at the bottom",
          bub.items[0][1] >= 480.0, "y=%.1f" % bub.items[0][1])
    check("recycling a bubble allocates no surface",
          STATS["surfaces"] == surf_before)
    check("bubble count is fixed", len(bub.items) == ss.Bubbles.COUNT)

    fox = ss.Kitsune(800, 480, col)
    check("fox has four run frames in both facings",
          len(fox.frames) == 2 and len(fox.frames[0]) == 4 and len(fox.frames[1]) == 4)
    check("fox was flipped, not redrawn", STATS["transforms"] >= 4)
    check("butterfly wing poses are baked",
          len(fox.wings) == 2 and all(len(w) == 3 for w in fox.wings))
    surf_before = STATS["surfaces"]
    try:
        for _ in range(900):
            fox.step(1.0 / 30)
            fox.draw(screen)
        ok, why = True, ""
    except Exception as exc:
        ok, why = False, "%s: %s" % (type(exc).__name__, exc)
    check("kitsune survives 900 frames", ok, why)
    check("kitsune allocates nothing while running",
          STATS["surfaces"] == surf_before,
          "surfaces=%d" % (STATS["surfaces"] - surf_before))
    check("the fox actually catches butterflies", fox.catches >= 1,
          "catches=%d" % fox.catches)
    check("the fox stays on screen",
          0.0 <= fox.fx <= 800 - ss.Kitsune.FOX_W
          and 0.0 <= fox.fy <= 480 - ss.Kitsune.FOX_H,
          "%.1f,%.1f" % (fox.fx, fox.fy))
    check("butterflies stay on screen",
          all(0.0 <= b[0] <= 800.0 and 0.0 <= b[1] <= 480.0 for b in fox.flies),
          str([(int(b[0]), int(b[1])) for b in fox.flies]))
    check("the target index stays valid", 0 <= fox.target < len(fox.flies))
    check("spark pool is fixed size", len(fox.sparks) == ss.Kitsune.SPARKS)
    check("startle timers decay", all(b[6] <= 1.4 for b in fox.flies))
    check("facing is one of the two baked sets", fox.facing in (0, 1))

    for name in ("beams", "bubbles", "kitsune"):
        res = ss.run(screen, clock, mode=name, max_secs=0.02)
        check("run() drives %s end to end" % name, res == "timeout", str(res))

    # 2. wake on a real key
    sys.modules["pygame"].event.post(FakeEvent(768, key=32))
    check("KEYDOWN wakes the saver", ss.run(screen, clock, mode="starfield", max_secs=5) == "wake")

    # 3. the waking event is swallowed, not left for the launcher
    sys.modules["pygame"].event.post(FakeEvent(768, key=32))
    ss.run(screen, clock, mode="starfield", max_secs=5)
    check("wake event is swallowed", len(sys.modules["pygame"].event.QUEUE) == 0)

    # 4. analog drift must not wake it
    sys.modules["pygame"].event.post(FakeEvent(1536, axis=0, value=0.02))
    res = ss.run(screen, clock, mode="starfield", max_secs=0.05)
    check("JOYAXISMOTION does not wake", res == "timeout", res)

    # 5. joystick buttons do wake it
    sys.modules["pygame"].event.post(FakeEvent(1539, button=1))
    check("JOYBUTTONDOWN wakes", ss.run(screen, clock, mode="bounce", max_secs=5) == "wake")

    # 6. off switches
    check("mode off skips", ss.run(screen, clock, mode="off") == "skip")
    check("empty mode skips", ss.run(screen, clock, mode="") == "skip")
    check("mode None uses default", ss.run(screen, clock, mode=None, max_secs=0.02) == "timeout")
    check("unknown mode falls back", ss.run(screen, clock, mode="banana", max_secs=0.02) == "timeout")
    check("mode is case insensitive", ss.run(screen, clock, mode="  STARFIELD ", max_secs=0.02) == "timeout")

    # 7. it actually paints
    before = STATS["flips"]
    ss.run(screen, clock, mode="clock", max_secs=0.05)
    check("saver flips the display", STATS["flips"] > before, "flips=%d" % (STATS["flips"] - before))

    # 8. broken theme must not crash it
    themes.get = lambda: {"accent": (1, 2, 3)}
    col = ss._palette()
    check("partial palette is filled", col["bg"] == ss._FALLBACK["bg"] and col["accent"] == (1, 2, 3), str(col))
    themes.get = lambda: (_ for _ in ()).throw(RuntimeError("theme exploded"))
    try:
        col = ss._palette()
        ok = col == ss._FALLBACK
    except Exception as exc:
        ok = False
        col = exc
    check("exploding theme falls back", ok, str(col))
    themes.get = lambda: dict(PALETTE)

    # 9. dead battery module must not crash the clock saver
    ss._bat = None
    saver = ss.ClockSaver(800, 480, ss._palette())
    try:
        saver.step(0.1)
        saver.draw(screen)
        ok, why = True, ""
    except Exception as exc:
        ok, why = False, str(exc)
    check("clock saver survives no battery module", ok, why)

    # --------------------------------------------------------------
    # sleep_timer hook
    # --------------------------------------------------------------
    cfg = CountingConfig({"sleep_timeout_secs": 300, "screensaver_secs": 90, "screensaver_mode": "rain"})
    st.CONFIG_FILE = cfg

    timer = st.SleepTimer()
    check("reads saver config", (timer.saver_secs(), timer.saver_mode()) == (90, "rain"), "%s %s" % (timer.saver_secs(), timer.saver_mode()))

    stub = StubSaver("wake")
    st._saver = stub
    timer = st.SleepTimer()
    timer._last_activity = time.monotonic() - 100          # idle past the saver, not past sleep
    res = timer.tick(screen, clock)
    check("saver runs before sleep", res is False and len(stub.calls) == 1, "res=%s calls=%s" % (res, stub.calls))
    check("saver gets the configured mode", stub.calls and stub.calls[0]["mode"] == "rain", str(stub.calls))
    check(
        "saver deadline is the remaining sleep time",
        stub.calls and 195 < stub.calls[0]["max_secs"] < 205,
        str(stub.calls),
    )
    check("wake resets the idle timer", timer.idle_secs() < 1.0, "%.1f" % timer.idle_secs())

    stub = StubSaver("timeout")
    st._saver = stub
    timer = st.SleepTimer()
    timer._last_activity = time.monotonic() - 100
    check("saver timeout means sleep now", timer.tick(screen, clock) is True)

    stub = StubSaver("skip")
    st._saver = stub
    timer = st.SleepTimer()
    timer._last_activity = time.monotonic() - 100
    check("skip falls through without sleeping", timer.tick(screen, clock) is False)

    stub = StubSaver("wake")
    st._saver = stub
    timer = st.SleepTimer()
    timer._last_activity = time.monotonic() - 10           # not idle enough yet
    res = timer.tick(screen, clock)
    check("saver does not run early", res is False and stub.calls == [])

    # sleep disabled, saver still runs, with no deadline
    cfg2 = CountingConfig({"sleep_timeout_secs": 0, "screensaver_secs": 5, "screensaver_mode": "clock"})
    st.CONFIG_FILE = cfg2
    stub = StubSaver("wake")
    st._saver = stub
    timer = st.SleepTimer()
    timer._last_activity = time.monotonic() - 60
    res = timer.tick(screen, clock)
    check(
        "saver runs forever when sleep is disabled",
        res is False and stub.calls and stub.calls[0]["max_secs"] is None,
        "res=%s calls=%s" % (res, stub.calls),
    )

    # saver disabled entirely
    cfg3 = CountingConfig({"sleep_timeout_secs": 60, "screensaver_secs": 0})
    st.CONFIG_FILE = cfg3
    stub = StubSaver("wake")
    st._saver = stub
    timer = st.SleepTimer()
    timer._last_activity = time.monotonic() - 30
    check("screensaver_secs 0 disables the saver", timer.tick(screen, clock) is False and stub.calls == [])
    timer._last_activity = time.monotonic() - 90
    check("sleep still fires with the saver off", timer.tick(screen, clock) is True and stub.calls == [])

    # a raising saver must never take the launcher down
    class Exploding:
        def run(self, *a, **kw):
            raise RuntimeError("saver exploded")

    cfg4 = CountingConfig({"sleep_timeout_secs": 300, "screensaver_secs": 10})
    st.CONFIG_FILE = cfg4
    st._saver = Exploding()
    timer = st.SleepTimer()
    timer._last_activity = time.monotonic() - 60
    try:
        res = timer.tick(screen, clock)
        ok, why = res is False, "res=%s" % res
    except Exception as exc:
        ok, why = False, "raised %s" % exc
    check("exploding saver is contained", ok, why)

    # missing screensaver.py behaves like the old module
    st._saver = None
    timer = st.SleepTimer()
    timer._last_activity = time.monotonic() - 60
    check("no saver module, no sleep yet", timer.tick(screen, clock) is False)
    timer._last_activity = time.monotonic() - 400
    check("no saver module, sleep still fires", timer.tick(screen, clock) is True)

    # config is cached, not read once per frame
    cfg5 = CountingConfig({"sleep_timeout_secs": 0, "screensaver_secs": 0})
    st.CONFIG_FILE = cfg5
    st._saver = None
    timer = st.SleepTimer()
    for _ in range(600):
        timer.tick(screen, clock)
    check("600 frames cause one config read", cfg5.reads == 1, "reads=%d" % cfg5.reads)

    failed = [r for r in RESULTS if not r[1]]
    print("\n%d checks, %d failed" % (len(RESULTS), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
