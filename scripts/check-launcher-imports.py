#!/usr/bin/env python3
"""Verify every 'from launcher.X import Y' in a launcher tree actually resolves.

Usage:
  check-launcher-imports.py <launcher_src_dir> [shipped_file ...]

Exit 1 on any hard error. Shipped file list is optional; when given, the script
also warns when a published module depends on a module that is NOT published,
which is the failure mode that breaks OTA updates.
"""
import ast, sys
from pathlib import Path

# build-rootfs.sh creates a compat symlink sleep.py -> sleep_timer.py
ALIASES = {"sleep": "sleep_timer"}


def toplevel_names(path):
    tree = ast.parse(path.read_text(), filename=str(path))
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                names.add((a.asname or a.name).split(".")[0])
    return names


def resolve(src, mod):
    mod = ALIASES.get(mod, mod)
    return src / (mod + ".py")


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    src = Path(sys.argv[1])
    shipped = set(sys.argv[2:])
    if not src.is_dir():
        print("ERROR: not a directory: " + str(src), file=sys.stderr)
        return 2

    errors, warnings, cache = [], [], {}

    for f in sorted(src.glob("*.py")):
        try:
            tree = ast.parse(f.read_text(), filename=str(f))
        except SyntaxError as e:
            errors.append(f.name + ": syntax error line " + str(e.lineno) + ": " + e.msg)
            continue

        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("launcher."):
                mods.append((node.module.split(".", 1)[1], node.names, node.lineno))
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.startswith("launcher."):
                        mods.append((a.name.split(".", 1)[1], [], node.lineno))

            for mod, aliases, lineno in mods:
                target = resolve(src, mod)
                if not target.exists():
                    errors.append(f.name + ":" + str(lineno) + ": imports launcher." + mod + " but " + target.name + " is missing")
                    continue
                if target not in cache:
                    try:
                        cache[target] = toplevel_names(target)
                    except SyntaxError as e:
                        errors.append(target.name + ": syntax error line " + str(e.lineno))
                        cache[target] = set()
                names = cache[target]
                for a in aliases:
                    if a.name == "*":
                        continue
                    if a.name not in names:
                        errors.append(f.name + ":" + str(lineno) + ": 'from launcher." + mod + " import " + a.name + "' but " + target.name + " defines no top-level '" + a.name + "'")
                if shipped and f.name in shipped and target.name not in shipped:
                    w = f.name + " is published but its dependency " + target.name + " is NOT in FILES -- OTA would ship a broken pair"
                    if w not in warnings:
                        warnings.append(w)

    for w in warnings:
        print("WARN:  " + w)
    for e in errors:
        print("ERROR: " + e)

    if errors:
        print("")
        print("FAILED: " + str(len(errors)) + " unresolved launcher import(s). Refusing to publish.")
        return 1
    if warnings:
        print("")
        print("PASSED with " + str(len(warnings)) + " warning(s).")
        return 0
    print("OK: all launcher imports resolve.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
