#!/usr/bin/env python3
"""Wire launcher/screensaver.py into launcher/sleep_timer.py.

Two insertions, both self locating, both idempotent, and the result is
compiled in memory before a single byte is written. If it would not compile,
nothing is touched.

  1. a guarded  from . import screensaver as _saver  at module scope
  2. a three line hook as the first statement of SleepTimer.tick()

All the screen saver policy (config keys, idle threshold, mode, deadline)
lives in screensaver.py, so sleep_timer.py never needs to change again. The
import is guarded so a device without screensaver.py degrades to plain sleep
instead of crash looping, which is exactly how 2.0.2 bricked itself.

Usage:
  hook_screensaver.py [PATH] [--show] [--dry-run] [--undo]

PATH defaults to ~/pocketmint/rootfs/launcher/sleep_timer.py
"""
import ast
import shutil
import sys
from pathlib import Path

DEFAULT_TARGET = Path.home() / "pocketmint" / "rootfs" / "launcher" / "sleep_timer.py"
BACKUP_SUFFIX = ".presaver"

IMPORT_KEY = "import screensaver"
HOOK_KEY = "_saver.hook("

IMPORT_BLOCK = [
    "",
    "try:",
    "    from . import screensaver as _saver",
    "except Exception:",
    "    # screensaver.py not deployed: degrade to plain sleep, never crash.",
    "    _saver = None",
]


def hook_block(indent):
    pad = " " * indent
    return [
        pad + "# Screen saver phase. Owns its own frames, so it must run",
        pad + "# before anything else in the tick.",
        pad + "if _saver is not None:",
        pad + "    _hooked = _saver.hook(self, screen, clock)",
        pad + "    if _hooked is not None:",
        pad + "        return _hooked",
    ]


def parse(text, label):
    try:
        return ast.parse(text)
    except SyntaxError as exc:
        print("ERROR: %s does not parse: %s" % (label, exc))
        return None


def find_tick(tree):
    """Return the tick FunctionDef node inside class SleepTimer."""
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "SleepTimer":
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and sub.name == "tick":
                    return sub
    return None


def last_toplevel_import(tree):
    """Line number (1 based) of the last module scope import statement."""
    line = 0
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            line = max(line, getattr(node, "end_lineno", node.lineno))
        elif isinstance(node, ast.Try):
            # a guarded import block counts too
            for sub in node.body:
                if isinstance(sub, (ast.Import, ast.ImportFrom)):
                    line = max(line, getattr(node, "end_lineno", node.lineno))
    return line


def body_insert_point(fn):
    """(line_index_to_insert_before, indent) for the first real statement of a
    function body, skipping a docstring of any length."""
    first = fn.body[0]
    indent = first.col_offset
    is_doc = (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    )
    if is_doc:
        if len(fn.body) == 1:
            return getattr(first, "end_lineno", first.lineno), indent
        return getattr(first, "end_lineno", first.lineno), indent
    return first.lineno - 1, indent


def dump(lines, start, end):
    for i in range(max(0, start - 1), min(len(lines), end)):
        body = lines[i]
        pad = len(body) - len(body.lstrip(" "))
        print("%4d [%2d] %s" % (i + 1, pad, body.strip()))


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    flags = set(a for a in argv[1:] if a.startswith("--"))
    target = Path(args[0]).expanduser() if args else DEFAULT_TARGET

    if not target.is_file():
        print("ERROR: no such file: %s" % target)
        return 1

    backup = target.with_name(target.name + BACKUP_SUFFIX)

    if "--undo" in flags:
        if not backup.is_file():
            print("ERROR: no backup at %s" % backup)
            return 1
        shutil.copy2(backup, target)
        print("Restored %s from %s" % (target, backup.name))
        return 0

    text = target.read_text()
    lines = text.split("\n")
    tree = parse(text, target.name)
    if tree is None:
        return 1

    fn = find_tick(tree)
    if fn is None:
        print("ERROR: could not find SleepTimer.tick() in %s" % target)
        print("       Nothing was changed. Send me the file and I will look.")
        return 1

    insert_before, indent = body_insert_point(fn)

    if "--show" in flags:
        print("--- %s" % target)
        print("tick() at line %d, body indent %d, insert after line %d"
              % (fn.lineno, indent, insert_before))
        dump(lines, fn.lineno, min(len(lines), fn.lineno + 14))
        return 0

    changes = []

    # patch 2 first: it is further down the file, so patch 1 cannot shift it
    if HOOK_KEY in text:
        print("SKIP patch 2: tick() already calls the screen saver hook")
    else:
        block = hook_block(indent)
        lines[insert_before:insert_before] = block
        changes.append("hook into tick() after line %d" % insert_before)

    if IMPORT_KEY in text:
        print("SKIP patch 1: screensaver already imported")
    else:
        anchor = last_toplevel_import(tree)
        if anchor <= 0:
            print("ERROR: found no module scope imports to anchor to")
            return 1
        lines[anchor:anchor] = IMPORT_BLOCK
        changes.append("guarded import after line %d" % anchor)

    if not changes:
        print("Nothing to do. %s is already wired." % target.name)
        return 0

    new_text = "\n".join(lines)

    try:
        compile(new_text, str(target), "exec")
    except SyntaxError as exc:
        print("ERROR: patched file would not compile: %s" % exc)
        print("Refusing to write. File untouched.")
        return 1

    if "--dry-run" in flags:
        for c in changes:
            print("OK (dry run): %s" % c)
        print("Patched file compiles. Nothing written.")
        return 0

    if not backup.is_file():
        shutil.copy2(target, backup)
    target.write_text(new_text)
    for c in changes:
        print("applied: %s" % c)
    print("Wrote %s (%d change%s). Backup: %s"
          % (target, len(changes), "" if len(changes) == 1 else "s", backup.name))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
