#!/usr/bin/env python3
# rootfs/apps/mintshell/main.py -- MintShell v1.0
# Terminal emulator for MintKit OS
import os, sys, platform, subprocess, shlex, threading
from collections import deque

IS_LINUX = platform.system() == "Linux"
if IS_LINUX:
    os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")
    os.environ.setdefault("SDL_AUDIODRIVER", "alsa")

import pygame

# ── Constants ────────────────────────────────────────────────────────────────
SCREEN_W, SCREEN_H = 640, 480
FPS = 60
BG       = (10,  26,  16)
ACCENT   = (61, 204, 112)
DIM      = (40, 120,  65)
WHITE    = (180, 240, 195)
ERROR    = (220,  80,  60)
BAR      = ( 6,  13,   8)
BORDER   = (29, 100,  55)
CURSOR   = (61, 204, 112)

FONT_SIZE   = 14
LINE_H      = 18
PAD         = 8
INPUT_H     = 28
HEADER_H    = 28
OUTPUT_Y    = HEADER_H + PAD
OUTPUT_H    = SCREEN_H - HEADER_H - INPUT_H - PAD * 3
MAX_LINES   = 500

# ── Shell state ──────────────────────────────────────────────────────────────
cwd        = os.path.expanduser("~")
history    = deque(maxlen=100)
hist_idx   = -1
lines      = deque(maxlen=MAX_LINES)   # (text, color)
input_buf  = ""
cursor_vis = True
cursor_tmr = 0
scroll_off = 0   # lines scrolled up from bottom
running_proc = None

def push(text, color=None):
    color = color or WHITE
    for chunk in (text.split("\n") if "\n" in text else [text]):
        lines.append((chunk, color))

def prompt():
    home = os.path.expanduser("~")
    display = cwd.replace(home, "~") if cwd.startswith(home) else cwd
    return f"mintkit@pocketmint:{display}$ "

def run_command(cmd_str):
    global cwd, running_proc
    cmd_str = cmd_str.strip()
    if not cmd_str:
        push(prompt())
        return

    push(prompt() + cmd_str, ACCENT)

    # Built-ins
    if cmd_str == "clear":
        lines.clear()
        return
    if cmd_str == "exit" or cmd_str == "quit":
        pygame.event.post(pygame.event.Event(pygame.QUIT))
        return
    if cmd_str.startswith("cd"):
        parts = cmd_str.split(None, 1)
        target = parts[1] if len(parts) > 1 else os.path.expanduser("~")
        target = os.path.expandvars(os.path.expanduser(target))
        if not os.path.isabs(target):
            target = os.path.join(cwd, target)
        target = os.path.normpath(target)
        if os.path.isdir(target):
            cwd = target
        else:
            push(f"cd: {target}: No such file or directory", ERROR)
        push("")
        return

    # External command
    def _run():
        global running_proc
        try:
            proc = subprocess.Popen(
                cmd_str, shell=True, cwd=cwd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1
            )
            running_proc = proc
            for line in proc.stdout:
                push(line.rstrip())
            proc.wait()
            if proc.returncode != 0:
                push(f"[exited {proc.returncode}]", DIM)
        except Exception as e:
            push(str(e), ERROR)
        finally:
            running_proc = None
            push("")

    t = threading.Thread(target=_run, daemon=True)
    t.start()

# ── pygame init ──────────────────────────────────────────────────────────────
pygame.init()
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("MintShell")
clock  = pygame.time.Clock()
font   = pygame.font.SysFont("monospace", FONT_SIZE)
pygame.key.set_repeat(400, 40)

push("MintShell v1.0 — type 'exit' to return to launcher", ACCENT)
push("")

# ── Main loop ────────────────────────────────────────────────────────────────
while True:
    dt = clock.tick(FPS)
    cursor_tmr += dt
    if cursor_tmr >= 500:
        cursor_vis = not cursor_vis
        cursor_tmr = 0

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit(); sys.exit()

        elif event.type == pygame.KEYDOWN:
            mods = pygame.key.get_mods()

            # Ctrl+C — kill running process
            if event.key == pygame.K_c and mods & pygame.KMOD_CTRL:
                if running_proc:
                    running_proc.kill()
                    push("^C", ERROR)
                else:
                    input_buf = ""
                    push(prompt() + "^C", ERROR)
                cursor_vis = True; cursor_tmr = 0

            # Ctrl+L — clear
            elif event.key == pygame.K_l and mods & pygame.KMOD_CTRL:
                lines.clear()

            # Enter
            elif event.key == pygame.K_RETURN:
                if input_buf:
                    history.appendleft(input_buf)
                hist_idx = -1
                run_command(input_buf)
                input_buf = ""
                scroll_off = 0
                cursor_vis = True; cursor_tmr = 0

            # Backspace
            elif event.key == pygame.K_BACKSPACE:
                input_buf = input_buf[:-1]
                cursor_vis = True; cursor_tmr = 0

            # History up
            elif event.key == pygame.K_UP:
                if history:
                    hist_idx = min(hist_idx + 1, len(history) - 1)
                    input_buf = history[hist_idx]

            # History down
            elif event.key == pygame.K_DOWN:
                if hist_idx > 0:
                    hist_idx -= 1
                    input_buf = history[hist_idx]
                else:
                    hist_idx = -1
                    input_buf = ""

            # Scroll output
            elif event.key == pygame.K_PAGEUP:
                scroll_off = min(scroll_off + 5, max(0, len(lines) - 1))
            elif event.key == pygame.K_PAGEDOWN:
                scroll_off = max(scroll_off - 5, 0)

            # Tab (basic autocomplete)
            elif event.key == pygame.K_TAB:
                parts = input_buf.rsplit(" ", 1)
                stub = parts[-1]
                base = os.path.join(cwd, os.path.dirname(stub))
                prefix = os.path.basename(stub)
                try:
                    matches = [f for f in os.listdir(base or cwd) if f.startswith(prefix)]
                    if len(matches) == 1:
                        completed = os.path.join(os.path.dirname(stub), matches[0])
                        parts[-1] = completed
                        input_buf = " ".join(parts)
                    elif len(matches) > 1:
                        push("  ".join(matches), DIM)
                except Exception:
                    pass

            # Printable
            elif event.unicode and event.unicode.isprintable():
                input_buf += event.unicode
                cursor_vis = True; cursor_tmr = 0

    # ── Draw ─────────────────────────────────────────────────────────────────
    screen.fill(BG)

    # Header bar
    pygame.draw.rect(screen, BAR, (0, 0, SCREEN_W, HEADER_H))
    pygame.draw.line(screen, BORDER, (0, HEADER_H), (SCREEN_W, HEADER_H))
    title_surf = font.render("MintShell  |  " + cwd.replace(os.path.expanduser("~"), "~"), True, ACCENT)
    screen.blit(title_surf, (PAD, (HEADER_H - title_surf.get_height()) // 2))

    # Output area — work out visible lines
    visible = int(OUTPUT_H // LINE_H)
    all_lines = list(lines)
    total = len(all_lines)
    end_idx = max(0, total - scroll_off)
    start_idx = max(0, end_idx - visible)
    visible_lines = all_lines[start_idx:end_idx]

    y = OUTPUT_Y
    for text, color in visible_lines:
        surf = font.render(text, True, color)
        screen.blit(surf, (PAD, y))
        y += LINE_H

    # Scroll indicator
    if scroll_off > 0:
        ind = font.render(f" ▲ {scroll_off} lines ", True, BAR, ACCENT)
        screen.blit(ind, (SCREEN_W - ind.get_width() - PAD, OUTPUT_Y))

    # Input bar
    input_y = SCREEN_H - INPUT_H - PAD
    pygame.draw.rect(screen, BAR, (0, input_y - 2, SCREEN_W, INPUT_H + 4))
    pygame.draw.line(screen, BORDER, (0, input_y - 2), (SCREEN_W, input_y - 2))
    prompt_str = prompt()
    prompt_surf = font.render(prompt_str, True, DIM)
    screen.blit(prompt_surf, (PAD, input_y + (INPUT_H - prompt_surf.get_height()) // 2))
    input_x = PAD + prompt_surf.get_width()
    input_surf = font.render(input_buf, True, WHITE)
    screen.blit(input_surf, (input_x, input_y + (INPUT_H - input_surf.get_height()) // 2))
    if cursor_vis:
        cx = input_x + input_surf.get_width()
        cy = input_y + (INPUT_H - LINE_H) // 2
        pygame.draw.rect(screen, CURSOR, (cx, cy, 2, LINE_H))

    pygame.display.flip()

pygame.quit()