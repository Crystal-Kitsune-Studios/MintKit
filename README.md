# MintKit

**MintKit** is the official operating system for the **PocketMint** handheld console by Crystal Kitsune Studios. A custom Linux Mint-based embedded OS — stripped to a retro-green pygame launcher with no desktop, no clutter, and a sub-10s boot time.

---

## Features

- 🟢 **Purpose-built launcher** — pygame UI designed for 256x240, full controller nav
- 🎮 **Full gamepad support** — udev button mapping for D-Pad, I, II, RUN, O, L/R
- 🛍️ **PocketMall integration** — browse, install and update games/apps on-device
- ⚡ **Fast boot** — systemd-minimal, autologin, straight to launcher. No desktop.
- 🔊 **Hardware controls** — brightness (PWM backlight) and volume (ALSA) via launcher
- 📼 **Physical cartridge support** — udev auto-mount and launch on cartridge insert
- 🔓 **Open source** — MIT license. Build your own image, write your own games.

---

## System Overview

| Component | Details |
| --- | --- |
| Base | Linux Mint 21 (Ubuntu Jammy core, debootstrap minimal) |
| Kernel | Linux 6.1 LTS + Rockchip RK3566 BSP patches |
| Bootloader | U-Boot 2024.01 (RK3566 SPL) |
| Init | systemd (minimal target, no desktop units) |
| Display | DRM/KMS framebuffer → pygame SDL2 (no X11, no Wayland) |
| Audio | ALSA (no PulseAudio) |
| Launcher | [mintos.py](http://mintos.py) — Python 3 + pygame 2, runs as system service |

---

## Target Hardware

| Spec | Value |
| --- | --- |
| CPU | Rockchip RK3566 — Quad-core Cortex-A55 @ 1.8GHz |
| Display | 256x240 backlit IPS, 60fps |
| Input | D-Pad, I, II, RUN, O, L + R shoulder buttons |
| Storage | Physical cartridge slot + internal eMMC |
| Audio | Stereo speakers, 3.5mm headphone jack |
| Connectivity | WiFi 802.11 b/g/n, USB-C charging |

---

## Building the OS Image

### Dependencies

```bash
sudo apt install -y \
  debootstrap qemu-user-static binfmt-support \
  gcc-aarch64-linux-gnu binutils-aarch64-linux-gnu \
  device-tree-compiler u-boot-tools \
  python3-pygame libsdl2-dev \
  parted dosfstools e2fsprogs
```

### Clone and configure

```bash
git clone https://github.com/Crystal-Kitsune-Studios/pocketmint
cd pocketmint
cp config/mintkit.conf.example config/mintkit.conf
# Edit mintkit.conf to set player name, wifi SSID, locale, etc.
```

### Build

```bash
# Full build (kernel + rootfs + image) — takes ~20–40 min
sudo ./build.sh rk3566

# Or build steps individually:
sudo ./scripts/build-kernel.sh rk3566    # Cross-compile kernel + DTB
sudo ./scripts/build-rootfs.sh           # debootstrap + overlay + launcher
sudo ./scripts/build-image.sh            # Pack into flashable .img
```

Output: `dist/mintkit-rk3566.img`

### Flash to SD card

```bash
# Replace /dev/sdX with your SD card device
sudo ./scripts/flash.sh dist/mintkit-rk3566.img /dev/sdX

# Or manually:
sudo dd if=dist/mintkit-rk3566.img of=/dev/sdX bs=4M status=progress
sync
```

### Image layout

```
┌─────────────────────────────────────────┐
│  Sector 0–63    │ GPT + U-Boot SPL      │
│  Sector 64–8191 │ U-Boot proper         │
│  Part 1 (FAT32) │ Kernel + DTB          │
│  Part 2 (ext4)  │ Root filesystem       │
│  Part 3 (ext4)  │ /opt/cks (games/apps) │
└─────────────────────────────────────────┘
```

---

## Running the Launcher on PC (dev/emulator)

No hardware needed for launcher development:

```bash
pip install pygame
cd rootfs/overlay/opt/cks/launcher
python3 mintos.py --dev   # Runs at 256x240 in a window
```

Controller input is mapped to keyboard in `--dev` mode:

`WASD` = D-Pad, `Z` = I, `X` = II, `Enter` = RUN, `A` = O

---

## Writing Games for PocketMint

Games are pygame apps or compiled ARM64 binaries. Drop them in `/opt/cks/games/` with a `game.json` manifest and the launcher picks them up.

**game.json:**

```json
{
  "name": "My Game",
  "dev": "Your Studio",
  "entry": "main.py",
  "version": "1.0.0"
}
```

**Minimal game template:**

```python
import pygame

pygame.init()
screen = pygame.display.set_mode((256, 240))
clock = pygame.time.Clock()

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:  # RUN button
                running = False

    screen.fill((10, 26, 16))
    pygame.display.flip()
    clock.tick(60)

pygame.quit()
```

Submit to **PocketMall** via [pocketmint.crystal-kitsune-studios.com](http://pocketmint.crystal-kitsune-studios.com).

---

## Project Structure

```
pocketmint/
  build.sh                  # Main build entry point
  config/
    mintkit.conf.example    # Build config template
    kernel.config           # Linux kernel config (RK3566)
    uboot.config            # U-Boot config
  kernel/
    patches/                # RK3566 BSP + display patches
  rootfs/
    overlay/                # Merged onto base rootfs
      etc/
        systemd/system/
          mintkit.service   # Launcher autostart service
        udev/rules.d/
          99-buttons.rules  # Button → input event mapping
          99-cartridge.rules
        mintkit/            # System config files
      opt/cks/
        launcher/           # mintos.py + assets
        games/              # Bundled games (Crypt Raid, etc.)
  scripts/
    build-kernel.sh
    build-rootfs.sh
    build-image.sh
    flash.sh
  dist/                     # Output images (gitignored)
```

---

## Launcher Screens

- **Library** — browse and launch installed games and ROMs
- **PocketMall** — download games, apps, emulators and media tools
- **Friends** — local and online multiplayer, friend list
- **Settings** — WiFi, brightness, volume, player name, system info
- **Media** — music and video player

---

## License

MIT License — Crystal Kitsune Studios 2026

See [LICENSE](LICENSE) for full text.

---

*Part of the PocketMint project by [Crystal Kitsune Studios](https://crystal-kitsune-studios.com)*# MintKit

**MintKit** is the official operating system for the **PocketMint** handheld console by Crystal Kitsune Studios. A custom Linux Mint fork stripped down to a retro-green pygame launcher - no desktop, no clutter. Boot straight into your games.

---

## Features

- 🟢 **Purpose-built launcher** - pygame-based UI designed for controllers, 256x240 display
- 🎮 **Full gamepad support** - udev button mapping for D-Pad, I, II, RUN, O, L/R
- 🛍️ **PocketMall integration** - browse, install and update games/apps from the device
- ⚡ **Fast boot** - autostart on boot, no login screen, no desktop environment
- 🔊 **Hardware controls** - brightness and volume mapped to launcher shortcuts
- 📼 **Physical cartridge support** - auto-detects games on cartridge mount
- 🔓 **Open source** - MIT license, build your own images, write your own games

---

## Quick Start (PC / emulator)

```bash
pip install pygame
python3 mintos.py
```

---

## Building for Hardware (RK3566)

```bash
# Clone the repo
git clone https://github.com/Crystal-Kitsune-Studios/pocketmint
cd mintkit

# Build image
sudo ./build.sh rk3566

# Flash to SD card (replace sdX with your card)
sudo ./scripts/flash.sh dist/mintkit-rk3566.img /dev/sdX
```

---

## Target Hardware

| Spec | Value |
| --- | --- |
| CPU | Rockchip RK3566 - Quad-core Cortex-A55 @ 1.8GHz |
| Display | 256x240 backlit IPS, 60fps |
| Input | D-Pad, I, II, RUN, O, L + R shoulder buttons |
| Storage | Physical cartridge slot + internal flash |
| Audio | Stereo speakers, 3.5mm headphone jack |
| Connectivity | WiFi 802.11 b/g/n, USB-C charging |

---

## Launcher Screens

- **Library** - browse and launch installed games and ROMs
- **PocketMall** - download games, apps, emulators and media tools
- **Friends** - local and online multiplayer, friend list
- **Settings** - WiFi, brightness, volume, player name, system info
- **Media** - music and video player

---

## Writing Games for PocketMint

Games are pygame applications or compiled binaries. Drop them in `/opt/cks/games/` and the launcher picks them up automatically.

```python
# Minimal MintKit game template
import pygame

pygame.init()
screen = pygame.display.set_mode((256, 240))
clock = pygame.time.Clock()

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:  # mapped to RUN button
                running = False

    screen.fill((10, 26, 16))  # MintKit green-black
    pygame.display.flip()
    clock.tick(60)

pygame.quit()
```

Submit finished games to **PocketMall** via [pocketmint.crystal-kitsune-studios.com](http://pocketmint.crystal-kitsune-studios.com).

---

## Project Structure

```
mintkit/
  mintos.py          # Main launcher
  mintos_cfg.json    # User config (wifi, player name, etc.)
  build.sh           # Image build script
  scripts/
    flash.sh         # SD card flash helper
    udev-buttons.sh  # Button mapping setup
  assets/
    fonts/           # Retro bitmap fonts
    sfx/             # UI sound effects
  games/             # Bundled games (e.g. Crypt Raid)
```

---

## License

MIT License - Crystal Kitsune Studios 2026

See [LICENSE](LICENSE) for full text.

---

*Part of the PocketMint project by [Crystal Kitsune Studios](https://crystal-kitsune-studios.com)*
