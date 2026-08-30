#!/usr/bin/env python3
"""MintCalc -- MintKit built-in calculator, basic and scientific modes.

Launcher entry point:

    from launcher import mintcalc
    mintcalc.run(screen, clock)

Design notes:
  * pygame and launcher.themes are imported lazily inside run(), so that the
    boot-time 'from launcher import mintcalc' in mintos.py stays cheap and
    headless-safe. Nothing at module scope touches the display.
  * Expressions go through an ast whitelist. Never eval() on raw input.
  * No surface is allocated per frame and the screen is only redrawn when
    state actually changes. This board has 357 MB of RAM, act accordingly.
"""

import ast
import math
import operator

VERSION = "MintCalc 1.0"
MAX_EXPR = 72

_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.FloorDiv: operator.floordiv,
}

_UNARYOPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}

_FUNCS = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "sqrt": math.sqrt,
    "log": math.log10,
    "ln": math.log,
    "exp": math.exp,
    "abs": abs,
    "floor": math.floor,
    "ceil": math.ceil,
    "radians": math.radians,
    "degrees": math.degrees,
}

_CONSTS = {"pi": math.pi, "e": math.e, "tau": math.tau}


class CalcError(Exception):
    pass


def _eval_node(node):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            raise CalcError("bad value")
        if not isinstance(node.value, (int, float)):
            raise CalcError("bad value")
        return node.value
    if isinstance(node, ast.BinOp):
        fn = _BINOPS.get(type(node.op))
        if fn is None:
            raise CalcError("bad operator")
        return fn(_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp):
        fn = _UNARYOPS.get(type(node.op))
        if fn is None:
            raise CalcError("bad operator")
        return fn(_eval_node(node.operand))
    if isinstance(node, ast.Name):
        if node.id in _CONSTS:
            return _CONSTS[node.id]
        raise CalcError("unknown name")
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise CalcError("unknown function")
        fn = _FUNCS.get(node.func.id)
        if fn is None:
            raise CalcError("unknown function")
        if node.keywords:
            raise CalcError("no keywords")
        return fn(*[_eval_node(a) for a in node.args])
    raise CalcError("bad expression")


def format_number(value):
    """Human readable result string."""
    if isinstance(value, int):
        return str(value)
    if value != value:
        return "undefined"
    if value in (float("inf"), float("-inf")):
        return "undefined"
    if abs(value) >= 1e12 or (value != 0 and abs(value) < 1e-9):
        return "%.6e" % value
    text = ("%.10f" % value).rstrip("0").rstrip(".")
    return text if text not in ("", "-") else "0"


def evaluate(expr):
    """Evaluate an expression string. Always returns a string, never raises."""
    text = (expr or "").strip().replace("^", "**")
    if not text:
        return ""
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError:
        return "syntax error"
    except (ValueError, MemoryError, RecursionError):
        return "bad expression"
    try:
        value = _eval_node(tree)
    except ZeroDivisionError:
        return "div by zero"
    except CalcError as exc:
        return str(exc)
    except (ValueError, OverflowError, TypeError, RecursionError):
        return "math error"
    return format_number(value)


# ── Keypad layouts ─────────────────────────────────────────────────────────
# Each cell is (label, inserted_text). "=", "C" and "DEL" are actions.

BASIC_PAD = (
    (("7", "7"), ("8", "8"), ("9", "9"), ("/", "/")),
    (("4", "4"), ("5", "5"), ("6", "6"), ("*", "*")),
    (("1", "1"), ("2", "2"), ("3", "3"), ("-", "-")),
    (("0", "0"), (".", "."), ("=", "="), ("+", "+")),
)

SCI_PAD = (
    (("sin", "sin("), ("cos", "cos("), ("tan", "tan("), ("^", "^")),
    (("sqrt", "sqrt("), ("log", "log("), ("ln", "ln("), ("%", "%")),
    (("pi", "pi"), ("e", "e"), ("(", "("), (")", ")")),
    (("C", "C"), ("DEL", "DEL"), ("=", "="), ("+", "+")),
)

PADS = (("BASIC", BASIC_PAD), ("SCI", SCI_PAD))


def _palette():
    """Theme colors, with MintKit defaults if themes is unavailable."""
    pal = {}
    try:
        from launcher import themes as _th

        pal = _th.get() or {}
    except Exception:
        pal = {}
    return {
        "bg": pal.get("bg", (10, 26, 16)),
        "panel": pal.get("panel", (29, 100, 55)),
        "accent": pal.get("accent", (61, 204, 112)),
        "text": pal.get("text", (180, 240, 195)),
        "dim": pal.get("dim", (90, 150, 105)),
        "gold": pal.get("gold", (240, 200, 60)),
    }


def run(screen, clock=None):
    """Run MintCalc on an existing pygame surface. Returns on exit."""
    import pygame

    col = _palette()
    w, h = screen.get_size()

    font_big = pygame.font.Font(None, 56)
    font_mid = pygame.font.Font(None, 38)
    font_sml = pygame.font.Font(None, 26)

    expr = ""
    result = ""
    mode = 0
    row = 0
    cell = 0
    dirty = True
    running = True

    pad_x, pad_y = 40, 170
    cell_w, cell_h = 130, 62
    gap = 12

    def insert(text):
        nonlocal expr, result
        if len(expr) + len(text) <= MAX_EXPR:
            expr += text
            result = ""

    def activate(label, payload):
        nonlocal expr, result
        if label == "=":
            result = evaluate(expr)
        elif label == "C":
            expr = ""
            result = ""
        elif label == "DEL":
            expr = expr[:-1]
            result = ""
        else:
            insert(payload)

    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
                break
            if ev.type != pygame.KEYDOWN:
                continue

            dirty = True
            key = ev.key
            pad = PADS[mode][1]

            if key in (pygame.K_ESCAPE, pygame.K_HOME):
                running = False
            elif key == pygame.K_TAB:
                mode = (mode + 1) % len(PADS)
                row = min(row, len(PADS[mode][1]) - 1)
                cell = min(cell, len(PADS[mode][1][row]) - 1)
            elif key == pygame.K_UP:
                row = (row - 1) % len(pad)
            elif key == pygame.K_DOWN:
                row = (row + 1) % len(pad)
            elif key == pygame.K_LEFT:
                cell = (cell - 1) % len(pad[row])
            elif key == pygame.K_RIGHT:
                cell = (cell + 1) % len(pad[row])
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                activate(*pad[row][cell])
            elif key == pygame.K_BACKSPACE:
                expr = expr[:-1]
                result = ""
            elif key == pygame.K_DELETE:
                expr = ""
                result = ""
            elif key == pygame.K_EQUALS:
                result = evaluate(expr)
            else:
                ch = ev.unicode or ""
                if ch and ch in "0123456789.+-*/%^()":
                    insert(ch)
                elif ch in ("p",):
                    insert("pi")
                elif ch in ("s",):
                    insert("sqrt(")

        if not running:
            break

        if dirty:
            screen.fill(col["bg"])

            title = font_sml.render(
                "MINTCALC  %s" % PADS[mode][0], True, col["accent"]
            )
            screen.blit(title, (40, 32))
            hint = font_sml.render(
                "TAB mode   ENTER press   BKSP delete   ESC exit",
                True,
                col["dim"],
            )
            screen.blit(hint, (40, h - 40))

            pygame.draw.rect(
                screen, col["panel"], pygame.Rect(36, 66, w - 72, 88), 2
            )
            shown = expr[-28:] if len(expr) > 28 else expr
            screen.blit(
                font_mid.render(shown or "0", True, col["text"]), (52, 78)
            )
            if result:
                res = font_big.render(result, True, col["gold"])
                screen.blit(res, (w - 52 - res.get_width(), 96))

            pad = PADS[mode][1]
            for r, cells in enumerate(pad):
                for c, (label, _payload) in enumerate(cells):
                    rect = pygame.Rect(
                        pad_x + c * (cell_w + gap),
                        pad_y + r * (cell_h + gap),
                        cell_w,
                        cell_h,
                    )
                    selected = r == row and c == cell
                    pygame.draw.rect(
                        screen,
                        col["accent"] if selected else col["panel"],
                        rect,
                        0 if selected else 2,
                    )
                    img = font_mid.render(
                        label, True, col["bg"] if selected else col["text"]
                    )
                    screen.blit(
                        img,
                        (
                            rect.centerx - img.get_width() // 2,
                            rect.centery - img.get_height() // 2,
                        ),
                    )

            pygame.display.flip()
            dirty = False

        if clock is not None:
            clock.tick(30)
        else:
            pygame.time.wait(16)


def main():
    """Standalone launch, for testing outside the launcher."""
    import pygame

    pygame.init()
    screen = pygame.display.set_mode((800, 480))
    pygame.display.set_caption(VERSION)
    clock = pygame.time.Clock()
    try:
        run(screen, clock)
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
