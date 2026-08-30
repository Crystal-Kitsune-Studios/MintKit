#!/usr/bin/env python3
"""Stop the boot splash lying about the version, and centre it properly.

Two bugs in ``rootfs/launcher/splash.py``:

1. The version is a hardcoded string literal, ``"v1.3.0"``, so every release
   bump since Foxfire has been invisible on the boot screen.
2. ``SCREEN_W, SCREEN_H = 640, 480`` while the PocketMint panel is 800x480, so
   the splash is centred on x=320 and sits 80px left of centre.

After this patch ``show()`` takes a ``version`` argument, ``mintos.py`` passes
its single ``VERSION`` constant, and the layout derives its size from the real
surface via ``screen.get_size()``. Bumping one line in ``mintos.py`` then
updates the boot screen, the About entry and the splash together.

Stdlib only. Backs up, refuses to write anything that will not compile, and is
safe to run twice.

    python3 scripts/fix_splash_version.py --dry-run
    python3 scripts/fix_splash_version.py
"""

import argparse
import os
import re
import shutil
import sys

BACKUP_SUFFIX = ".presplash"

HELPERS = '''

def _short_version(raw: str) -> str:
    """Turn 'MintKit 2.1.0 "Spearmint"' into 'v2.1.0 "Spearmint"'."""
    text = (raw or "").strip()
    if text.lower().startswith("mintkit"):
        text = text[len("mintkit"):].strip()
    if text and not text.startswith("v"):
        text = "v" + text
    return text


def _fallback_version() -> str:
    """Last resort: whatever the OTA updater last wrote. Never raises."""
    try:
        return _short_version((DATA_DIR / "version.txt").read_text().strip())
    except Exception:
        return ""
'''


def patch_splash(src: str, report):
    """Return the patched splash.py source."""
    out = src

    # 1. Fallback constant should match the real panel.
    new, n = re.subn(r"SCREEN_W,\s*SCREEN_H\s*=\s*640\s*,\s*480",
                     "SCREEN_W, SCREEN_H = 800, 480", out, count=1)
    if n:
        out = new
        report("OK   splash: panel size 640 -> 800")
    elif "SCREEN_W, SCREEN_H = 800, 480" in out:
        report("SKIP splash: panel size already 800")
    else:
        report("WARN splash: no 640x480 constant found, left alone")

    # 2. Version helpers.
    if "_short_version" in out:
        report("SKIP splash: helpers already present")
    else:
        anchor = re.search(r"^_fonts_cache.*$", out, re.M)
        if not anchor:
            report("FAIL splash: no _fonts_cache anchor for the helpers")
            return None
        cut = anchor.end()
        out = out[:cut] + HELPERS + out[cut:]
        report("OK   splash: added _short_version and _fallback_version")

    # 3. show() gains a version argument.
    if re.search(r"def show\([^)]*version", out, re.S):
        report("SKIP splash: show() already takes a version")
    else:
        new, n = re.subn(
            r"(def show\(screen, clock, duration_ms: int = DEFAULT_MS)\)",
            r'\1, version: str = "")', out, count=1)
        if not n:
            report("FAIL splash: could not find the show() signature")
            return None
        out = new
        report("OK   splash: show() takes version")

    # 4. Both renderers should size themselves from the real surface.
    for func, anchor in (("show", r"(\n    p = th\.get\(\)\n)"),
                         ("_draw_default",
                          r"(\n    overlay = pygame\.Surface\()")):
        marker = "SCREEN_W, SCREEN_H = screen.get_size()"
        if out.count(marker) >= (1 if func == "show" else 2):
            report("SKIP splash: %s already sizes from the surface" % func)
            continue
        line = "    %s\n" % marker
        if func == "show":
            new, n = re.subn(anchor, r"\1" + line, out, count=1)
        else:
            new, n = re.subn(anchor, "\n" + line + r"\1", out, count=1)
        if not n:
            report("WARN splash: no size anchor in %s" % func)
            continue
        out = new
        report("OK   splash: %s sizes from the surface" % func)

    # 5. Pass version through to the default renderer.
    if re.search(r"_draw_default\(screen, p, alpha, fonts, version\)", out):
        report("SKIP splash: version already passed to _draw_default")
    else:
        new, n = re.subn(r"_draw_default\(screen, p, alpha, fonts\)",
                         "_draw_default(screen, p, alpha, fonts, version)",
                         out, count=1)
        if not n:
            report("FAIL splash: could not find the _draw_default call")
            return None
        out = new
        report("OK   splash: version passed to _draw_default")

    if re.search(r"def _draw_default\([^)]*version", out, re.S):
        report("SKIP splash: _draw_default already takes a version")
    else:
        new, n = re.subn(
            r"(def _draw_default\(screen, p: dict, alpha: int, fonts: dict)\)",
            r'\1, version: str = "")', out, count=1)
        if not n:
            report("FAIL splash: could not find the _draw_default signature")
            return None
        out = new
        report("OK   splash: _draw_default takes version")

    # 6. The actual lie.
    if "_short_version(version)" in out:
        report("SKIP splash: version string already dynamic")
    else:
        new, n = re.subn(
            r'ver\s*=\s*fonts\["sm"\]\.render\(\s*"v[^"]*"\s*,',
            'ver   = fonts["sm"].render(_short_version(version) or '
            '_fallback_version(),', out, count=1)
        if not n:
            report("FAIL splash: could not find the hardcoded version render")
            return None
        out = new
        report("OK   splash: version string is dynamic")

    return out


def patch_mintos(src: str, report):
    """Return the patched mintos.py source, or the original when already done."""
    call = re.search(r"show_splash\(([^)]*)\)", src)
    if not call:
        report("FAIL mintos: no show_splash( call found")
        return None
    if "version" in call.group(1):
        report("SKIP mintos: show_splash already passes a version")
        return src
    args = call.group(1).rstrip()
    patched = "show_splash(%s, version=VERSION)" % args
    out = src[:call.start()] + patched + src[call.end():]
    report("OK   mintos: show_splash passes VERSION")
    return out


def process(path, patcher, dry_run, report):
    if not os.path.exists(path):
        report("FAIL %s does not exist" % path)
        return False
    with open(path, "r", encoding="utf-8") as handle:
        src = handle.read()

    out = patcher(src, report)
    if out is None:
        return False
    if out == src:
        return True

    try:
        compile(out, path, "exec")
    except SyntaxError as exc:
        report("ERROR patched %s would not compile: %s" % (path, exc))
        report("Refusing to write. File untouched.")
        return False

    if dry_run:
        report("dry run, not writing %s" % path)
        return True

    shutil.copy2(path, path + BACKUP_SUFFIX)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(out)
    report("wrote %s (backup at %s)" % (path, path + BACKUP_SUFFIX))
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=os.path.expanduser("~/pocketmint"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--show", action="store_true",
                        help="print the version lines and exit")
    args = parser.parse_args(argv)

    launcher = os.path.join(args.root, "rootfs", "launcher")
    splash = os.path.join(launcher, "splash.py")
    mintos = os.path.join(launcher, "mintos.py")

    lines = []
    report = lines.append

    if args.show:
        for path in (splash, mintos):
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    for num, line in enumerate(handle, 1):
                        if re.search(r"VERSION|v\d+\.\d+\.\d+|SCREEN_W", line):
                            print("%s:%d: %s" % (os.path.basename(path),
                                                 num, line.rstrip()))
            except OSError as exc:
                print("cannot read %s: %s" % (path, exc))
        return 0

    ok = process(splash, patch_splash, args.dry_run, report)
    ok = process(mintos, patch_mintos, args.dry_run, report) and ok

    for line in lines:
        print(line)
    if not ok:
        print("\nFAILED. Nothing was written for any file that reported FAIL.")
        return 1
    print("\nDone. Bump VERSION in mintos.py and the splash follows it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
