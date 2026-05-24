#!/usr/bin/env python3
# rootfs/launcher/settings.py -- System Settings (OS built-in)
import os, sys, platform, json, subprocess
from pathlib import Path
from . import themes as th   # same package

IS_LINUX = platform.system() == "Linux"

FPS    = 60
PAD    = 10
HEADER = 36
TAB_H  = 26
CONTENT_Y = HEADER + TAB_H + PAD
SCREEN_W, SCREEN_H = 640, 480

DATA_DIR    = Path(os.environ.get("MINTKIT_DATA", Path.home() / ".mintkit"))
CONFIG_FILE = DATA_DIR / "config.json"

import pygame

# ── Config ────────────────────────────────────────────────────────────────
def load_cfg():
    if CONFIG_FILE.exists():
        try: return json.loads(CONFIG_FILE.read_text())
        except Exception: pass
    return {}

def save_cfg(cfg):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))

# ── Tabs ────────────────────────────────────────────────────────────────
TABS = ["THEME", "WIFI", "DISPLAY", "SOUND", "SYSTEM"]

# ── Wi-Fi helpers ─────────────────────────────────────────────────────────
def scan_wifi():
    try:
        out = subprocess.check_output(
            ["sudo", "iwlist", "wlan0", "scan"],
            stderr=subprocess.DEVNULL, timeout=8, text=True)
        nets = []
        ssid = sig = None
        for line in out.splitlines():
            l = line.strip()
            if "ESSID:" in l:
                ssid = l.split('"')[1] if '"' in l else ""
            if "Signal level" in l:
                try: sig = int(l.split("Signal level=")[1].split(" ")[0].split("/")[0])
                except Exception: sig = -80
            if ssid is not None and sig is not None:
                nets.append({"ssid": ssid, "signal": sig, "connected": False})
                ssid = sig = None
        try:
            cur = subprocess.check_output(["iwgetid", "-r"], text=True).strip()
            for n in nets:
                if n["ssid"] == cur: n["connected"] = True
        except Exception: pass
        return sorted(nets, key=lambda x: -x["signal"]), f"{len(nets)} networks found"
    except Exception as e:
        return [], f"Scan failed: {e}"

def connect_wifi(ssid, password):
    try:
        cmd = f'wpa_passphrase "{ssid}" "{password}" | sudo tee -a /etc/wpa_supplicant/wpa_supplicant.conf'
        subprocess.run(cmd, shell=True, check=True)
        subprocess.run(["sudo", "wpa_cli", "-i", "wlan0", "reconfigure"], check=True)
        return f"Connected to {ssid}"
    except Exception as e:
        return f"Failed: {e}"

# ── Display / Sound helpers ────────────────────────────────────────────────
BRIGHTNESS_PATH = Path("/sys/class/backlight/rpi_backlight/brightness")
MAX_BRIGHT_PATH = Path("/sys/class/backlight/rpi_backlight/max_brightness")

def get_brightness(): 
    try: return int(BRIGHTNESS_PATH.read_text().strip())
    except: return 128
def get_max_brightness():
    try: return int(MAX_BRIGHT_PATH.read_text().strip())
    except: return 255
def set_brightness(v):
    try: subprocess.run(["sudo", "tee", str(BRIGHTNESS_PATH)], input=str(v), text=True, capture_output=True)
    except: pass
def get_volume():
    try:
        out = subprocess.check_output(["amixer", "get", "Master"], text=True)
        return int(out.split("[")[1].split("%")[0])
    except: return 80
def set_volume(v):
    try: subprocess.run(["amixer", "set", "Master", f"{v}%"], capture_output=True)
    except: pass

# ── System info ────────────────────────────────────────────────────────────
def sys_info():
    rows = []
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("Model"): rows.append(("Board", line.split(":")[1].strip())); break
    except: rows.append(("Board", "Unknown"))
    try:
        for line in open("/proc/meminfo"):
            if line.startswith("MemTotal"): rows.append(("RAM", f"{int(line.split()[1])//1024} MB")); break
    except: pass
    try:
        up = float(Path("/proc/uptime").read_text().split()[0])
        rows.append(("Uptime", f"{int(up//3600)}h {int((up%3600)//60)}m"))
    except: pass
    try:
        df = subprocess.check_output(["df", "-h", "/"], text=True).splitlines()[1].split()
        rows.append(("Disk", f"{df[2]} / {df[1]}"))
    except: pass
    try:
        for line in open("/etc/os-release"):
            if line.startswith("PRETTY_NAME"): rows.append(("OS", line.split('"')[1])); break
    except: pass
    rows.append(("Python", platform.python_version()))
    return rows

# ── Main entry point ──────────────────────────────────────────────────────
def run(screen, clock):
    """Called by the launcher. Runs settings UI on the shared screen."""
    font_lg = pygame.font.SysFont("monospace", 14, bold=True)
    font_sm = pygame.font.SysFont("monospace", 11)
    font_xs = pygame.font.SysFont("monospace", 10)
    pygame.key.set_repeat(400, 60)

    tab        = 0
    all_themes = th.list_themes()
    theme_cur  = next((i for i, (tid, _) in enumerate(all_themes)
                       if tid == th.get_active_id()), 0)
    preview_pal = all_themes[theme_cur][1]

    wifi_networks  = []
    wifi_cur       = 0
    wifi_status    = "Press Z to scan"
    wifi_input_mode = False
    wifi_input_ssid = ""
    wifi_input_pass = ""
    wifi_input_field = 0

    display_brightness = get_brightness()
    display_max        = get_max_brightness()
    sound_volume       = get_volume()
    system_rows        = sys_info()

    def P(): return preview_pal if tab == 0 else th.get()

    def draw_header():
        p = P()
        pygame.draw.rect(screen, p["bar"], (0, 0, SCREEN_W, HEADER))
        pygame.draw.line(screen, p["border"], (0, HEADER), (SCREEN_W, HEADER))
        screen.blit(font_lg.render("Settings", True, p["accent"]),
                    (PAD, (HEADER - font_lg.size("Settings")[1]) // 2))
        h = font_sm.render("\u2190\u2192 tabs  Esc back", True, p["dim"])
        screen.blit(h, (SCREEN_W - h.get_width() - PAD,
                        (HEADER - h.get_height()) // 2))

    def draw_tabs():
        p = P(); tw = SCREEN_W // len(TABS)
        for i, name in enumerate(TABS):
            x = i * tw
            pygame.draw.rect(screen, p["bar"], (x, HEADER, tw, TAB_H))
            if i == tab:
                pygame.draw.rect(screen, p["accent"], (x, HEADER + TAB_H - 2, tw, 2))
            s = font_xs.render(name, True, p["accent"] if i == tab else p["locked"])
            screen.blit(s, (x + tw//2 - s.get_width()//2,
                            HEADER + (TAB_H - s.get_height())//2))
        pygame.draw.line(screen, p["border"],
                         (0, HEADER + TAB_H), (SCREEN_W, HEADER + TAB_H))

    def draw_row(label, value, y, sel=False):
        p = P()
        bg = tuple(min(255, c+8) for c in p["card"]) if sel else p["card"]
        pygame.draw.rect(screen, bg, (PAD, y, SCREEN_W-PAD*2, 36), border_radius=4)
        if sel: pygame.draw.rect(screen, p["accent"],
                                  (PAD, y, SCREEN_W-PAD*2, 36), 1, border_radius=4)
        screen.blit(font_sm.render(label, True, p["dim"]), (PAD+8, y+4))
        v = font_lg.render(str(value), True, p["accent"] if sel else p["white"])
        screen.blit(v, (SCREEN_W - v.get_width() - PAD*2, y+4))

    def draw_slider(label, val, max_val, y):
        p = P()
        draw_row(label, f"{val}/{max_val}", y, True)
        bx = PAD+8; bw = SCREEN_W-PAD*2-16
        fill = int(bw * val / max(max_val, 1))
        pygame.draw.rect(screen, p["locked"], (bx, y+26, bw, 6), border_radius=3)
        pygame.draw.rect(screen, p["accent"],  (bx, y+26, fill, 6), border_radius=3)

    def draw_hint(*pairs):
        p = P()
        pygame.draw.line(screen, p["border"],
                         (0, SCREEN_H-34), (SCREEN_W, SCREEN_H-34))
        hx = 6
        for key, act in pairs:
            ki = font_sm.render(key, True, p["black"]); kw = ki.get_width()+8
            pygame.draw.rect(screen, p["accent"], (hx, SCREEN_H-26, kw, 18))
            screen.blit(ki, (hx+4, SCREEN_H-24)); hx += kw+4
            ai = font_sm.render(act, True, p["dim"])
            screen.blit(ai, (hx, SCREEN_H-24)); hx += ai.get_width()+12

    running = True
    while running:
        clock.tick(FPS)
        p = P()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if not wifi_input_mode:
                    if event.key == pygame.K_RIGHT:  tab = (tab+1) % len(TABS)
                    elif event.key == pygame.K_LEFT: tab = (tab-1) % len(TABS)
                    elif event.key in (pygame.K_ESCAPE, pygame.K_b): running = False

                if tab == 0:   # Theme
                    if event.key in (pygame.K_UP, pygame.K_w):
                        nonlocal theme_cur, preview_pal
                        theme_cur = (theme_cur-1) % len(all_themes)
                        preview_pal = all_themes[theme_cur][1]
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        theme_cur = (theme_cur+1) % len(all_themes)
                        preview_pal = all_themes[theme_cur][1]
                    elif event.key in (pygame.K_RETURN, pygame.K_z):
                        th.set_theme(all_themes[theme_cur][0])

                elif tab == 1:  # Wi-Fi
                    if wifi_input_mode:
                        if event.key == pygame.K_TAB:   wifi_input_field ^= 1
                        elif event.key == pygame.K_RETURN:
                            nonlocal wifi_status
                            wifi_status = connect_wifi(wifi_input_ssid, wifi_input_pass)
                            wifi_input_mode = False
                        elif event.key == pygame.K_ESCAPE: wifi_input_mode = False
                        elif event.key == pygame.K_BACKSPACE:
                            if wifi_input_field == 0: wifi_input_ssid = wifi_input_ssid[:-1]
                            else:                      wifi_input_pass = wifi_input_pass[:-1]
                        elif event.unicode and event.unicode.isprintable():
                            if wifi_input_field == 0 and len(wifi_input_ssid) < 32:
                                wifi_input_ssid += event.unicode
                            elif wifi_input_field == 1 and len(wifi_input_pass) < 64:
                                wifi_input_pass += event.unicode
                    else:
                        if event.key in (pygame.K_UP, pygame.K_w):
                            wifi_cur = max(0, wifi_cur-1)
                        elif event.key in (pygame.K_DOWN, pygame.K_s):
                            wifi_cur = min(len(wifi_networks)-1, wifi_cur+1)
                        elif event.key in (pygame.K_z, pygame.K_RETURN):
                            wifi_networks[:], wifi_status = scan_wifi()
                        elif event.key == pygame.K_RETURN and wifi_networks:
                            wifi_input_mode = True
                            wifi_input_ssid = wifi_networks[wifi_cur]["ssid"]
                            wifi_input_pass = ""
                            wifi_input_field = 1

                elif tab == 2:  # Display
                    step = max(1, display_max // 16)
                    if event.key in (pygame.K_UP, pygame.K_w):
                        nonlocal display_brightness
                        display_brightness = min(display_max, display_brightness+step)
                        set_brightness(display_brightness)
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        display_brightness = max(10, display_brightness-step)
                        set_brightness(display_brightness)

                elif tab == 3:  # Sound
                    if event.key in (pygame.K_UP, pygame.K_w):
                        nonlocal sound_volume
                        sound_volume = min(100, sound_volume+5)
                        set_volume(sound_volume)
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        sound_volume = max(0, sound_volume-5)
                        set_volume(sound_volume)

                elif tab == 4:  # System
                    if event.key == pygame.K_r:
                        subprocess.run(["sudo", "reboot"])
                    elif event.key == pygame.K_s:
                        subprocess.run(["sudo", "shutdown", "-h", "now"])

        screen.fill(p["bg"])
        draw_header()
        draw_tabs()

        if tab == 0:  # Theme
            for i, (tid, td) in enumerate(all_themes):
                y = CONTENT_Y + i * 52; sel = (i == theme_cur)
                bg = tuple(min(255,c+8) for c in preview_pal["card"]) if sel else preview_pal["card"]
                pygame.draw.rect(screen, bg, (PAD, y, SCREEN_W-PAD*2, 48), border_radius=4)
                if sel: pygame.draw.rect(screen, preview_pal["accent"],
                                          (PAD, y, SCREEN_W-PAD*2, 48), 1, border_radius=4)
                for si, col in enumerate([td["accent"],td["dim"],td["bar"]]):
                    pygame.draw.rect(screen, col, (PAD+10+si*20, y+8, 16, 16), border_radius=3)
                ns = font_lg.render(td["name"], True,
                                     preview_pal["accent"] if sel else preview_pal["white"])
                screen.blit(ns, (PAD+76, y+8))
                if tid == th.get_active_id():
                    b = font_xs.render("ACTIVE", True, preview_pal["black"])
                    bw = b.get_width()+8
                    pygame.draw.rect(screen, preview_pal["accent"],
                                     (SCREEN_W-PAD*2-bw, y+10, bw, 14), border_radius=3)
                    screen.blit(b, (SCREEN_W-PAD*2-bw+4, y+11))
            draw_hint(("\u2191\u2193","SELECT"),("Z","APPLY"),("Esc","BACK"))

        elif tab == 1:  # Wi-Fi
            y = CONTENT_Y
            screen.blit(font_sm.render(wifi_status, True, p["dim"]), (PAD, y)); y += 20
            if wifi_input_mode:
                ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
                ov.fill((0,0,0,160)); screen.blit(ov,(0,0))
                pygame.draw.rect(screen, p["card"], (60,140,SCREEN_W-120,140), border_radius=6)
                pygame.draw.rect(screen, p["accent"], (60,140,SCREEN_W-120,140), 1, border_radius=6)
                hdr = font_lg.render(f"Connect: {wifi_input_ssid or '?'}", True, p["accent"])
                screen.blit(hdr, (SCREEN_W//2 - hdr.get_width()//2, 150))
                for fi, (lbl, val) in enumerate([("SSID",wifi_input_ssid),("Pass",wifi_input_pass)]):
                    cy = 182+fi*36; sel = (wifi_input_field==fi)
                    pygame.draw.rect(screen, p["card"] if sel else p["bar"],
                                     (76,cy,SCREEN_W-152,28), border_radius=3)
                    if sel: pygame.draw.rect(screen, p["accent"],
                                             (76,cy,SCREEN_W-152,28), 1, border_radius=3)
                    ls = font_sm.render(lbl+":", True, p["dim"])
                    screen.blit(ls, (80, cy+7))
                    disp = ("*"*len(val) if lbl=="Pass" and val else val) + ("_" if sel else "")
                    screen.blit(font_lg.render(disp[:28], True, p["white"]),
                                (80+ls.get_width()+6, cy+5))
                draw_hint(("Tab","FIELD"),("Enter","CONNECT"),("Esc","CANCEL"))
            else:
                for i, net in enumerate(wifi_networks):
                    if y+40 > SCREEN_H-40: break
                    sel = (i==wifi_cur)
                    bg = tuple(min(255,c+8) for c in p["card"]) if sel else p["card"]
                    pygame.draw.rect(screen, bg, (PAD,y,SCREEN_W-PAD*2,36), border_radius=4)
                    if sel: pygame.draw.rect(screen, p["accent"],
                                             (PAD,y,SCREEN_W-PAD*2,36), 1, border_radius=4)
                    ss = font_lg.render(net["ssid"][:32], True,
                                        p["accent"] if net["connected"] else p["white"])
                    screen.blit(ss, (PAD+8, y+4))
                    sig = font_sm.render(f"{max(0,min(100,(net['signal']+90)*2))}%",
                                         True, p["dim"])
                    screen.blit(sig, (SCREEN_W-sig.get_width()-PAD*2, y+10))
                    y += 40
                draw_hint(("Z","SCAN"),("Enter","CONNECT"),("Esc","BACK"))

        elif tab == 2:  # Display
            draw_slider("Brightness", display_brightness, display_max, CONTENT_Y)
            try:
                info = subprocess.check_output(["fbset"],text=True,stderr=subprocess.DEVNULL)
                for line in info.splitlines():
                    if "mode" in line.lower() and '"' in line:
                        draw_row("Resolution", line.strip().strip('mode').strip().strip('"'),
                                 CONTENT_Y+46); break
            except: draw_row("Resolution", "640x480", CONTENT_Y+46)
            draw_hint(("\u2191\u2193","BRIGHTNESS"),("Esc","BACK"))

        elif tab == 3:  # Sound
            draw_slider("Volume", sound_volume, 100, CONTENT_Y)
            draw_hint(("\u2191\u2193","VOLUME"),("Esc","BACK"))

        elif tab == 4:  # System
            y = CONTENT_Y
            for label, value in system_rows:
                if y+38 > SCREEN_H-40: break
                draw_row(label, value, y); y += 40
            y += 8
            for i, (lbl, col) in enumerate([("Reboot",p["accent"]),("Shutdown",(220,60,60))]):
                bx = PAD + i*120
                pygame.draw.rect(screen, col, (bx, y, 110, 28), border_radius=4)
                bt = font_sm.render(lbl, True, p["black"])
                screen.blit(bt, (bx+55-bt.get_width()//2, y+6))
            draw_hint(("R","REBOOT"),("S","SHUTDOWN"),("Esc","BACK"))

        pygame.display.flip()

    pygame.key.set_repeat(0)  # restore launcher's key repeat settings