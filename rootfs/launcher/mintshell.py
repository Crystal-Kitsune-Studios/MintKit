#!/usr/bin/env python3
# rootfs/launcher/mintshell.py -- MintShell terminal (OS built-in)
import os, sys, subprocess, threading, pty, select, signal, fcntl, termios, struct
from pathlib import Path
from . import themes as th

import pygame

SCREEN_W, SCREEN_H = 640, 480
FPS       = 60
COLS      = 80
ROWS      = 24
PAD       = 4
HEADER    = 28
FONT_NAME = "monospace"
FONT_SIZE = 12

# ── Terminal emulator state ──────────────────────────────────────────────────────────
class Screen:
    """Simple VT100-ish screen buffer."""
    def __init__(self, rows, cols):
        self.rows  = rows
        self.cols  = cols
        self.buf   = [[' '] * cols for _ in range(rows)]
        self.cx    = 0   # cursor col
        self.cy    = 0   # cursor row
        self.dirty = True
        self._esc  = ""  # escape sequence accumulator
        self._in_esc = False

    def scroll_up(self):
        self.buf.pop(0)
        self.buf.append([' '] * self.cols)

    def write(self, data: str):
        self.dirty = True
        i = 0
        while i < len(data):
            ch = data[i]
            if self._in_esc:
                self._esc += ch
                # CSI sequence ends on letter
                if self._esc.startswith('[') and ch.isalpha():
                    self._handle_csi(self._esc)
                    self._esc = ""
                    self._in_esc = False
                elif not self._esc.startswith('[') and ch != '[':
                    # simple 2-char escape (e.g. ESC c = reset)
                    self._esc = ""
                    self._in_esc = False
                i += 1
                continue
            if ch == '\x1b':
                self._in_esc = True
                self._esc    = ""
            elif ch == '\r':
                self.cx = 0
            elif ch == '\n':
                self.cy += 1
                if self.cy >= self.rows:
                    self.scroll_up()
                    self.cy = self.rows - 1
            elif ch == '\x08' or ch == '\x7f':  # backspace
                self.cx = max(0, self.cx - 1)
                self.buf[self.cy][self.cx] = ' '
            elif ch == '\x07':  # bell — ignore
                pass
            elif ch >= ' ':  # printable
                if self.cx >= self.cols:
                    self.cx = 0
                    self.cy += 1
                    if self.cy >= self.rows:
                        self.scroll_up()
                        self.cy = self.rows - 1
                self.buf[self.cy][self.cx] = ch
                self.cx += 1
            i += 1

    def _handle_csi(self, seq):
        """Handle a subset of CSI sequences."""
        cmd = seq[-1]
        params_str = seq[1:-1]  # strip leading '[' and trailing command
        if params_str[:1] in ("?", ">", "<", "="):
            return  # private DEC modes such as bracketed paste. Not ours to interpret.
        try:
            params = [int(x) if x else 0 for x in params_str.split(';')] if params_str else [0]
        except ValueError:
            return  # one odd escape must never kill the reader thread

        if cmd == 'H' or cmd == 'f':   # cursor position
            self.cy = max(0, min(self.rows - 1, (params[0] or 1) - 1))
            self.cx = max(0, min(self.cols - 1, (params[1] if len(params) > 1 else 1) - 1))
        elif cmd == 'A':  # cursor up
            self.cy = max(0, self.cy - (params[0] or 1))
        elif cmd == 'B':  # cursor down
            self.cy = min(self.rows - 1, self.cy + (params[0] or 1))
        elif cmd == 'C':  # cursor forward
            self.cx = min(self.cols - 1, self.cx + (params[0] or 1))
        elif cmd == 'D':  # cursor back
            self.cx = max(0, self.cx - (params[0] or 1))
        elif cmd == 'J':  # erase in display
            if params[0] == 2:
                self.buf = [[' '] * self.cols for _ in range(self.rows)]
                self.cx = self.cy = 0
            elif params[0] == 0:
                for c in range(self.cx, self.cols): self.buf[self.cy][c] = ' '
                for r in range(self.cy + 1, self.rows): self.buf[r] = [' '] * self.cols
        elif cmd == 'K':  # erase in line
            if params[0] == 0:
                for c in range(self.cx, self.cols): self.buf[self.cy][c] = ' '
            elif params[0] == 1:
                for c in range(0, self.cx + 1): self.buf[self.cy][c] = ' '
            elif params[0] == 2:
                self.buf[self.cy] = [' '] * self.cols
        elif cmd == 'm':  # SGR — colour (ignore for now, monochrome)
            pass

    def get_lines(self):
        return [''.join(row) for row in self.buf]


# ── PTY shell subprocess ────────────────────────────────────────────────────────────────
class ShellProcess:
    def __init__(self, rows, cols):
        self.rows = rows
        self.cols = cols
        self.alive = False
        self.master_fd = None
        self._thread = None
        self.on_data = None   # callback(str)

    def start(self):
        pid, master_fd = pty.fork()
        if pid == 0:  # child
            os.environ['TERM'] = 'xterm-256color'
            os.environ['COLUMNS'] = str(self.cols)
            os.environ['LINES']   = str(self.rows)
            os.execvp('/bin/bash', ['/bin/bash', '--login'])
            sys.exit(1)
        self.pid       = pid
        self.master_fd = master_fd
        self.alive     = True
        self._set_winsize()
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()

    def _set_winsize(self):
        winsize = struct.pack('HHHH', self.rows, self.cols, 0, 0)
        fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)

    def _reader(self):
        while self.alive:
            try:
                r, _, _ = select.select([self.master_fd], [], [], 0.05)
                if r:
                    data = os.read(self.master_fd, 4096)
                    if data and self.on_data:
                        self.on_data(data.decode('utf-8', errors='replace'))
            except OSError:
                self.alive = False

    def write(self, data: bytes):
        if self.alive and self.master_fd is not None:
            try: os.write(self.master_fd, data)
            except OSError: self.alive = False

    def stop(self):
        self.alive = False
        try:
            os.kill(self.pid, signal.SIGHUP)
        except ProcessLookupError: pass


# ── Pygame key → bytes ────────────────────────────────────────────────────────────────
_SPECIAL = {
    pygame.K_RETURN:    b'\r',
    pygame.K_KP_ENTER:  b'\r',
    pygame.K_BACKSPACE: b'\x7f',
    pygame.K_DELETE:    b'\x1b[3~',
    pygame.K_UP:        b'\x1b[A',
    pygame.K_DOWN:      b'\x1b[B',
    pygame.K_RIGHT:     b'\x1b[C',
    pygame.K_LEFT:      b'\x1b[D',
    pygame.K_HOME:      b'\x1b[H',
    pygame.K_END:       b'\x1b[F',
    pygame.K_PAGEUP:    b'\x1b[5~',
    pygame.K_PAGEDOWN:  b'\x1b[6~',
    pygame.K_TAB:       b'\t',
    pygame.K_ESCAPE:    b'\x1b',  # passes through: nano and vim need it
    pygame.K_F10:       None,      # handled by caller to exit
    pygame.K_F1:        b'\x1bOP',
    pygame.K_F2:        b'\x1bOQ',
    pygame.K_F3:        b'\x1bOR',
    pygame.K_F4:        b'\x1bOS',
}

def key_to_bytes(event) -> bytes | None:
    """Convert a pygame KEYDOWN event to the bytes to send to the shell."""
    mods = event.mod
    ctrl = mods & pygame.KMOD_CTRL

    if event.key in _SPECIAL:
        return _SPECIAL[event.key]  # None signals exit

    if ctrl and event.key == pygame.K_q:
        return None  # Ctrl+Q exits MintShell

    if ctrl and pygame.K_a <= event.key <= pygame.K_z:
        return bytes([event.key - pygame.K_a + 1])  # Ctrl+A = 0x01, etc.

    if event.unicode and event.unicode.isprintable():
        return event.unicode.encode('utf-8')

    return b''  # unknown — send nothing


# ── Main entry point ────────────────────────────────────────────────────────────────
# pygame's SysFont enumerates system fonts by shelling out to fc-list, and
# fontconfig is not installed on PocketMint. So SysFont finds nothing and
# silently falls back to a proportional font, which makes char_w meaningless
# and walks the cursor away from the text. Load a real mono TTF by path.
_MONO_REGULAR = (
    "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
)
_MONO_BOLD = (
    "/usr/share/fonts/truetype/freefont/FreeMonoBold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
)
_FONT_CACHE = {}


def _mono(size, bold=False):
    """A monospace font, loaded by path and cached.

    Cached because the header title was building a new font object every
    frame, which is not free on a Pi Zero.
    """
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    f = None
    for path in (_MONO_BOLD if bold else _MONO_REGULAR):
        if os.path.exists(path):
            f = pygame.font.Font(path, size)
            break
    if f is None:
        f = pygame.font.SysFont(FONT_NAME, size, bold=bold)
    _FONT_CACHE[key] = f
    return f

def run(screen, clock):
    """Called by the launcher. Runs MintShell on the shared SDL screen."""
    global SCREEN_W, SCREEN_H
    SCREEN_W, SCREEN_H = screen.get_size()
    font    = _mono(FONT_SIZE)
    # advance width, not ink width. font.size() includes side bearing, which
    # put the cursor grid one pixel per column ahead of the rendered text.
    _adv = font.metrics("M")
    char_w = _adv[0][4] if (_adv and _adv[0]) else font.size("M" * 40)[0] // 40
    char_h  = font.get_linesize()

    # Fit as many cols/rows as possible inside the content area
    content_h = SCREEN_H - HEADER - PAD * 2
    content_w = SCREEN_W - PAD * 2
    cols = max(20, content_w  // char_w)
    rows = max(5,  content_h  // char_h)

    scr  = Screen(rows, cols)
    proc = ShellProcess(rows, cols)

    lock = threading.Lock()

    def on_data(text):
        with lock:
            scr.write(text)

    proc.on_data = on_data
    proc.start()

    pygame.key.set_repeat(400, 40)
    blink_timer = 0
    cursor_vis  = True
    running     = True

    while running:
        dt = clock.tick(FPS)
        blink_timer += dt
        if blink_timer >= 500:
            cursor_vis  = not cursor_vis
            blink_timer = 0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                b = key_to_bytes(event)
                if b is None:        # Ctrl+Q or F10 → exit MintShell
                    running = False
                elif b:
                    proc.write(b)
                    cursor_vis  = True
                    blink_timer = 0

        p = th.get()
        screen.fill(p['bg'])

        # ── Header bar ──────────────────────────────────────────────────
        pygame.draw.rect(screen, p['bar'], (0, 0, SCREEN_W, HEADER))
        pygame.draw.line(screen, p['border'], (0, HEADER), (SCREEN_W, HEADER))
        icon = font.render('\U0001f5a5', True, p['accent'])   # 🖥
        title = _mono(FONT_SIZE, bold=True).render(
            'MintShell', True, p['accent'])
        screen.blit(icon,  (PAD, (HEADER - icon.get_height())  // 2))
        screen.blit(title, (PAD + icon.get_width() + 4,
                             (HEADER - title.get_height()) // 2))
        hint = font.render('Ctrl+Q → back', True, p['dim'])
        screen.blit(hint, (SCREEN_W - hint.get_width() - PAD,
                            (HEADER - hint.get_height()) // 2))

        # ── Terminal buffer ────────────────────────────────────────────────
        with lock:
            lines = scr.get_lines()
            cx, cy = scr.cx, scr.cy

        for row_i, line in enumerate(lines):
            y = HEADER + PAD + row_i * char_h
            # Render line in chunks (optimisation: skip blank lines)
            if line.strip():
                surf = font.render(line, True, p['white'])
                screen.blit(surf, (PAD, y))

        # Blinking block cursor
        if cursor_vis and proc.alive:
            cx_px = PAD  + cx * char_w
            cy_px = HEADER + PAD + cy * char_h
            pygame.draw.rect(screen, p['accent'],
                             (cx_px, cy_px, char_w, char_h))
            if 0 <= cy < len(lines) and 0 <= cx < len(lines[cy]):
                ch = lines[cy][cx]
                if ch.strip():
                    cs = font.render(ch, True, p['bg'])
                    screen.blit(cs, (cx_px, cy_px))

        # Dead shell notice
        if not proc.alive:
            msg = font.render('[shell exited — press Ctrl+Q]', True, p['dim'])
            screen.blit(msg, (PAD, SCREEN_H - PAD - char_h))

        pygame.display.flip()

    proc.stop()
    pygame.key.set_repeat(400, 60)  # restore launcher repeat