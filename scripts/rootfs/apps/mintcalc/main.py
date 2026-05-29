#!/usr/bin/env python3
# rootfs/apps/mintcalc/main.py -- Calculator & Unit Converter v1.0
import os, sys, math
from pathlib import Path

IS_LINUX = sys.platform == "linux"
if IS_LINUX:
    os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")
    os.environ.setdefault("SDL_AUDIODRIVER", "alsa")

import pygame

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "launcher"))
import themes as th

SCREEN_W, SCREEN_H = 640, 480
FPS    = 30
PAD    = 12
HEADER = 36
TAB_H  = 26
FOOTER = 34

# ── Safe evaluator ────────────────────────────────────────────────────────
import ast, operator as op

ALLOWED_OPS = {
    ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul,
    ast.Div: op.truediv, ast.Pow: op.pow, ast.Mod: op.mod,
    ast.USub: op.neg,
}
ALLOWED_FUNCS = {
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "sqrt": math.sqrt, "log": math.log, "abs": abs,
    "pi": math.pi, "e": math.e,
}

def safe_eval(expr: str):
    def _eval(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        elif isinstance(node, ast.Name) and node.id in ALLOWED_FUNCS:
            return ALLOWED_FUNCS[node.id]
        elif isinstance(node, ast.BinOp) and type(node.op) in ALLOWED_OPS:
            return ALLOWED_OPS[type(node.op)](_eval(node.left), _eval(node.right))
        elif isinstance(node, ast.UnaryOp) and type(node.op) in ALLOWED_OPS:
            return ALLOWED_OPS[type(node.op)](_eval(node.operand))
        elif isinstance(node, ast.Call):
            fn = _eval(node.func)
            return fn(*[_eval(a) for a in node.args])
        raise ValueError(f"Unsupported: {type(node).__name__}")
    tree = ast.parse(expr.replace("^", "**"), mode="eval")
    return _eval(tree.body)

# ── Unit conversions ──────────────────────────────────────────────────────
CONVERT_GROUPS = [
    ("Length", "m", [
        ("mm",  0.001), ("cm",  0.01), ("m",   1.0), ("km",  1000.0),
        ("in",  0.0254), ("ft", 0.3048), ("mi", 1609.344),
    ]),
    ("Weight", "kg", [
        ("mg",  1e-6), ("g",  0.001), ("kg",  1.0), ("lb",  0.453592), ("oz", 0.0283495),
    ]),
    ("Temp", "C", None),  # handled specially
    ("Speed", "m/s", [
        ("m/s",  1.0), ("km/h", 1/3.6), ("mph", 0.44704), ("kn", 0.514444),
    ]),
    ("Data", "bytes", [
        ("B",    1), ("KB", 1024), ("MB", 1024**2), ("GB", 1024**3), ("TB", 1024**4),
    ]),
]

def convert_temp(val, from_u, to_u):
    if from_u == to_u: return val
    c = val if from_u == "C" else (val - 32) * 5/9 if from_u == "F" else val - 273.15
    return c if to_u == "C" else c * 9/5 + 32 if to_u == "F" else c + 273.15

# ── State ──────────────────────────────────────────────────────────────────
pygame.init()
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("Calculator")
clock   = pygame.time.Clock()
font_lg = pygame.font.SysFont("monospace", 15, bold=True)
font_xl = pygame.font.SysFont("monospace", 22, bold=True)
font_sm = pygame.font.SysFont("monospace", 11)
pygame.key.set_repeat(400, 60)

tab       = 0  # 0=CALC 1=CONVERT
expr      = ""
result    = ""
error     = False
history   = []

cv_group  = 0
cv_from   = 0
cv_to     = 1
cv_input  = ""
cv_result = ""
cv_focus  = 0   # 0=input, 1=from, 2=to

TEMP_UNITS = ["C", "F", "K"]

def do_calc():
    global result, error
    try:
        r = safe_eval(expr)
        if isinstance(r, float) and r == int(r): r = int(r)
        result = str(round(r, 10)) if isinstance(r, float) else str(r)
        history.insert(0, f"{expr} = {result}")
        if len(history) > 6: history.pop()
        error = False
    except Exception as ex:
        result = "Error"
        error  = True

def do_convert():
    global cv_result
    grp_name, _, units = CONVERT_GROUPS[cv_group]
    try:
        val = float(cv_input)
    except Exception:
        cv_result = ""
        return
    if grp_name == "Temp":
        fu = TEMP_UNITS[cv_from % 3]
        tu = TEMP_UNITS[cv_to   % 3]
        r  = convert_temp(val, fu, tu)
    else:
        f_factor = units[cv_from % len(units)][1]
        t_factor = units[cv_to   % len(units)][1]
        r = val * f_factor / t_factor
    cv_result = f"{round(r, 6):g}"

def draw():
    p = th.get()
    screen.fill(p["bg"])
    pygame.draw.rect(screen, p["bar"], (0, 0, SCREEN_W, HEADER))
    pygame.draw.line(screen, p["border"], (0, HEADER), (SCREEN_W, HEADER))
    title = font_lg.render("Calculator", True, p["accent"])
    screen.blit(title, (PAD, (HEADER - title.get_height()) // 2))
    # Tabs
    tw = SCREEN_W // 2
    for i, name in enumerate(["CALC", "CONVERT"]):
        col = p["accent"] if i == tab else p["locked"]
        pygame.draw.rect(screen, p["bar"], (i * tw, HEADER, tw, TAB_H))
        if i == tab:
            pygame.draw.rect(screen, p["accent"], (i * tw, HEADER + TAB_H - 2, tw, 2))
        t = font_sm.render(name, True, col)
        screen.blit(t, (i * tw + tw // 2 - t.get_width() // 2, HEADER + (TAB_H - t.get_height()) // 2))
    pygame.draw.line(screen, p["border"], (0, HEADER + TAB_H), (SCREEN_W, HEADER + TAB_H))

    cy = HEADER + TAB_H + PAD

    if tab == 0:
        # Display
        pygame.draw.rect(screen, p["card"], (PAD, cy, SCREEN_W - PAD * 2, 60), border_radius=4)
        col = (220, 60, 60) if error else p["white"]
        et = font_xl.render((expr or "0")[-22:] + "_", True, p["dim"])
        rt = font_xl.render(result or " ", True, col)
        screen.blit(et, (SCREEN_W - et.get_width() - PAD * 2, cy + 4))
        screen.blit(rt, (SCREEN_W - rt.get_width() - PAD * 2, cy + 30))
        cy += 68
        for h in history:
            ht = font_sm.render(h[:56], True, p["dim"])
            screen.blit(ht, (PAD, cy)); cy += 18
    else:
        grp_name, _, units = CONVERT_GROUPS[cv_group]
        is_temp = grp_name == "Temp"
        unit_list = TEMP_UNITS if is_temp else [u[0] for u in units]
        from_u = unit_list[cv_from % len(unit_list)]
        to_u   = unit_list[cv_to   % len(unit_list)]
        # Group selector
        gt = font_lg.render(f"< {grp_name} >", True, p["accent"])
        screen.blit(gt, (SCREEN_W // 2 - gt.get_width() // 2, cy)); cy += 32
        # Input
        for label, val, idx in [(f"From ({from_u})", cv_input, 0),
                                 (f"To   ({to_u})",  cv_result, 2)]:
            sel = (cv_focus == idx) and idx == 0
            bg  = tuple(min(255, c + 15) for c in p["card"]) if sel else p["card"]
            pygame.draw.rect(screen, bg, (PAD, cy, SCREEN_W - PAD * 2, 44), border_radius=4)
            if sel:
                pygame.draw.rect(screen, p["accent"], (PAD, cy, SCREEN_W - PAD * 2, 44), 1, border_radius=4)
            screen.blit(font_sm.render(label, True, p["dim"]), (PAD + 8, cy + 4))
            vt = font_lg.render((val + "_") if sel else val, True, p["white"])
            screen.blit(vt, (PAD + 8, cy + 22)); cy += 52
        # Unit pickers
        screen.blit(font_sm.render("FROM unit: ←→", True, p["dim"]), (PAD, cy)); cy += 20
        screen.blit(font_sm.render("TO unit:   ←→ (hold Tab)", True, p["dim"]), (PAD, cy))

    pygame.draw.line(screen, p["border"], (0, SCREEN_H - FOOTER), (SCREEN_W, SCREEN_H - FOOTER))
    hints = [("0-9", "INPUT"), ("=↵", "CALC"), ("Del", "CLEAR"), ("Esc", "QUIT")] if tab == 0 \
        else [("0-9", "INPUT"), ("←→", "UNIT"), ("Tab", "TO"), ("Esc", "QUIT")]
    hx = 6
    for key, act in hints:
        ki = font_sm.render(key, True, p["black"]); kw = ki.get_width() + 8
        pygame.draw.rect(screen, p["accent"], (hx, SCREEN_H - 26, kw, 18))
        screen.blit(ki, (hx + 4, SCREEN_H - 24)); hx += kw + 4
        ai = font_sm.render(act, True, p["dim"])
        screen.blit(ai, (hx, SCREEN_H - 24)); hx += ai.get_width() + 12

shift = False
running = True
while running:
    clock.tick(FPS)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_TAB:
                if tab == 1: cv_focus = 1 - min(cv_focus, 1)
                else: tab = 1
            elif event.key == pygame.K_ESCAPE:
                running = False
            elif tab == 0:
                if event.unicode and event.unicode in "0123456789.+-*/()^sincotaqrlbep":
                    expr += event.unicode; error = False
                elif event.key in (pygame.K_RETURN, pygame.K_EQUALS): do_calc()
                elif event.key == pygame.K_BACKSPACE: expr = expr[:-1]; error = False
                elif event.key == pygame.K_DELETE: expr = ""; result = ""; error = False
                elif event.key == pygame.K_LEFT: tab = 0
                elif event.key == pygame.K_RIGHT: tab = 1
            else:
                if event.unicode and event.unicode in "0123456789.":
                    cv_input += event.unicode; do_convert()
                elif event.key == pygame.K_BACKSPACE:
                    cv_input = cv_input[:-1]; do_convert()
                elif event.key == pygame.K_DELETE:
                    cv_input = ""; cv_result = ""
                elif event.key == pygame.K_LEFT:
                    if cv_focus == 0: cv_from -= 1
                    elif cv_focus == 1: cv_to -= 1
                    else: cv_group = (cv_group - 1) % len(CONVERT_GROUPS)
                    do_convert()
                elif event.key == pygame.K_RIGHT:
                    if cv_focus == 0: cv_from += 1
                    elif cv_focus == 1: cv_to += 1
                    else: cv_group = (cv_group + 1) % len(CONVERT_GROUPS)
                    do_convert()
                elif event.key == pygame.K_UP:
                    cv_group = (cv_group - 1) % len(CONVERT_GROUPS); do_convert()
                elif event.key == pygame.K_DOWN:
                    cv_group = (cv_group + 1) % len(CONVERT_GROUPS); do_convert()
    draw()
    pygame.display.flip()

pygame.quit()