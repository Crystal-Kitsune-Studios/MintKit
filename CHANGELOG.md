# Changelog

All notable changes to MintKit are recorded here. Entries from 2.0.0 onward are
written by hand. Everything below the "Earlier releases" divider was generated
mechanically from commit subjects and is not a reliable record.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.0.3] - 2026-08-29 "Spearmint"

The idle timer powered the device off instead of sleeping, and had done so since
the feature was written. It went unnoticed for months because the launcher never
stayed up long enough to reach five minutes of idle. The first genuinely
successful boot lasted nineteen minutes before the device shut itself down.

### Fixed

- **Idle timeout powered the device off instead of sleeping.** From the journal:
  two `sudo /usr/sbin/poweroff` calls one frame apart at `00:10:13`, five
  minutes after the last input. The Pi Zero 2 W has no suspend-to-RAM, so
  `systemctl suspend` is not available and shutdown was used as a substitute.
  Sleep is now implemented in software: blank the framebuffer, cut panel power
  with `vcgencmd display_power 0` (DPMS fallback under `vc4-kms-v3d`), then idle
  at 8 Hz polling for input instead of rendering at 60 fps. State survives and
  wake is instant, against a 15 second cold boot on a board with no RTC.
  Wake fires on `KEYDOWN`, `JOYBUTTONDOWN`, and `MOUSEBUTTONDOWN` only. Analog
  axes and hats are deliberately excluded so stick drift cannot wake a sleeping
  device. `sleep_and_wake()` pokes the idle timer on return so it does not
  immediately re-sleep.
- **The Settings "Shutdown" item never worked.** It called
  `subprocess.run(["poweroff"])` as an unprivileged user, so the shutdown you
  asked for silently failed while the one you did not ask for succeeded. Now
  invoked with sudo.
- **`sleep_timer.timeout()` read and JSON-parsed `config.json` every frame.**
  `tick()` runs once per frame at `FPS = 60`, so this was 60 SD card reads per
  second for the lifetime of the process. Now cached for 5 seconds. The
  per-frame read also meant editing the config was an instant shutdown trigger
  rather than a setting change.
- **Sleep warning overlay was drawn for the wrong panel.** It allocated a
  `640x480` surface and centered text at `x=320` on an 800x480 display, so the
  dimming covered only the left 640 px and the text sat 80 px left of center.
  Now derived from `screen.get_size()`.
- **Two `SysFont` objects allocated per warning frame.** Now cached at module
  level.
- **Palette lookups raised `KeyError` on incomplete themes.** `p["accent"]` and
  `p["dim"]` were indexed directly. Now `.get()` with fallbacks.
- **`mintcalc.py` was missing from both OTA file lists** despite being imported
  unconditionally by `mintos.py`. Added to `LAUNCHER_FILES` in `updater.py` and
  `FILES` in `deploy-launcher.sh`. This is the same class of defect that made
  2.0.2 unbootable.

### Added

- **`scripts/check-launcher-imports.py`**, a publish guard that refuses to ship
  when a launcher module imports a name that does not exist. It resolves
  `from launcher.MOD import NAME`, `from launcher import MOD`,
  `import launcher.MOD`, and relative forms `from . import MOD` and
  `from .MOD import NAME`. The relative forms were skipped entirely by the first
  version of the guard, which matters because `sleep_timer.py` uses exactly
  that syntax. Run against the full tree, all 24 modules resolve.

### Known issues

- The image still ships `/etc/resolv.conf` copied from the CI runner, pointing
  at `127.0.0.53` for a `systemd-resolved` that is not installed, plus an Azure
  internal search domain. DNS fails on a fresh flash until the file is replaced.
  Fix belongs in `build-rootfs.sh`.
- `launcher/mintfb.py` is referenced by the `app_env()` docstring but does not
  exist. Nothing imports it, so it is documentation drift rather than a crash.

---

## [2.0.2] - 2026-08-28 "Spearmint"

Demoted to prerelease after the fact. The image boots but never reaches the
launcher.

### Fixed

- **`battery.py` defined no `draw_bar`.** `mintos.py` imported it at module
  scope, so the launcher raised `ImportError` on every start, hit
  `StartLimitBurst=3` within five seconds, and left a black screen with no
  visible cause.
- **`mintkit-expand.service` pointed at `/usr/bin/resize2fs`.** On Debian
  bookworm it lives in `/usr/sbin`. The unit failed on first boot and the root
  filesystem stayed at 1.7 GB, 97% full, on a 64 GB card.

### Known issues

- The launcher still does not start. `mintos.py` imports `mintcalc`, which does
  not exist in this release. Fixed in 2.0.3.

---

## [2.0.1] - 2026-08-27 "Spearmint"

### Added

- **`launcher/inputbridge.py`.** With `SDL_VIDEODRIVER=offscreen` SDL provides
  no input backend, so no keypress or gamepad event had ever reached the
  launcher on hardware. The bridge reads `/dev/input/event*` directly, decodes
  the 24-byte `llHHi` event struct, maps keycodes to pygame keysyms, and posts
  `KEYDOWN`/`KEYUP` into the pygame queue from a daemon thread. Standard library
  only, rescans for new devices every 3 seconds. Verified on hardware decoding a
  Logitech K760 over Bluetooth on `event1`.

### Known issues

- Launcher does not start, same `mintcalc` `ImportError` as 2.0.2.

---

## [2.0.0] - 2026-08-27 "Spearmint"

The launcher was being killed by the OOM reaper roughly every 90 seconds on a
real device, and had been since at least 21 August. Every fix in this release
comes from evidence on hardware, not from documentation. Where the docs and the
code disagreed, the code won.

### Fixed

- **Clip capture exhausted system memory and the OOM killer took the launcher.**
  `MAX_CLIP_FRAMES` was `15 * 30`, or 450 frames. The panel is 800x480 and
  surfaces are 32bpp, so each `surface.copy()` costs 1.46 MB and the eviction
  ceiling was 658 MB on a machine that shows 357 MB. The cap was unreachable,
  so `pop(0)` never fired, the process paged frame data to the SD card, and the
  kernel killed it at 186 MB anon RSS. Now 30 frames, about 44 MB.
  Measured after the fix: RSS flat at 91 MB across 12 samples, previously
  climbing 50 to 155 MB at roughly 2.6 MB/s. Swap use dropped from 95 MB to 9 MB.
- **Every restricted app launch raised `AttributeError`.** Four calls in
  `mintos.py` targeted a parental controls API that does not exist:
  `is_enabled()` to `is_locked(app_id)`, `prompt_pin()` called with three
  arguments instead of two, `time_limit_reached()` to `check_time_limit()`, and
  `log_playtime(0)` to `record_session(0.0)`.
- **Black screen on boot.** `mintkit.service` set
  `SDL_VIDEODRIVER=kmsdrm`, but the launcher packs RGB565 and writes to
  `/dev/fb0` itself. Now `offscreen`.
- **Repeated FAT32 corruption of the boot partition.** The service unit carried
  `DefaultDependencies=no`, which left it unordered against `umount.target`, so
  shutdown killed it after the filesystems were already gone. Removed. `/boot`
  now also mounts read-only, since FAT32 has no journal.
- **Crashes were invisible for months.** The unit sent stdout to `tty`, which
  swallowed every `print()` and traceback. Now `StandardOutput=journal`,
  `StandardInput=null`.
- **`MemoryMax` was silently ignored.** The memory cgroup controller was
  compiled in but disabled at boot. Added `cgroup_enable=memory cgroup_memory=1`
  to the kernel cmdline, along with `video=HDMI-A-1:800x480@60` and
  `vt.global_cursor_default=0`. Confirmed: `/proc/cgroups` moved from
  `memory 0 38 0` to `memory 0 49 1` and `memory.max` appeared as 314572800.
- **Crash loop on failure.** `RestartSec=0` against an instant-crash bug is a
  spin loop. Now `RestartSec=5` with `StartLimitBurst=3` in 60 seconds.
- **`gpio` and `spi` groups never existed in the image,** so
  `99-mintkit.rules` discarded its `GROUP=` lines on every boot with
  "Unknown group". Both are now created before `useradd`, and the `mintkit`
  user gained `render`, `adm`, and `systemd-journal`.
- **Undeclared runtime dependencies.** `python3-evdev` and `python3-numpy` are
  both imported by `mintos.py` and neither was ever installed.
- **No editor in the image at all,** which is why `systemctl edit` failed with
  "temporary file is empty". Added `nano`.
- **`pocketmint.local` did not resolve.** Added `avahi-daemon` and `libnss-mdns`.
- **No RTC and no clock persistence.** All 11 recorded boots carried the same
  timestamp and one NTP correction stepped the clock by 121.9 days. Added
  `fake-hwclock`.
- **Truncated images could be published.** `release.sh` guards were existence
  checks only, so a half-written `.img` was renamed, compressed, torrented, and
  released without complaint. Added `validate_image()`, which checks size and
  reads the partition table, and switched `set -e` to `set -euo pipefail`.
- **`MINTKIT_VERSION` was three minors stale** at 0.5.0, and it feeds
  `IMG_NAME`, so release artifacts were named wrong. `GPU_MEM` also disagreed
  with `config.txt` at 64 versus the 128 actually in use.
- Both copies of the launcher were CRLF. Now LF, matching every other file.

### Added

- **`scripts/deploy-launcher.sh`.** Nothing in this repo had ever published the
  OTA launcher files. `updater.py` fetches `mintos.py` and `updater.py` from
  `/launcher/` on the web server, and no script wrote there, while
  `OtaManager` decided an update existed by comparing against the latest
  GitHub release tag. Tagging a release therefore told every device an update
  was available and then served it the old code. The new script compiles each
  file, verifies the version string matches, and publishes by atomic rename.
- `deploy.sh` now publishes the launcher when `LAUNCHER_VERSION` is set, and
  only overwrites live HTML behind `DEPLOY_HTML=1`.
- `ExecStartPre` clears the framebuffer before start. Stride 1600 times 480
  rows is 768000 bytes exactly.

### Changed

- `MemoryMax=300M` on the launcher service as a backstop.
- `SupplementaryGroups=input video render`, required because `offscreen`
  disables SDL input and the evdev thread needs `input`.
- `TZ=America/Chicago` and `PYTHONPATH` set explicitly in the unit.

### Known issues

- **The repo contains two divergent copies of the launcher tree,**
  `scripts/rootfs/launcher/` and `rootfs/launcher/`. `mintos.py` differs by the
  whole of `app_env()` plus the `cwd=` and `env=` arguments to `Popen`, and the
  two `99-mintkit.rules` are entirely different rule sets. Which tree gets
  copied into the image decides whether the screen works. `deploy-launcher.sh`
  defaults to `rootfs/launcher`, which is a choice and not a fact.
- **Clip capture is about 2 seconds, not 30.** Buffering full Surfaces at
  800x480 cannot reach 30 seconds on 512 MB. The redesign is to buffer
  downscaled RGB565 bytes, 192 KB per frame, and to allocate only once capture
  starts.
- **The published checksums may not match the published image.** CI builds and
  compresses the release asset, while `release.sh` computed SHA256 and MD5 from
  a separate local build and wrote those into `download.html`. Two independent
  debootstrap builds are not byte-identical.
- **CI produces no torrent.** `mktorrent` only ever ran inside `release.sh`, so
  the magnet link and torrent on the download page can lag the release.
- **`scripts/update-web.sh` is a stale copy of `release.sh`** from an older
  revision. It force-pushes and creates releases. Do not run it.
- The launcher spends about 31 percent of a core converting RGB888 to RGB565
  every frame, which is why the effective frame rate is near 7 and not 60.
- `mintos.cpython-312.pyc` is committed and the device runs Python 3.11.

---

## Earlier releases

Everything below was produced automatically by `release.sh` from
`git log LAST_TAG..HEAD`. Because tags were repeatedly force-moved onto new
commits, the ranges overlap and most entries only say which release preceded
them. Four separate `v1.3.1` sections existed, and `v1.0.2` and `v1.0.3` were
identical. They are collapsed to one entry per version here. Treat the dates as
approximate and the contents as near meaningless.

## [1.3.1] - 2026-06-01

- Foxfire. Re-tagged onto entirely different code on 2026-08-27, so two
  different images have been distributed under this version number. Prefer
  2.0.0.

## [1.3.0] - 2026-05-31

## [1.2.8] - 2026-05-31

## [1.2.7] - 2026-05-31

## [1.2.6] - 2026-05-31

## [1.2.5] - 2026-05-30

## [1.2.4] - 2026-05-29

## [1.2.3] - 2026-05-29

## [1.2.2] - 2026-05-28

## [1.2.1] - 2026-05-28

## [1.2.0] - 2026-05-28

## [1.1.2] - 2026-05-27

## [1.1.1] - 2026-05-27

## [1.1.0] - 2026-05-27

## [1.0.3] - 2026-05-27

- Fix xz group permission error, chown `dist/` before compress.
- Fix `IMAGE_SIZE_MB` unbound variable in `build-image.sh`.
- Add udev rules for mintkit device access.

## [1.0.2] - 2026-05-24

- Same contents as 1.0.3. Duplicate entry, kept for the version record only.
