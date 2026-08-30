#!/usr/bin/env python3
"""Insert the 2.2.0 section into CHANGELOG.md.

One shot and idempotent. The prose lives in this file rather than being pasted,
because pasting indentation sensitive text through a clipboard has already
eaten a heredoc once this month.

Also normalises curly quotes in section headings, which is why the 2.0.0
heading still reads ``"Spearmint\u201d``.

    python3 scripts/changelog_2_2_0.py --dry-run
    python3 scripts/changelog_2_2_0.py
"""

import argparse
import datetime
import os
import re
import shutil
import sys

BACKUP_SUFFIX = ".prebump"
VERSION = "2.2.0"
CODENAME = "Spearmint"
HEADING = re.compile(r"^##\s*\[([^\]]+)\]")

BODY = '''## [{version}] - {date} "{codename}"

The boot screen had been reporting v1.3.0 since Foxfire. The version was a
string literal in `splash.py`, so it never followed `VERSION` and every release
since has quietly announced the wrong one to anyone watching the device start.

### Fixed

- **The boot splash reported a hardcoded `v1.3.0`.** `splash.py` rendered the
  version from a string literal, so the boot screen, the About entry and the
  release tag had drifted three minor versions apart. `show()` now takes the
  version from its caller, `mintos.py` passes its single `VERSION` constant,
  and the splash falls back to `~/.mintkit/version.txt`, which the OTA updater
  already maintains, if it is called without one. Bumping `VERSION` now moves
  all three together.
- **The boot splash was laid out for a 640x480 panel.** It allocated a 640 wide
  overlay and centred every element at `x=320` on an 800x480 display, leaving
  the whole splash 80 px left of centre. Both renderers now derive their size
  from `screen.get_size()`. This is the same defect fixed in the sleep warning
  overlay in 2.1.0. `splash.py` had its own copy of it.

### Added

- **Three more screen saver modes, seven in total.** `beams`, five rotating
  light arms on a Lissajous orbit with baked shade and width tables; `bubbles`,
  sixteen drifting spheres composited from fifteen pre-rendered sprites; and
  `kitsune`, a three tailed fox chasing butterflies across the panel. As with
  the original four, every surface is allocated once at start, so a frame is
  fill and blit only.
- **Power aware sleep.** The idle timeout now depends on where the power is
  coming from. On wall power the device does not sleep and the saver runs
  indefinitely. On battery it uses `sleep_timeout_secs`. At or below
  `low_battery_pct`, 20 by default, it drops to `sleep_timeout_low_secs`, 90 by
  default. An unknown power state deliberately falls back to the configured
  timeout, so a missing battery driver can never pin the panel awake. While
  held awake on wall power the saver re-checks the power source every five
  minutes, so unplugging is noticed without a restart. Tunable with
  `power_aware_sleep`, `sleep_timeout_charging_secs`, `sleep_timeout_low_secs`
  and `low_battery_pct`.
- **`launcher/pisugar.py`**, a PiSugar 3 battery reader. The PiSugar is an I2C
  device and never appears under `/sys/class/power_supply`, so `battery.get()`
  returns `None` on a PocketMint and the power policy had nothing to read. It
  prefers `pisugar-server` over its unix socket or TCP 8423 when the daemon is
  running, and otherwise talks to the MCU at `0x57` on `/dev/i2c-1` directly
  through `ioctl`, with no third party library and no pip install. Register
  map from the official PiSugar 3 datasheet: bit 7 of `0x02` is external power
  connected, `0x2A` is the calculated percentage, `0x22` and `0x23` are the
  battery voltage in mV. Returns the same shape as `battery.get()`, and `None`
  rather than a guess when nothing answers.
- **`scripts/fix_splash_version.py`**, which applies both splash fixes, backs
  up first, and refuses to write a result that does not compile.

### Known issues

- I2C is disabled in the shipped `config.txt`, so `/dev/i2c-1` does not exist
  on a fresh flash and `pisugar.py` reads as unknown power state until
  `dtparam=i2c_arm=on` and the `i2c-dev` module are added. `mintkit.service`
  will also need `i2c` in `SupplementaryGroups`, because a systemd unit does
  not inherit group membership granted with `usermod`. Belongs in
  `build-rootfs.sh`.
- The image still ships `/etc/resolv.conf` copied from the CI runner, pointing
  at `127.0.0.53` for a `systemd-resolved` that is not installed, plus an Azure
  internal search domain. DNS fails on a fresh flash until the file is
  replaced. Fix belongs in `build-rootfs.sh`.
- `launcher/mintfb.py` is referenced by the `app_env()` docstring but does not
  exist. Nothing imports it, so it is documentation drift rather than a crash.

---
'''


def normalise_headings(lines, report):
    fixed = 0
    out = []
    for line in lines:
        if line.startswith("## [") and ("\u201c" in line or "\u201d" in line):
            line = line.replace("\u201c", '"').replace("\u201d", '"')
            fixed += 1
        out.append(line)
    if fixed:
        report("OK   normalised curly quotes in %d heading(s)" % fixed)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default=os.path.expanduser(
        "~/pocketmint/CHANGELOG.md"))
    parser.add_argument("--date", default=datetime.date.today().isoformat())
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--show", action="store_true",
                        help="list the section headings and exit")
    args = parser.parse_args(argv)

    if not os.path.exists(args.file):
        print("FAIL %s does not exist" % args.file)
        return 1

    with open(args.file, "r", encoding="utf-8") as handle:
        lines = handle.read().split("\n")

    if args.show:
        for num, line in enumerate(lines, 1):
            if HEADING.match(line):
                print("%d: %s" % (num, line))
        return 0

    notes = []
    report = notes.append

    for line in lines:
        match = HEADING.match(line)
        if match and match.group(1).strip() == VERSION:
            print("Nothing to do, a %s section already exists." % VERSION)
            return 0

    first = None
    for index, line in enumerate(lines):
        if HEADING.match(line):
            first = index
            break

    if first is None:
        print("FAIL no '## [version]' heading found in %s" % args.file)
        print("Refusing to guess where the section belongs.")
        return 1

    newest = HEADING.match(lines[first]).group(1).strip()
    report("OK   inserting %s above the current newest section, %s"
           % (VERSION, newest))

    lines = normalise_headings(lines, report)

    body = BODY.format(version=VERSION, date=args.date, codename=CODENAME)
    block = body.split("\n")
    if block and block[-1] == "":
        block = block[:-1]
    block.append("")

    out = lines[:first] + block + lines[first:]
    text = "\n".join(out)

    if "\u201c" in text or "\u201d" in text:
        report("WARN curly quotes remain in the body text, outside headings")

    for line in notes:
        print(line)

    if args.dry_run:
        print("\ndry run, not writing. Preview of the new section:\n")
        print("\n".join(block[:14]))
        print("  ...")
        return 0

    shutil.copy2(args.file, args.file + BACKUP_SUFFIX)
    with open(args.file, "w", encoding="utf-8") as handle:
        handle.write(text)
    print("\nwrote %s (backup at %s)" % (args.file, args.file + BACKUP_SUFFIX))
    return 0


if __name__ == "__main__":
    sys.exit(main())
