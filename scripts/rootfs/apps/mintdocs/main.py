#!/usr/bin/env python3
# rootfs/apps/mintdocs/main.py -- MintDocs v1.0
import os, sys, json, textwrap
from pathlib import Path

IS_LINUX = sys.platform == "linux"
if IS_LINUX:
    os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")
    os.environ.setdefault("SDL_AUDIODRIVER", "alsa")

import pygame

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "launcher"))
import themes as th

SCREEN_W, SCREEN_H = 640, 480
FPS     = 30
PAD     = 14
HEADER  = 36
FOOTER  = 34
LINE_H  = 18
COLS    = (SCREEN_W - PAD * 2) // 8   # monospace char width ~8px
VIS     = (SCREEN_H - HEADER - FOOTER) // LINE_H

DATA_DIR  = Path(os.environ.get("MINTKIT_DATA", Path.home() / ".mintkit"))
DOCS_DIR  = DATA_DIR / "docs"
PROG_FILE = DATA_DIR / "docs_progress.json"

def load_progress():
    if PROG_FILE.exists():
        try: return json.loads(PROG_FILE.read_text())
        except Exception: pass
    return {}

def save_progress(prog):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROG_FILE.write_text(json.dumps(prog, indent=2))

def list_docs():
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(DOCS_DIR.glob("*.md")) + sorted(DOCS_DIR.glob("*.txt"))
    return files

def render_markdown(text: str) -> list:
    """Very simple markdown -> list of (line_str, is_heading, is_code) tuples."""
    lines = []
    in_code = False
    for raw in text.splitlines():
        if raw.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            lines.append((raw, False, True))
            continue
        if raw.startswith("# "):
            lines.append((raw[2:].upper(), True, False))
        elif raw.startswith("## "):
            lines.append(("  " + raw[3:].upper(), True, False))
        elif raw.startswith("### "):
            lines.append(("    " + raw[4:], True, False))
        else:
            # Word-wrap
            stripped = raw.lstrip("-* ")
            prefix   = "• " if raw.startswith(("- ", "* ")) else ""
            for i, chunk in enumerate(textwrap.wrap(stripped or " ", COLS - len(prefix)) or [" "]):
                lines.append(((prefix if i == 0 else "  ") + chunk, False, False))
    return lines

pygame.init()
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("MintDocs")
clock  = pygame.time.Clock()
font_lg = pygame.font.SysFont("monospace", 15, bold=True)
font_nm = pygame.font.SysFont("monospace", 13)
font_sm = pygame.font.SysFont("monospace", 11)
pygame.key.set_repeat(400, 60)

files    = list_docs()
progress = load_progress()
view     = "list"   # "list" | "doc"
sel      = 0
scroll   = 0
doc_lines = []
doc_name  = ""

def open_doc(path):
    global doc_lines, doc_name, scroll, view
    text = path.read_text(errors="replace")
    doc_lines = render_markdown(text)
    doc_name  = path.name
    scroll    = progress.get(str(path), 0)
    view      = "doc"

def draw():
    p = th.get()
    screen.fill(p["bg"])
    pygame.draw.rect(screen, p["bar"], (0, 0, SCREEN_W, HEADER))
    pygame.draw.line(screen, p["border"], (0, HEADER), (SCREEN_W, HEADER))
    heading = doc_name if view == "doc" else "MintDocs"
    ht = font_lg.render(heading[:40], True, p["accent"])
    screen.blit(ht, (PAD, (HEADER - ht.get_height()) // 2))
    if view == "doc":
        pct = font_sm.render(f"{min(100, scroll * 100 // max(1, len(doc_lines) - VIS))}%", True, p["dim"])
        screen.blit(pct, (SCREEN_W - pct.get_width() - PAD, (HEADER - pct.get_height()) // 2))
        for i, (line, is_h, is_code) in enumerate(doc_lines[scroll:scroll + VIS]):
            y = HEADER + i * LINE_H
            col = p["accent"] if is_h else (p["dim"] if is_code else p["white"])
            f   = font_lg if is_h else font_nm
            screen.blit(f.render(line[:COLS], True, col), (PAD, y))
    else:
        y = HEADER + PAD
        for i, fpath in enumerate(files):
            sel_row = (i == sel)
            col = p["accent"] if sel_row else p["white"]
            marker = "> " if sel_row else "  "
            screen.blit(font_nm.render(marker + fpath.name[:50], True, col), (PAD, y))
            y += LINE_H + 4
        if not files:
            msg = font_nm.render("No docs — copy .md/.txt to ~/.mintkit/docs/", True, p["dim"])
            screen.blit(msg, (PAD, SCREEN_H // 2))
    pygame.draw.line(screen, p["border"], (0, SCREEN_H - FOOTER), (SCREEN_W, SCREEN_H - FOOTER))
    hints = [("↑↓", "SCROLL"), ("Esc", "BACK")] if view == "doc" else [("Z", "OPEN"), ("Esc", "QUIT")]
    hx = 6
    for key, act in hints:
        ki = font_sm.render(key, True, p["black"]); kw = ki.get_width() + 8
        pygame.draw.rect(screen, p["accent"], (hx, SCREEN_H - 26, kw, 18))
        screen.blit(ki, (hx + 4, SCREEN_H - 24)); hx += kw + 4
        ai = font_sm.render(act, True, p["dim"])
        screen.blit(ai, (hx, SCREEN_H - 24)); hx += ai.get_width() + 12

running = True
while running:
    clock.tick(FPS)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if view == "list":
                if event.key in (pygame.K_UP, pygame.K_w): sel = max(0, sel - 1)
                elif event.key in (pygame.K_DOWN, pygame.K_s): sel = min(len(files) - 1, sel + 1)
                elif event.key in (pygame.K_RETURN, pygame.K_z):
                    if files: open_doc(files[sel])
                elif event.key in (pygame.K_ESCAPE, pygame.K_b): running = False
            else:
                if event.key in (pygame.K_UP, pygame.K_w): scroll = max(0, scroll - 1)
                elif event.key in (pygame.K_DOWN, pygame.K_s): scroll = min(max(0, len(doc_lines) - VIS), scroll + 1)
                elif event.key == pygame.K_PAGEDOWN: scroll = min(max(0, len(doc_lines) - VIS), scroll + VIS)
                elif event.key == pygame.K_PAGEUP: scroll = max(0, scroll - VIS)
                elif event.key in (pygame.K_ESCAPE, pygame.K_b):
                    progress[str(files[sel])] = scroll
                    save_progress(progress)
                    view = "list"
    draw()
    pygame.display.flip()

pygame.quit()