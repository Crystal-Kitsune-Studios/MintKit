#!/usr/bin/env python3
"""check-launcher-imports.py -- pre-publish import guard for the MintKit launcher.

Usage:
    check-launcher-imports.py <launcher_dir> [shipped_file ...]

Resolves three import shapes against the files actually present on disk:

    from launcher.MOD import NAME   ->  MOD.py exists AND defines top-level NAME
    from launcher import MOD        ->  MOD.py exists (or NAME lives in __init__.py)
    import launcher.MOD             ->  MOD.py exists

ERROR (exit 1)  an import cannot resolve. The launcher will crash at boot.
WARN  (exit 0)  a module resolves locally but is missing from the shipped-file
                list, so an OTA push would ship a broken pair.

v2: added the 'from launcher import MOD' shape. v1 only understood
'from launcher.MOD import NAME' and 'import launcher.MOD', which is why it
missed 'from launcher import mintcalc'.
"""

import ast
import os
import sys

# build-rootfs.sh creates sleep.py as a symlink to sleep_timer.py, so the
# import name and the repo filename differ.
ALIASES = {"sleep": "sleep_timer"}


def top_level_names(path):
    """Every name a module binds at module scope."""
    names = set()
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            tree = ast.parse(fh.read(), filename=path)
    except SyntaxError as exc:
        return names, "%s: syntax error: %s" % (os.path.basename(path), exc)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
                elif isinstance(target, (ast.Tuple, ast.List)):
                    for elt in target.elts:
                        if isinstance(elt, ast.Name):
                            names.add(elt.id)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
    return names, None


def main(argv):
    if len(argv) < 2:
        sys.stderr.write(__doc__)
        return 2

    src = argv[1].rstrip("/")
    shipped = set(argv[2:])

    if not os.path.isdir(src):
        print("ERROR: %s is not a directory" % src)
        return 1

    present = set()
    for entry in os.listdir(src):
        if entry.endswith(".py"):
            present.add(entry[:-3])

    init_names = set()
    init_path = os.path.join(src, "__init__.py")
    if os.path.isfile(init_path):
        init_names, _ = top_level_names(init_path)

    cache = {}

    def names_of(module):
        if module not in cache:
            cache[module] = top_level_names(os.path.join(src, module + ".py"))
        return cache[module]

    def resolve(module):
        """Import name -> real module stem on disk, or None."""
        if module in present:
            return module
        alias = ALIASES.get(module)
        if alias and alias in present:
            return alias
        return None

    errors = []
    warnings = []
    deps = {}

    sources = sorted(f for f in os.listdir(src) if f.endswith(".py"))

    for filename in sources:
        path = os.path.join(src, filename)
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                tree = ast.parse(fh.read(), filename=path)
        except SyntaxError as exc:
            errors.append("%s: syntax error: %s" % (filename, exc))
            continue

        used = deps.setdefault(filename, set())

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level > 1:
                    continue
                if node.level == 1:
                    # 'from . import themes' and 'from .battery import draw_bar'
                    # mean exactly the same thing as the absolute forms inside
                    # the launcher package. Rewrite and fall through so the
                    # same checks apply.
                    node.module = (
                        "launcher" if not node.module else "launcher." + node.module
                    )
                    node.level = 0
                if not node.module:
                    continue

                # shape: from launcher import MOD [, MOD2]
                if node.module == "launcher":
                    for alias in node.names:
                        target = alias.name
                        real = resolve(target)
                        if real is None:
                            if target in init_names:
                                continue
                            errors.append(
                                "%s:%d: 'from launcher import %s' but %s.py "
                                "does not exist in %s"
                                % (filename, node.lineno, target, target, src)
                            )
                        else:
                            used.add(real + ".py")

                # shape: from launcher.MOD import NAME
                elif node.module.startswith("launcher."):
                    module = node.module.split(".")[1]
                    real = resolve(module)
                    if real is None:
                        errors.append(
                            "%s:%d: 'from %s import ...' but %s.py does not "
                            "exist in %s"
                            % (filename, node.lineno, node.module, module, src)
                        )
                        continue
                    used.add(real + ".py")
                    defined, syntax_error = names_of(real)
                    if syntax_error:
                        errors.append("%s:%d: %s" % (filename, node.lineno, syntax_error))
                        continue
                    for alias in node.names:
                        if alias.name == "*":
                            continue
                        if alias.name not in defined:
                            errors.append(
                                "%s:%d: 'from %s import %s' but %s.py defines "
                                "no top-level '%s'"
                                % (
                                    filename,
                                    node.lineno,
                                    node.module,
                                    alias.name,
                                    real,
                                    alias.name,
                                )
                            )

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if not alias.name.startswith("launcher."):
                        continue
                    module = alias.name.split(".")[1]
                    real = resolve(module)
                    if real is None:
                        errors.append(
                            "%s:%d: 'import %s' but %s.py does not exist in %s"
                            % (filename, node.lineno, alias.name, module, src)
                        )
                    else:
                        used.add(real + ".py")

    if shipped:
        for filename in sorted(shipped):
            if not os.path.isfile(os.path.join(src, filename)):
                errors.append(
                    "%s is in the shipped list but does not exist in %s"
                    % (filename, src)
                )
        for filename in sorted(shipped):
            for dep in sorted(deps.get(filename, ())):
                if dep not in shipped:
                    warnings.append(
                        "%s is published but its dependency %s is NOT in FILES "
                        "-- OTA would ship a broken pair" % (filename, dep)
                    )

    for line in warnings:
        print("WARN:  %s" % line)
    for line in errors:
        print("ERROR: %s" % line)

    if errors:
        print("")
        print(
            "FAILED: %d unresolved launcher import(s). Refusing to publish."
            % len(errors)
        )
        return 1

    print("OK: all launcher imports resolve.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
