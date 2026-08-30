#!/usr/bin/env python3
"""Rename an unreleased CHANGELOG entry and fold the screen saver into it.

The 2.0.3 entry was written before the screen saver existed and 2.0.3 was
never tagged, so the number is still free. A new user facing feature is a
minor bump, which makes this 2.1.0.

What it does, all idempotent:
  * rewrites the  ## [FROM]  heading to  ## [TO] - DATE "Codename"
  * adds the screen saver bullets to that entry's ### Added section,
    creating the section if it does not exist
  * normalises curly quotes in every  ## [  heading, because at least one
    entry picked up a smart quote from a paste

Only the target entry is touched. Older entries keep their text.

Usage:
  bump_changelog.py [--file PATH] [--from 2.0.3] [--to 2.1.0]
                    [--date YYYY-MM-DD] [--show] [--dry-run]

--file defaults to ~/pocketmint/CHANGELOG.md
"""
import argparse
import datetime
import re
import shutil
import sys
from pathlib import Path

BACKUP_SUFFIX = ".prebump"
HEADING = re.compile(r"^##\s*\[([^\]]+)\]")
SUBHEAD = re.compile(r"^###\s+(.*)$")
IDEMPOTENCY_KEY = "screen saver"

BULLETS = [
    "- Screen saver, shown before the device sleeps. Four modes: `bounce` (a",
    "  DVD style POCKETMINT wordmark with a corner hit counter), `starfield`,",
    "  `clock` (large drifting time, date and battery) and `rain`. Chosen with",
    "  `screensaver_mode`, started after `screensaver_secs` of idle, disabled",
    "  with `0` or `\"off\"`. It owns its own frames at 30 fps, allocates every",
    "  surface once at start so a frame is fill and blit only, hands control",
    "  back on real input, and hands over to sleep when the sleep timeout",
    "  arrives. Analog axes and hats are excluded from wake, so a drifting",
    "  stick cannot hold the panel awake. Setting `sleep_timeout_secs` to `0`",
    "  alongside a small `screensaver_secs` gives a saver that never sleeps.",
    "- `screensaver.py` is imported defensively by `sleep_timer.py`, so a",
    "  device that receives a partial update degrades to plain sleep instead",
    "  of crash looping, which is how 2.0.2 became unbootable.",
    "- `fix_ota_lists.py`, which rebuilds `LAUNCHER_FILES` and `FILES` from",
    "  parsed tokens instead of substituting text, and reports any module",
    "  present in one OTA list but not the other, or listed but absent on",
    "  disk. Both lists now carry `screensaver.py`.",
    "- `hook_screensaver.py`, which wires the saver into `SleepTimer.tick()`",
    "  by locating the method with `ast` and compiling the result before it",
    "  writes anything.",
]


def normalise_quotes(line):
    return line.replace("\u201c", '"').replace("\u201d", '"')


def find_section(lines, version):
    start = None
    for i, line in enumerate(lines):
        m = HEADING.match(line)
        if m and m.group(1).strip() == version:
            start = i
            break
    if start is None:
        return None, None
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if HEADING.match(lines[j]):
            end = j
            break
    return start, end


def codename_of(line):
    m = re.search(r'["\u201c]([^"\u201c\u201d]+)["\u201d]', line)
    return m.group(1) if m else None


def insert_point(lines, start, end):
    """(index, needs_header) for where the screen saver bullets belong."""
    added = None
    for i in range(start + 1, end):
        m = SUBHEAD.match(lines[i])
        if m and m.group(1).strip().lower() == "added":
            added = i
            break
    if added is not None:
        stop = end
        for j in range(added + 1, end):
            if SUBHEAD.match(lines[j]):
                stop = j
                break
        while stop > added + 1 and not lines[stop - 1].strip():
            stop -= 1
        return stop, False
    # no Added section: sit before Known issues if present, else at the end
    for i in range(start + 1, end):
        m = SUBHEAD.match(lines[i])
        if m and m.group(1).strip().lower().startswith("known"):
            return i, True
    stop = end
    while stop > start + 1 and not lines[stop - 1].strip():
        stop -= 1
    return stop, True


def main(argv=None):
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--file", default=str(Path.home() / "pocketmint" / "CHANGELOG.md"))
    ap.add_argument("--from", dest="src", default="2.0.3")
    ap.add_argument("--to", dest="dst", default="2.1.0")
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    path = Path(args.file).expanduser()
    if not path.is_file():
        print("ERROR: no such file: %s" % path)
        return 1

    original = path.read_text()
    lines = original.split("\n")

    if args.show:
        for i, line in enumerate(lines):
            if HEADING.match(line):
                print("%4d  %s" % (i + 1, line))
        return 0

    start, end = find_section(lines, args.src)
    already = find_section(lines, args.dst)[0] is not None
    if start is None and already:
        start, end = find_section(lines, args.dst)
        print("heading is already [%s]" % args.dst)
    elif start is None:
        print("ERROR: no '## [%s]' heading in %s" % (args.src, path.name))
        print("       Run with --show to list the headings. Nothing changed.")
        return 1

    changes = []

    # 1. bullets, before any renaming so the section index stays valid
    section_text = "\n".join(lines[start:end]).lower()
    if IDEMPOTENCY_KEY in section_text:
        print("SKIP: the entry already mentions the screen saver")
    else:
        idx, needs_header = insert_point(lines, start, end)
        block = (["### Added", ""] if needs_header else []) + list(BULLETS)
        if needs_header:
            block = [""] + block + [""]
        lines[idx:idx] = block
        end += len(block)
        changes.append("added %d screen saver lines" % len(BULLETS))

    # 2. heading
    if HEADING.match(lines[start]).group(1).strip() != args.dst:
        name = codename_of(lines[start]) or "Spearmint"
        lines[start] = '## [%s] - %s "%s"' % (args.dst, args.date, name)
        changes.append("renamed [%s] to [%s]" % (args.src, args.dst))

    # 3. curly quotes in headings
    fixed = 0
    for i, line in enumerate(lines):
        if HEADING.match(line):
            clean = normalise_quotes(line)
            if clean != line:
                lines[i] = clean
                fixed += 1
    if fixed:
        changes.append("normalised curly quotes in %d heading%s"
                       % (fixed, "" if fixed == 1 else "s"))

    new_text = "\n".join(lines)
    if new_text == original:
        print("Nothing to do. %s is already up to date." % path.name)
        return 0

    if args.dry_run:
        for c in changes:
            print("would: %s" % c)
        print("Nothing written.")
        return 0

    bak = path.with_name(path.name + BACKUP_SUFFIX)
    if not bak.is_file():
        shutil.copy2(path, bak)
    path.write_text(new_text)
    for c in changes:
        print("applied: %s" % c)
    print("Wrote %s. Backup: %s" % (path, bak.name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
