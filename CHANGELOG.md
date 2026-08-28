# v2.0.1 (28 August 2026)

- feat(input): add evdev input bridge so keyboards and gamepads reach the launcher
- Added inputbridge.py
- Fix: Added inputbridge.py to add keyboard support
- chore: bump MINTKIT_VERSION to 2.0.0

Changelog
All notable changes to MintKit are recorded here. Entries from 2.0.0 onward are
written by hand. Everything below the "Earlier releases" divider was generated
mechanically from commit subjects and is not a reliable record.

Format: Keep a Changelog.
Versioning: Semantic Versioning.

[2.0.0] - 2026-08-27 "Spearmint"
The launcher was being killed by the OOM reaper roughly every 90 seconds on a
real device, and had been since at least 21 August. Every fix in this release
comes from evidence on hardware, not from documentation. Where the docs and the
code disagreed, the code won.

Fixed
Clip capture exhausted system memory and the OOM killer took the launcher.
MAX_CLIP_FRAMES was 15 * 30, or 450 frames. The panel is 800x480 and
surfaces are 32bpp, so each surface.copy() costs 1.46 MB and the eviction
ceiling was 658 MB on a machine that shows 357 MB. The cap was unreachable,
so pop(0) never fired, the process paged frame data to the SD card, and the
kernel killed it at 186 MB anon RSS. Now 30 frames, about 44 MB.
Measured after the fix: RSS flat at 91 MB across 12 samples, previously
climbing 50 to 155 MB at roughly 2.6 MB/s. Swap use dropped from 95 MB to 9 MB.
Every restricted app launch raised AttributeError. Four calls in
mintos.py targeted a parental controls API that does not exist:
is_enabled() to is_locked(app_id), prompt_pin() called with three
arguments instead of two, time_limit_reached() to check_time_limit(), and
log_playtime(0) to record_session(0.0).
Black screen on boot. mintkit.service set
SDL_VIDEODRIVER=kmsdrm, but the launcher packs RGB565 and writes to
/dev/fb0 itself. Now offscreen.
Repeated FAT32 corruption of the boot partition. The service unit carried
DefaultDependencies=no, which left it unordered against umount.target, so
shutdown killed it after the filesystems were already gone. Removed. /boot
now also mounts read-only, since FAT32 has no journal.
Crashes were invisible for months. The unit sent stdout to tty, which
swallowed every print() and traceback. Now StandardOutput=journal,
StandardInput=null.
MemoryMax was silently ignored. The memory cgroup controller was
compiled in but disabled at boot. Added cgroup_enable=memory cgroup_memory=1
to the kernel cmdline, along with video=HDMI-A-1:800x480@60 and
vt.global_cursor_default=0. Confirmed: /proc/cgroups moved from
memory 0 38 0 to memory 0 49 1 and memory.max appeared as 314572800.
Crash loop on failure. RestartSec=0 against an instant-crash bug is a
spin loop. Now RestartSec=5 with StartLimitBurst=3 in 60 seconds.
gpio and spi groups never existed in the image, so
99-mintkit.rules discarded its GROUP= lines on every boot with
"Unknown group". Both are now created before useradd, and the mintkit
user gained render, adm, and systemd-journal.
Undeclared runtime dependencies. python3-evdev and python3-numpy are
both imported by mintos.py and neither was ever installed.
No editor in the image at all, which is why systemctl edit failed with
"temporary file is empty". Added nano.
pocketmint.local did not resolve. Added avahi-daemon and libnss-mdns.
No RTC and no clock persistence. All 11 recorded boots carried the same
timestamp and one NTP correction stepped the clock by 121.9 days. Added
fake-hwclock.
Truncated images could be published. release.sh guards were existence
checks only, so a half-written .img was renamed, compressed, torrented, and
released without complaint. Added validate_image(), which checks size and
reads the partition table, and switched set -e to set -euo pipefail.
MINTKIT_VERSION was three minors stale at 0.5.0, and it feeds
IMG_NAME, so release artifacts were named wrong. GPU_MEM also disagreed
with config.txt at 64 versus the 128 actually in use.
Both copies of the launcher were CRLF. Now LF, matching every other file.
Added
scripts/deploy-launcher.sh. Nothing in this repo had ever published the
OTA launcher files. updater.py fetches mintos.py and updater.py from
/launcher/ on the web server, and no script wrote there, while
OtaManager decided an update existed by comparing against the latest
GitHub release tag. Tagging a release therefore told every device an update
was available and then served it the old code. The new script compiles each
file, verifies the version string matches, and publishes by atomic rename.
deploy.sh now publishes the launcher when LAUNCHER_VERSION is set, and
only overwrites live HTML behind DEPLOY_HTML=1.
ExecStartPre clears the framebuffer before start. Stride 1600 times 480
rows is 768000 bytes exactly.
Changed
MemoryMax=300M on the launcher service as a backstop.
SupplementaryGroups=input video render, required because offscreen
disables SDL input and the evdev thread needs input.
TZ=America/Chicago and PYTHONPATH set explicitly in the unit.
Known issues
The repo contains two divergent copies of the launcher tree,
scripts/rootfs/launcher/ and rootfs/launcher/. mintos.py differs by the
whole of app_env() plus the cwd= and env= arguments to Popen, and the
two 99-mintkit.rules are entirely different rule sets. Which tree gets
copied into the image decides whether the screen works. deploy-launcher.sh
defaults to rootfs/launcher, which is a choice and not a fact.
Clip capture is about 2 seconds, not 30. Buffering full Surfaces at
800x480 cannot reach 30 seconds on 512 MB. The redesign is to buffer
downscaled RGB565 bytes, 192 KB per frame, and to allocate only once capture
starts.
The published checksums may not match the published image. CI builds and
compresses the release asset, while release.sh computed SHA256 and MD5 from
a separate local build and wrote those into download.html. Two independent
debootstrap builds are not byte-identical.
CI produces no torrent. mktorrent only ever ran inside release.sh, so
the magnet link and torrent on the download page can lag the release.
scripts/update-web.sh is a stale copy of release.sh from an older
revision. It force-pushes and creates releases. Do not run it.
The launcher spends about 31 percent of a core converting RGB888 to RGB565
every frame, which is why the effective frame rate is near 7 and not 60.
mintos.cpython-312.pyc is committed and the device runs Python 3.11.
Earlier releases
Everything below was produced automatically by release.sh from
git log LAST_TAG..HEAD. Because tags were repeatedly force-moved onto new
commits, the ranges overlap and most entries only say which release preceded
them. Four separate v1.3.1 sections existed, and v1.0.2 and v1.0.3 were
identical. They are collapsed to one entry per version here. Treat the dates as
approximate and the contents as near meaningless.

[1.3.1] - 2026-06-01
Foxfire. Re-tagged onto entirely different code on 2026-08-27, so two
different images have been distributed under this version number. Prefer
2.0.0.
[1.3.0] - 2026-05-31
[1.2.8] - 2026-05-31
[1.2.7] - 2026-05-31
[1.2.6] - 2026-05-31
[1.2.5] - 2026-05-30
[1.2.4] - 2026-05-29
[1.2.3] - 2026-05-29
[1.2.2] - 2026-05-28
[1.2.1] - 2026-05-28
[1.2.0] - 2026-05-28
[1.1.2] - 2026-05-27
[1.1.1] - 2026-05-27
[1.1.0] - 2026-05-27
[1.0.3] - 2026-05-27
Fix xz group permission error, chown dist/ before compress.
Fix IMAGE_SIZE_MB unbound variable in build-image.sh.
Add udev rules for mintkit device access.
[1.0.2] - 2026-05-24
Same contents as 1.0.3. Duplicate entry, kept for the version record only.