#!/usr/bin/env python3
"""
launcher/inputbridge.py  --  evdev to pygame input bridge for MintKit.

WHY THIS EXISTS
---------------
mintkit.service runs the launcher with SDL_VIDEODRIVER=offscreen, because the
launcher packs its own RGB565 and writes straight to /dev/fb0 rather than
letting SDL own the display. The offscreen video driver has no window system
attached, so SDL never opens an input device. pygame.event.get() therefore
returns an empty list on every single frame, forever. No keyboard, no gamepad,
no GPIO buttons, no hotkeys.

This module reads the kernel evdev character devices directly and posts
synthetic pygame KEYDOWN and KEYUP events into the normal event queue, so the
rest of the launcher needs no changes at all.

DESIGN NOTES
------------
* Standard library only. python3-evdev is not present on shipped cards and
  on-device apt is not safe to depend on.
* Devices are discovered by parsing /proc/bus/input/devices and keeping any
  node whose EV bitmask advertises EV_KEY. That covers keyboards, gamepads,
  and USB HID button boards alike.
* Rescans every few seconds, so a Bluetooth keyboard that connects after boot
  is picked up without a restart.
* Posting is skipped until pygame is initialised, so this can be started at
  import time without ordering worries.

Run it standalone to test without the launcher:
    sudo python3 -m launcher.inputbridge
"""

import glob
import os
import select
import struct
import threading
import time

import pygame

# struct input_event { struct timeval time; __u16 type; __u16 code; __s32 value; }
# timeval is two C longs, so this is 24 bytes on 64-bit and 16 on 32-bit.
# Native format codes let struct work that out for us.
_EV_FORMAT = "llHHi"
_EV_SIZE = struct.calcsize(_EV_FORMAT)

EV_KEY = 0x01
EV_KEY_BIT = 0x02  # bit 1 of the EV bitmask in /proc/bus/input/devices

RESCAN_SECONDS = 3.0
SELECT_TIMEOUT = 0.5

# Linux keycode -> pygame key constant.
# Values are from include/uapi/linux/input-event-codes.h
_KEYMAP = {
    1: pygame.K_ESCAPE,
    2: pygame.K_1, 3: pygame.K_2, 4: pygame.K_3, 5: pygame.K_4, 6: pygame.K_5,
    7: pygame.K_6, 8: pygame.K_7, 9: pygame.K_8, 10: pygame.K_9, 11: pygame.K_0,
    12: pygame.K_MINUS, 13: pygame.K_EQUALS, 14: pygame.K_BACKSPACE, 15: pygame.K_TAB,
    16: pygame.K_q, 17: pygame.K_w, 18: pygame.K_e, 19: pygame.K_r, 20: pygame.K_t,
    21: pygame.K_y, 22: pygame.K_u, 23: pygame.K_i, 24: pygame.K_o, 25: pygame.K_p,
    26: pygame.K_LEFTBRACKET, 27: pygame.K_RIGHTBRACKET, 28: pygame.K_RETURN,
    29: pygame.K_LCTRL,
    30: pygame.K_a, 31: pygame.K_s, 32: pygame.K_d, 33: pygame.K_f, 34: pygame.K_g,
    35: pygame.K_h, 36: pygame.K_j, 37: pygame.K_k, 38: pygame.K_l,
    39: pygame.K_SEMICOLON, 40: pygame.K_QUOTE, 41: pygame.K_BACKQUOTE,
    42: pygame.K_LSHIFT, 43: pygame.K_BACKSLASH,
    44: pygame.K_z, 45: pygame.K_x, 46: pygame.K_c, 47: pygame.K_v, 48: pygame.K_b,
    49: pygame.K_n, 50: pygame.K_m,
    51: pygame.K_COMMA, 52: pygame.K_PERIOD, 53: pygame.K_SLASH,
    54: pygame.K_RSHIFT, 55: pygame.K_ASTERISK, 56: pygame.K_LALT, 57: pygame.K_SPACE,
    58: pygame.K_CAPSLOCK,
    59: pygame.K_F1, 60: pygame.K_F2, 61: pygame.K_F3, 62: pygame.K_F4,
    63: pygame.K_F5, 64: pygame.K_F6, 65: pygame.K_F7, 66: pygame.K_F8,
    67: pygame.K_F9, 68: pygame.K_F10, 87: pygame.K_F11, 88: pygame.K_F12,
    96: pygame.K_KP_ENTER, 97: pygame.K_RCTRL, 98: pygame.K_KP_DIVIDE,
    100: pygame.K_RALT,
    102: pygame.K_HOME, 103: pygame.K_UP, 104: pygame.K_PAGEUP,
    105: pygame.K_LEFT, 106: pygame.K_RIGHT, 107: pygame.K_END,
    108: pygame.K_DOWN, 109: pygame.K_PAGEDOWN, 110: pygame.K_INSERT,
    111: pygame.K_DELETE,
}

# Gamepad and HID button codes, folded onto the same keys the launcher already
# understands. A Pico presenting the GPIO buttons as a HID gamepad lands here.
_BTNMAP = {
    0x130: pygame.K_z,       # BTN_SOUTH / A      -> confirm
    0x131: pygame.K_x,       # BTN_EAST  / B      -> cancel
    0x133: pygame.K_z,       # BTN_NORTH / X
    0x134: pygame.K_x,       # BTN_WEST  / Y
    0x136: pygame.K_TAB,     # BTN_TL  / L
    0x137: pygame.K_BACKQUOTE,  # BTN_TR / R
    0x13a: pygame.K_ESCAPE,  # BTN_SELECT
    0x13b: pygame.K_RETURN,  # BTN_START
    0x13c: pygame.K_HOME,    # BTN_MODE / guide
    0x220: pygame.K_UP,      # BTN_DPAD_UP
    0x221: pygame.K_DOWN,    # BTN_DPAD_DOWN
    0x222: pygame.K_LEFT,    # BTN_DPAD_LEFT
    0x223: pygame.K_RIGHT,   # BTN_DPAD_RIGHT
}

# Printable characters, so event.unicode is populated for anything that reads it
# (the WiFi password entry in settings, for one).
_UNSHIFTED = {
    pygame.K_1: "1", pygame.K_2: "2", pygame.K_3: "3", pygame.K_4: "4",
    pygame.K_5: "5", pygame.K_6: "6", pygame.K_7: "7", pygame.K_8: "8",
    pygame.K_9: "9", pygame.K_0: "0", pygame.K_MINUS: "-", pygame.K_EQUALS: "=",
    pygame.K_SPACE: " ", pygame.K_SEMICOLON: ";", pygame.K_QUOTE: "'",
    pygame.K_COMMA: ",", pygame.K_PERIOD: ".", pygame.K_SLASH: "/",
    pygame.K_BACKSLASH: "\\", pygame.K_BACKQUOTE: "`",
    pygame.K_LEFTBRACKET: "[", pygame.K_RIGHTBRACKET: "]",
}
for _c in "abcdefghijklmnopqrstuvwxyz":
    _UNSHIFTED[getattr(pygame, "K_" + _c)] = _c

_SHIFTED = {
    "1": "!", "2": "@", "3": "#", "4": "$", "5": "%", "6": "^", "7": "&",
    "8": "*", "9": "(", "0": ")", "-": "_", "=": "+", ";": ":", "'": '"',
    ",": "<", ".": ">", "/": "?", "\\": "|", "`": "~", "[": "{", "]": "}",
}

_MODBITS = {
    pygame.K_LSHIFT: pygame.KMOD_LSHIFT,
    pygame.K_RSHIFT: pygame.KMOD_RSHIFT,
    pygame.K_LCTRL: pygame.KMOD_LCTRL,
    pygame.K_RCTRL: pygame.KMOD_RCTRL,
    pygame.K_LALT: pygame.KMOD_LALT,
    pygame.K_RALT: pygame.KMOD_RALT,
}


def parse_events(buf):
    """Split a raw read() from an evdev node into (type, code, value) tuples."""
    out = []
    for off in range(0, len(buf) - _EV_SIZE + 1, _EV_SIZE):
        _sec, _usec, etype, code, value = struct.unpack_from(_EV_FORMAT, buf, off)
        out.append((etype, code, value))
    return out


def key_devices():
    """Event node paths for every device that advertises EV_KEY.

    Parsed out of /proc/bus/input/devices so we do not need ioctl bindings.
    Falls back to every event node if that file cannot be read.
    """
    found = []
    try:
        with open("/proc/bus/input/devices", "r") as fh:
            blocks = fh.read().split("\n\n")
    except OSError:
        return sorted(glob.glob("/dev/input/event*"))

    for block in blocks:
        handlers = ""
        name = ""
        ev_mask = 0
        for line in block.splitlines():
            if line.startswith("N: Name="):
                name = line.split("=", 1)[1].strip().strip('"')
            elif line.startswith("H: Handlers="):
                handlers = line.split("=", 1)[1]
            elif line.startswith("B: EV="):
                try:
                    ev_mask = int(line.split("=", 1)[1].strip(), 16)
                except ValueError:
                    ev_mask = 0
        if not (ev_mask & EV_KEY_BIT):
            continue
        for token in handlers.split():
            if token.startswith("event"):
                found.append(("/dev/input/" + token, name))
    return found


class _Bridge:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.fds = {}          # path -> open file object
        self.names = {}        # path -> friendly name
        self.mods = 0
        self._stop = threading.Event()
        self._last_scan = 0.0

    # -- device management -------------------------------------------------

    def scan(self):
        self._last_scan = time.time()
        wanted = key_devices()
        want_paths = set(p for p, _n in wanted)

        for path in list(self.fds):
            if path not in want_paths:
                self._close(path)

        for path, name in wanted:
            if path in self.fds:
                continue
            try:
                fh = open(path, "rb", buffering=0)
                os.set_blocking(fh.fileno(), False)
            except OSError as exc:
                if self.verbose:
                    print("inputbridge: cannot open %s (%s)" % (path, exc))
                continue
            self.fds[path] = fh
            self.names[path] = name
            if self.verbose:
                print("inputbridge: reading %s (%s)" % (path, name or "unnamed"))

    def _close(self, path):
        fh = self.fds.pop(path, None)
        self.names.pop(path, None)
        if fh is not None:
            try:
                fh.close()
            except OSError:
                pass

    # -- event translation -------------------------------------------------

    def _unicode_for(self, key):
        ch = _UNSHIFTED.get(key)
        if ch is None:
            return ""
        shifted = bool(self.mods & (pygame.KMOD_LSHIFT | pygame.KMOD_RSHIFT))
        if not shifted:
            return ch
        if ch.isalpha():
            return ch.upper()
        return _SHIFTED.get(ch, ch)

    def handle(self, etype, code, value):
        if etype != EV_KEY:
            return
        key = _KEYMAP.get(code) or _BTNMAP.get(code)
        if key is None:
            return

        bit = _MODBITS.get(key)
        if bit:
            if value:
                self.mods |= bit
            else:
                self.mods &= ~bit

        # value 1 = press, 2 = autorepeat, 0 = release
        if value in (1, 2):
            etype_pg = pygame.KEYDOWN
        elif value == 0:
            etype_pg = pygame.KEYUP
        else:
            return

        if self.verbose:
            print("inputbridge: code=%d -> key=%d %s"
                  % (code, key, "down" if etype_pg == pygame.KEYDOWN else "up"))
            return

        if not pygame.get_init():
            return
        try:
            pygame.event.post(pygame.event.Event(
                etype_pg,
                key=key,
                mod=self.mods,
                unicode=self._unicode_for(key) if etype_pg == pygame.KEYDOWN else "",
                scancode=code,
            ))
        except Exception:
            # A full queue must never take the launcher down.
            pass

    # -- main loop ---------------------------------------------------------

    def run(self):
        self.scan()
        while not self._stop.is_set():
            if time.time() - self._last_scan > RESCAN_SECONDS:
                self.scan()
            if not self.fds:
                time.sleep(SELECT_TIMEOUT)
                continue
            try:
                ready, _, _ = select.select(list(self.fds.values()), [], [],
                                            SELECT_TIMEOUT)
            except (OSError, ValueError):
                self.scan()
                continue
            for fh in ready:
                path = next((p for p, f in self.fds.items() if f is fh), None)
                try:
                    data = fh.read(_EV_SIZE * 64)
                except OSError:
                    if path:
                        self._close(path)   # device unplugged mid-read
                    continue
                if not data:
                    continue
                for etype, code, value in parse_events(data):
                    self.handle(etype, code, value)

    def stop(self):
        self._stop.set()


_thread = None
_bridge = None


def start(verbose=False):
    """Start the bridge once. Safe to call repeatedly."""
    global _thread, _bridge
    if _thread is not None and _thread.is_alive():
        return _thread
    _bridge = _Bridge(verbose=verbose)
    _thread = threading.Thread(target=_bridge.run, name="inputbridge", daemon=True)
    _thread.start()
    return _thread


def stop():
    if _bridge is not None:
        _bridge.stop()


if __name__ == "__main__":
    print("inputbridge self test. Press keys, Ctrl-C to quit.")
    devs = key_devices()
    if not devs:
        print("NO KEY-CAPABLE INPUT DEVICES FOUND.")
        print("Check /proc/bus/input/devices and that the keyboard is connected.")
    for p, n in devs:
        print("  %s  %s" % (p, n or "unnamed"))
    b = _Bridge(verbose=True)
    try:
        b.run()
    except KeyboardInterrupt:
        print("\nbye")
