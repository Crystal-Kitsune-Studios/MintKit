# v3.0.0 (2 September 2026)

- MintKit 3.0.0 Peppermint: manifest driven OTA, first boot installer, mintfb input bridge fix
- Fix child app framebuffer handoff
- Fix child app framebuffer handoff
- Fix child app framebuffer handoff

## [3.0.0] - 2026-09-01 "Peppermint"

First release on the Peppermint line. The 2.x Spearmint series is closed.

### Added
- Manifest driven OTA. The server publishes manifest.json and the device asks
  it which files to fetch, instead of relying on the list baked into the copy
  of updater.py it is currently running.
- Over the air updates for apps in /home/mintkit/games. Until now OTA covered
  the launcher only, so a stale app could never heal itself.
- First boot installer, rootfs/launcher/mintsetup.py, covering time zone,
  device name, Wi-Fi, clock sync and Tailscale login. Gated on
  /home/mintkit/.setup-complete and run with subprocess.run so it cannot race
  the launcher for /dev/fb0.
- version.txt on the OTA server as an update trigger, so future releases no
  longer depend on the GitHub releases API.
- rootfs/launcher/__init__.py committed, removing a hidden dependency on a
  file that only ever existed on one device.

### Fixed
- mintfb.py started the evdev input bridge twice. Every standalone app was
  running two reader threads on the same devices, which produced duplicated
  keypresses.
- The version fallback regex in updater.py looked for a double quote while
  mintos.py uses single quotes, so it never matched. Any device without a
  version.txt reported 0.0.0 and would be offered a phantom update.
- apply_update swallowed failed downloads and still recorded the new version.
  Failures are now collected, named, and the version is only written after a
  fully successful run.
- mintos.py imported launcher.sleep, which does not exist in the repo. It
  worked only because of an uncommitted symlink on one device, so a fresh
  flash would have failed before the splash screen.

### Changed
- apply_update prunes old .bak files instead of accumulating one generation
  per release forever.
- deploy-launcher.sh publishes app files and generates manifest.json from what
  it actually uploaded, so FILES and LAUNCHER_FILES can no longer drift apart.

### Removed
- mintkit_update.py, dead since updater.py replaced it.
- Tracked bytecode, rootfs/launcher/__pycache__, now gitignored.

### Known limitations
- mintsetup.py does not reach existing devices until 3.0.1. Devices take this
  release using 2.2.1's file list, which does not name it. Fresh flashes get
  it from the image immediately.
- Manifest driven downloading governs behaviour from 3.0.1 onward for the same
  reason. 3.0.0 is the release that plants it.