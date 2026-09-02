#!/usr/bin/env python3
# rootfs/launcher/mintsetup.py  --  MintKit first boot installer
"""Runs once, before the launcher UI, on a freshly flashed device.

Writes /home/mintkit/.setup-complete when finished so it never runs again.
Every step is skippable: a device with no network still reaches the launcher.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

LAUNCHER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(LAUNCHER_DIR))

# The launcher normally supplies these. mintsetup runs before the launcher UI,
# so set them here too rather than depending on the parent's environment.
os.environ.setdefault("SDL_VIDEODRIVER", "offscreen")
os.environ.setdefault("SDL_AUDIODRIVER", os.environ.get("MINTKIT_AUDIO", "alsa"))

import pygame
import mintfb  # noqa: F401  -- reassigns pygame.display.flip and starts the input bridge

W, H = 800, 480
BG   = (14, 20, 24)
FG   = (232, 240, 236)
ACC  = (94, 226, 173)
DIM  = (110, 130, 124)

SETUP_FLAG = Path("/home/mintkit/.setup-complete")
WPA_CONF   = Path("/etc/wpa_supplicant/wpa_supplicant.conf")
AUDIO_GATE = os.environ.get("MINTSETUP_AUDIO") == "1"
MUSIC      = LAUNCHER_DIR / "assets" / "setup.ogg"

TIMEZONES = [
    "America/Chicago",
    "America/New_York",
    "America/Denver",
    "America/Los_Angeles",
    "Europe/London",
    "UTC",
]


def sh(args, timeout=20):
    """Run a command, never raise. Returns (ok, combined output)."""
    try:
        p = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return p.returncode == 0, (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return False, str(e)


class UI:
    def __init__(self):
        pygame.init()
        pygame.mouse.set_visible(False)
        self.screen = pygame.display.set_mode((W, H))
        self.clock  = pygame.time.Clock()
        self.f_big  = pygame.font.Font(None, 52)
        self.f_mid  = pygame.font.Font(None, 34)
        self.f_sml  = pygame.font.Font(None, 26)
        if AUDIO_GATE and MUSIC.exists():
            try:
                pygame.mixer.init()
                pygame.mixer.music.load(str(MUSIC))
                pygame.mixer.music.set_volume(0.4)
                pygame.mixer.music.play(-1)
            except Exception:
                pass

    def frame(self, step, total, title, subtitle=""):
        self.screen.fill(BG)
        self.screen.blit(self.f_sml.render(f"MintKit setup  {step}/{total}", True, DIM), (40, 32))
        self.screen.blit(self.f_big.render(title, True, FG), (40, 70))
        if subtitle:
            self.screen.blit(self.f_sml.render(subtitle, True, DIM), (40, 126))
        pygame.draw.line(self.screen, (30, 44, 40), (40, 160), (W - 40, 160), 2)

    def hint(self, text):
        self.screen.blit(self.f_sml.render(text, True, DIM), (40, H - 48))

    def flush(self):
        pygame.display.flip()
        self.clock.tick(30)

    def message(self, step, total, title, lines, hint="Press ENTER to continue"):
        """Blocking notice. Returns when ENTER or ESC is pressed."""
        while True:
            for ev in pygame.event.get():
                if ev.type == pygame.KEYDOWN and ev.key in (
                    pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE
                ):
                    return
            self.frame(step, total, title)
            y = 200
            for ln in lines:
                self.screen.blit(self.f_mid.render(ln, True, FG), (40, y))
                y += 40
            self.hint(hint)
            self.flush()

    def pick(self, step, total, title, subtitle, options, allow_skip=True):
        """List picker. Returns the chosen string, or None if skipped."""
        idx = 0
        top = 0
        rows = 7
        while True:
            for ev in pygame.event.get():
                if ev.type != pygame.KEYDOWN:
                    continue
                if ev.key in (pygame.K_UP, pygame.K_w):
                    idx = max(0, idx - 1)
                elif ev.key in (pygame.K_DOWN, pygame.K_s):
                    idx = min(len(options) - 1, idx + 1)
                elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    return options[idx] if options else None
                elif ev.key == pygame.K_ESCAPE and allow_skip:
                    return None
            if idx < top:
                top = idx
            elif idx >= top + rows:
                top = idx - rows + 1

            self.frame(step, total, title, subtitle)
            y = 190
            for i in range(top, min(len(options), top + rows)):
                sel = i == idx
                if sel:
                    pygame.draw.rect(self.screen, (22, 34, 30), (32, y - 6, W - 64, 38))
                    pygame.draw.rect(self.screen, ACC, (32, y - 6, 4, 38))
                self.screen.blit(
                    self.f_mid.render(options[i], True, ACC if sel else FG), (52, y)
                )
                y += 38
            self.hint("UP and DOWN to move, ENTER to choose" + (", ESC to skip" if allow_skip else ""))
            self.flush()

    def text(self, step, total, title, subtitle, default="", secret=False, allow_skip=True):
        """Single line text entry. Returns the string, or None if skipped."""
        buf = default
        while True:
            for ev in pygame.event.get():
                if ev.type != pygame.KEYDOWN:
                    continue
                if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    return buf.strip()
                if ev.key == pygame.K_ESCAPE and allow_skip:
                    return None
                if ev.key == pygame.K_BACKSPACE:
                    buf = buf[:-1]
                elif ev.unicode and ev.unicode.isprintable():
                    buf += ev.unicode
            self.frame(step, total, title, subtitle)
            shown = ("*" * len(buf)) if secret else buf
            pygame.draw.rect(self.screen, (22, 34, 30), (40, 210, W - 80, 56))
            pygame.draw.rect(self.screen, ACC, (40, 210, W - 80, 56), 2)
            self.screen.blit(self.f_mid.render(shown + "_", True, FG), (56, 224))
            self.hint("Type, then ENTER" + (", ESC to skip" if allow_skip else ""))
            self.flush()


def step_timezone(ui, step, total):
    tz = ui.pick(step, total, "Time zone", "Used for the clock and screenshots.", TIMEZONES)
    if tz:
        sh(["sudo", "timedatectl", "set-timezone", tz])


def step_hostname(ui, step, total):
    name = ui.text(
        step, total, "Device name",
        "How this handheld appears on your network.",
        default="pocketmint",
    )
    if not name:
        return
    # Hostnames: letters, digits and hyphens only.
    name = re.sub(r"[^A-Za-z0-9-]", "-", name).strip("-").lower()[:32]
    if name:
        sh(["sudo", "hostnamectl", "set-hostname", name])


def scan_wifi():
    ok, out = sh(["sudo", "iwlist", "wlan0", "scan"], timeout=25)
    if not ok:
        return []
    seen = []
    for m in re.finditer(r'ESSID:"([^"]*)"', out):
        ssid = m.group(1).strip()
        if ssid and ssid not in seen:
            seen.append(ssid)
    return seen[:24]


def step_wifi(ui, step, total):
    ui.frame(step, total, "Wi-Fi", "Scanning...")
    ui.flush()
    nets = scan_wifi()
    if not nets:
        ui.message(
            step, total, "Wi-Fi",
            ["No networks found.", "You can connect later from Settings."],
        )
        return
    ssid = ui.pick(step, total, "Wi-Fi", "Choose a network.", nets)
    if not ssid:
        return
    psk = ui.text(step, total, "Wi-Fi password", ssid, secret=True)
    if psk is None:
        return
    ok, out = sh(["wpa_passphrase", ssid, psk])
    if not ok:
        ui.message(step, total, "Wi-Fi", ["Could not build the config.", out.strip()[:60]])
        return
    block = "\n".join(l for l in out.splitlines() if not l.strip().startswith("#psk="))
    try:
        # tee -a because this file is root owned and we are not.
        p = subprocess.run(
            ["sudo", "tee", "-a", str(WPA_CONF)],
            input="\n" + block + "\n",
            capture_output=True, text=True, timeout=10,
        )
        wrote = p.returncode == 0
    except Exception:
        wrote = False
    if wrote:
        sh(["sudo", "systemctl", "restart", "wpa_supplicant"], timeout=25)
        ui.message(step, total, "Wi-Fi", [f"Saved {ssid}.", "It will connect in a moment."])
    else:
        ui.message(step, total, "Wi-Fi", ["Could not write the config."])


def step_clock(ui, step, total):
    ok, out = sh(["timedatectl", "show", "-p", "NTPSynchronized", "--value"], timeout=10)
    synced = ok and out.strip() == "yes"
    if synced:
        ui.message(step, total, "Clock", ["Clock is synchronised.", "HTTPS will work correctly."])
        return
    sh(["sudo", "systemctl", "restart", "systemd-timesyncd"], timeout=15)
    ui.message(
        step, total, "Clock",
        ["Clock not synchronised yet.",
         "This device has no battery backed clock,",
         "so it needs the network to know the time."],
    )


def step_tailscale(ui, step, total):
    if not Path("/usr/bin/tailscale").exists():
        return
    go = ui.pick(
        step, total, "Tailscale",
        "Join your private network? You can do this later.",
        ["Yes, set it up now", "Skip"],
        allow_skip=False,
    )
    if go != "Yes, set it up now":
        return
    ui.frame(step, total, "Tailscale", "Requesting a login link...")
    ui.flush()
    sh(["sudo", "systemctl", "enable", "--now", "tailscaled"], timeout=25)
    ok, out = sh(["sudo", "tailscale", "up", "--timeout=1s"], timeout=30)
    m = re.search(r"https://login\.tailscale\.com/\S+", out)
    if not m:
        ui.message(step, total, "Tailscale", ["No login link returned.", "Try again from Settings."])
        return
    url = m.group(0)
    # Split the URL so it fits the 800px width at this font size.
    head, tail = url[:38], url[38:]
    ui.message(
        step, total, "Tailscale",
        ["Open this on your phone or laptop:", "", head, tail],
        hint="Press ENTER once you have approved it",
    )


def main():
    ui = UI()
    steps = [step_timezone, step_hostname, step_wifi, step_clock, step_tailscale]
    total = len(steps) + 1

    ui.message(
        1, total, "Welcome to MintKit",
        ["A few questions, then you are done.",
         "Press ESC on any screen to skip it."],
    )
    for i, fn in enumerate(steps, start=2):
        try:
            fn(ui, i, total)
        except Exception as e:
            # A failed step must never prevent reaching the launcher.
            print(f"[setup] step {fn.__name__} failed: {e}", file=sys.stderr)

    try:
        SETUP_FLAG.write_text("ok\n")
    except Exception as e:
        print(f"[setup] could not write {SETUP_FLAG}: {e}", file=sys.stderr)

    ui.message(total, total, "All set", ["Starting MintKit..."], hint="Press ENTER")
    try:
        pygame.mixer.music.fadeout(600)
    except Exception:
        pass
    pygame.quit()


if __name__ == "__main__":
    main()