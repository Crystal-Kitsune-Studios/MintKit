# MintKit

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
