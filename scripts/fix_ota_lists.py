#!/usr/bin/env python3
"""Repair and synchronise the two MintKit OTA file lists.

  rootfs/launcher/updater.py    LAUNCHER_FILES = [...]
  scripts/deploy-launcher.sh    FILES=(...)

Rather than substituting text, this parses every *.py token out of each list,
de-duplicates, adds anything missing, and rewrites the list in canonical form.
That makes it immune to a list that a bad sed already mangled, and it is
idempotent, so running it twice is a no-op.

updater.py is parsed with ast before anything is written. If the result would
not be valid Python, nothing is touched.

It also reports the two failure modes that actually bit this project:
  * a module in one list but not the other, which ships a broken pair
  * a module in a list that does not exist on disk

Usage:
  fix_ota_lists.py [--root DIR] [--add NAME.py ...] [--show] [--dry-run]

--root defaults to ~/pocketmint
"""
import argparse
import ast
import re
import shutil
import sys
from pathlib import Path

BACKUP_SUFFIX = ".preota"
DEFAULT_ADDS = ["screensaver.py"]
# where a newly added module should sit, for readability only
PREFER_AFTER = {"screensaver.py": "sleep_timer.py"}

TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_\-]*\.py")
PY_LIST = re.compile(r"^(\s*LAUNCHER_FILES\s*=\s*)\[(.*?)\]", re.M | re.S)
SH_LIST = re.compile(r"^(\s*FILES=\()(.*?)(\))\s*$", re.M | re.S)


def dedupe(items):
    seen = set()
    out = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out


def ensure(tokens, name):
    """Add name if absent, next to its preferred neighbour when possible."""
    if name in tokens:
        return tokens, False
    anchor = PREFER_AFTER.get(name)
    if anchor and anchor in tokens:
        idx = tokens.index(anchor) + 1
        return tokens[:idx] + [name] + tokens[idx:], True
    return tokens + [name], True


def read_list(path, pattern, label):
    if not path.is_file():
        return None, None, "missing file: %s" % path
    text = path.read_text()
    match = pattern.search(text)
    if not match:
        return text, None, "could not find %s in %s" % (label, path.name)
    tokens = dedupe(TOKEN.findall(match.group(2)))
    if not tokens:
        return text, None, "%s in %s parsed to an empty list" % (label, path.name)
    return text, (match, tokens), None


def main(argv=None):
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--root", default=str(Path.home() / "pocketmint"))
    ap.add_argument("--add", action="append", default=None)
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    root = Path(args.root).expanduser()
    adds = args.add if args.add else list(DEFAULT_ADDS)

    updater = root / "rootfs" / "launcher" / "updater.py"
    deploy = root / "scripts" / "deploy-launcher.sh"
    launcher_dir = root / "rootfs" / "launcher"

    up_text, up_found, up_err = read_list(updater, PY_LIST, "LAUNCHER_FILES")
    dp_text, dp_found, dp_err = read_list(deploy, SH_LIST, "FILES=(...)")

    for err in (up_err, dp_err):
        if err:
            print("ERROR: %s" % err)
    if up_err or dp_err:
        print("Nothing was changed.")
        return 1

    up_match, up_tokens = up_found
    dp_match, dp_tokens = dp_found

    if args.show:
        print("updater.py  LAUNCHER_FILES (%d):" % len(up_tokens))
        for t in up_tokens:
            print("    %s" % t)
        print("deploy-launcher.sh  FILES (%d):" % len(dp_tokens))
        for t in dp_tokens:
            print("    %s" % t)
        return 0

    new_up = list(up_tokens)
    new_dp = list(dp_tokens)
    changed_up = changed_dp = False
    for name in adds:
        new_up, c1 = ensure(new_up, name)
        new_dp, c2 = ensure(new_dp, name)
        changed_up = changed_up or c1
        changed_dp = changed_dp or c2

    # canonical rewrite always runs, which is what repairs a mangled list
    up_body = ", ".join('"%s"' % t for t in new_up)
    up_new_text = up_text[:up_match.start()] + up_match.group(1) + "[" + up_body + "]" \
        + up_text[up_match.end():]
    dp_body = " ".join(new_dp)
    dp_new_text = dp_text[:dp_match.start()] + dp_match.group(1) + dp_body + dp_match.group(3) \
        + dp_text[dp_match.end():]

    try:
        ast.parse(up_new_text)
    except SyntaxError as exc:
        print("ERROR: rewritten updater.py would not parse: %s" % exc)
        print("Refusing to write. Nothing was changed.")
        return 1

    up_dirty = up_new_text != up_text
    dp_dirty = dp_new_text != dp_text

    if not up_dirty and not dp_dirty:
        print("Both lists are already correct and in sync. Nothing to do.")
    else:
        if args.dry_run:
            if up_dirty:
                print("would rewrite LAUNCHER_FILES (%d entries)" % len(new_up))
            if dp_dirty:
                print("would rewrite FILES (%d entries)" % len(new_dp))
            print("Rewritten updater.py parses. Nothing written.")
        else:
            if up_dirty:
                bak = updater.with_name(updater.name + BACKUP_SUFFIX)
                if not bak.is_file():
                    shutil.copy2(updater, bak)
                updater.write_text(up_new_text)
                print("rewrote LAUNCHER_FILES (%d entries) in %s" % (len(new_up), updater.name))
            if dp_dirty:
                bak = deploy.with_name(deploy.name + BACKUP_SUFFIX)
                if not bak.is_file():
                    shutil.copy2(deploy, bak)
                deploy.write_text(dp_new_text)
                print("rewrote FILES (%d entries) in %s" % (len(new_dp), deploy.name))

    # ---- audit ----------------------------------------------------------
    problems = 0
    only_up = [t for t in new_up if t not in new_dp]
    only_dp = [t for t in new_dp if t not in new_up]
    for t in only_up:
        print("WARN: %s is in updater.py but not deploy-launcher.sh" % t)
        problems += 1
    for t in only_dp:
        print("WARN: %s is in deploy-launcher.sh but not updater.py" % t)
        problems += 1

    if launcher_dir.is_dir():
        for t in dedupe(new_up + new_dp):
            if not (launcher_dir / t).is_file():
                print("WARN: %s is listed but does not exist in %s" % (t, launcher_dir))
                problems += 1

    print("")
    print("LAUNCHER_FILES: %s" % " ".join(new_up))
    print("FILES:          %s" % " ".join(new_dp))
    if problems:
        print("\n%d warning%s. Fix these before publishing."
              % (problems, "" if problems == 1 else "s"))
    else:
        print("\nOK: both lists agree and every listed module exists.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
