# MintKit

**MintKit** is the official operating system for the **PocketMint** handheld console by Crystal Kitsune Studios. A custom Linux OS for the Raspberry Pi Zero 2 W - stripped to a retro-green pygame launcher with no desktop, no clutter, and a sub-10s boot time.

---

## Features

- 🟢 **Purpose-built launcher** - pygame UI designed for 256x240, full controller nav
- 🎮 **Full gamepad support** - udev button mapping for D-Pad, I, II, RUN, O, L/R
- 🛍️ **PocketMall integration** - browse, install and update games/apps on-device
- ⚡ **Fast boot** - systemd-minimal, autologin, straight to launcher. No desktop.
- 🔊 **Hardware controls** - brightness (PWM backlight) and volume (ALSA) via launcher
- 📼 **Physical cartridge support** - udev auto-mount and launch on cartridge insert
- 🔓 **Open source** - MIT license. Build your own image, write your own games.

---

## System Overview

| Component | Details |
| --- | --- |
| Base | Ubuntu Jammy 22.04 ARM64 (debootstrap minimal) |
| Kernel | Linux 6.1 LTS - Raspberry Pi kernel fork (rpi-6.1.y) |
| Bootloader | Pi GPU firmware (start.elf + config.txt) - no U-Boot needed |
| Init | systemd (minimal target, no desktop units) |
| Display | DRM/KMS framebuffer → pygame SDL2 (no X11, no Wayland) |
| Audio | ALSA (no PulseAudio) |
| Launcher | [mintos.py](http://mintos.py)  • Python 3 + pygame 2, runs as system service |

---

## Target Hardware

| Spec | Value |
| --- | --- |
| CPU | Broadcom BCM2710A1 - Quad-core Cortex-A53 @ 1GHz (Raspberry Pi Zero 2 W) |
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
  device-tree-compiler \
  python3-pygame libsdl2-dev \
  parted dosfstools e2fsprogs rsync git
```

### Clone and configure

```bash
git clone https://github.com/Crystal-Kitsune-Studios/MintKit
cd MintKit
cp config/mintkit.conf.example config/mintkit.conf
# Edit mintkit.conf to set wifi SSID, locale, etc.
```

### Build

```bash
export SCRIPT_DIR=$(pwd) ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu-

# Step 1 - fetch Pi boot firmware
sudo -E bash scripts/build-firmware.sh

# Step 2 - cross-compile kernel (~20-40 min, downloads ~1GB)
sudo -E bash scripts/build-kernel.sh

# Step 3 - build rootfs (debootstrap + launcher + games)
sudo -E bash scripts/build-rootfs.sh

# Step 4 - assemble flashable image
sudo -E bash scripts/build-image.sh
```

Output: `dist/mintkit-pizero2w.img`

### Flash to SD card

```bash
# Replace /dev/sdX with your SD card device (check with lsblk)
sudo dd if=dist/mintkit-pizero2w.img of=/dev/sdX bs=4M status=progress conv=fsync
```

### Image layout

```jsx
┌─────────────────────────────────────────────────────────┐
│  1MiB-65MiB  (FAT32, BOOT) │ Pi firmware + kernel8.img  │
│  65MiB-end   (ext4,  ROOT) │ Root filesystem + launcher  │
└─────────────────────────────────────────────────────────┘
No U-Boot - Pi GPU firmware boots kernel8.img directly.
```

---

## Running the Launcher on PC (dev/emulator)

No hardware needed for launcher development:

```bash
pip install pygame
cd rootfs/launcher
python3 mintos.py   # Runs at 640x480 in a window
```

Controller input is mapped to keyboard in `--dev` mode:

`WASD` = D-Pad, `Z` = I, `X` = II, `Enter` = RUN, `A` = O

---

## Writing Games for PocketMint

Games are pygame apps or compiled ARM64 binaries. Drop them in `/home/mintkit/games/` with a `game.json` manifest and the launcher picks them up.

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

```jsx
MintKit/
  .github/workflows/build.yml  # CI/CD - builds .img on push/tag
  config/
    mintkit.conf.example       # Build config template
    kernel.config              # Pi Zero 2 W kernel config (bcm2711_defconfig)
  kernel/
    patches/                   # Pi kernel patches
  rootfs/
    launcher/mintos.py         # pygame launcher
    games/crypt-raid/          # Bundled game
    services/mintkit.service   # Launcher autostart service
    udev/99-mintkit.rules      # Button + cartridge udev rules
  scripts/
    build-firmware.sh          # Fetch Pi boot firmware
    build-kernel.sh            # Cross-compile Pi kernel
    build-rootfs.sh            # debootstrap Ubuntu Jammy ARM64
    build-image.sh             # Assemble FAT32+ext4 .img
  install.sh                   # One-command installer (Pi OS base)
  dist/                        # Output images (gitignored)
```

---

## Launcher Screens

- **Library** - browse and launch installed games and ROMs
- **PocketMall** - download games, apps, emulators and media tools
- **Friends** - local and online multiplayer, friend list
- **Settings** - WiFi, brightness, volume, player name, system info
- **Media** - music and video player

---

## License

MIT License - Crystal Kitsune Studios 2026

See [LICENSE](LICENSE) for full text.

---

*Part of the PocketMint project by [Crystal Kitsune Studios](https://crystal-kitsune-studios.com)*
