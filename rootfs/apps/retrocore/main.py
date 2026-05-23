#!/usr/bin/env python3
# rootfs/apps/retrocore/main.py  --  RetroCore v1.0
import os, sys, platform, subprocess, shutil
from pathlib import Path

IS_LINUX = platform.system() == "Linux"
if IS_LINUX:
    os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")
    os.environ.setdefault("SDL_AUDIODRIVER", "alsa")

import pygame

SCREEN_W, SCREEN_H = 640, 480
FPS    = 60
BG     = (10,  26,  16)
CARD   = (13,  32,  16)
CARD_S = (18,  45,  22)
ACCENT = (61, 204, 112)
DIM    = (90, 150, 105)
WHITE  = (180, 240, 195)
BORDER = (29, 100,  55)
RED    = (220,  60,  60)
GOLD   = (240, 200,  60)
BLUE   = ( 60, 140, 220)
BAR    = (  6,  13,   8)

# ext -> (system_name, badge_color, [emulator_candidates])
SYSTEMS = {
    ".nes": ("NES",  RED,    ["fceux",   "nestopia-ue",  "mednafen"]),
    ".gb":  ("GB",   ACCENT, ["mgba",    "gambatte"]),
    ".gbc": ("GBC",  ACCENT, ["mgba",    "gambatte"]),
    ".gba": ("GBA",  BLUE,   ["mgba"]),
    ".sfc": ("SNES", DIM,    ["snes9x",  "bsnes"]),
    ".smc": ("SNES", DIM,    ["snes9x",  "bsnes"]),
    ".md":  ("MD",   RED,    ["gens",    "blastem",  "mednafen"]),
    ".gen": ("MD",   RED,    ["gens",    "blastem"]),
    ".pce": ("PCE",  GOLD,   ["mednafen"]),
    ".z64": ("N64",  BLUE,   ["mupen64plus"]),
    ".n64": ("N64",  BLUE,   ["mupen64plus"]),
}

ROM_DIRS = [
    Path("/home/mintkit/roms"),
    Path("/media/cartridge/roms"),
] if IS_LINUX else [Path(__file__).parent / "roms"]

CATS = ["ALL","NES","GB","GBC","GBA","SNES","MD","N64","PCE"]

def find_emu(candidates):
    for c in candidates:
        if shutil.which(c): return c
    return None

def scan_roms():
    roms=[]
    for d in ROM_DIRS:
        if not d.exists(): continue
        for f in sorted(d.rglob("*")):
            if f.suffix.lower() in SYSTEMS:
                sys_name,col,emus=SYSTEMS[f.suffix.lower()]
                roms.append({"path":f,"name":f.stem,"system":sys_name,
                              "color":col,"emulator":find_emu(emus),"emus":emus})
    return roms

class RetroCore:
    def __init__(self,screen,fonts):
        self.screen=screen; self.fonts=fonts
        self.roms=scan_roms(); self.cur=0; self.cat=0
        self.detail=None; self.msg=""; self.msg_t=0

    def filtered(self):
        c=CATS[self.cat%len(CATS)]
        return self.roms if c=="ALL" else [r for r in self.roms if r["system"]==c]

    def launch(self,rom):
        if not rom["emulator"]:
            self.msg=f"No emulator. Install: {', '.join(rom['emus'])}"; self.msg_t=FPS*4; return
        try:
            subprocess.Popen([rom["emulator"],str(rom["path"])])
            self.msg=f"Launching with {rom['emulator']}..."; self.msg_t=FPS*3
        except Exception as e:
            self.msg=f"Error: {e}"; self.msg_t=FPS*4

    def handle(self,ev):
        if self.msg_t>0: self.msg_t-=1
        if ev.type!=pygame.KEYDOWN: return None,None
        if self.detail:
            if ev.key in(pygame.K_RETURN,pygame.K_z,pygame.K_SPACE):
                self.launch(self.detail); self.detail=None
            elif ev.key in(pygame.K_ESCAPE,pygame.K_x): self.detail=None
            return None,None
        roms=self.filtered()
        if ev.key in(pygame.K_DOWN,pygame.K_s):   self.cur=(self.cur+1)%max(1,len(roms))
        elif ev.key in(pygame.K_UP,pygame.K_w):   self.cur=(self.cur-1)%max(1,len(roms))
        elif ev.key in(pygame.K_LEFT,pygame.K_a):  self.cat=(self.cat-1)%len(CATS); self.cur=0
        elif ev.key in(pygame.K_RIGHT,pygame.K_d): self.cat=(self.cat+1)%len(CATS); self.cur=0
        elif ev.key in(pygame.K_RETURN,pygame.K_z,pygame.K_SPACE):
            if roms: self.detail=roms[self.cur]
        elif ev.key in(pygame.K_ESCAPE,pygame.K_x): return"back",None
        return None,None

    def draw(self):
        s=self.screen; s.fill(BG)
        pygame.draw.rect(s,BAR,(0,0,SCREEN_W,48))
        pygame.draw.line(s,BORDER,(0,48),(SCREEN_W,48),1)
        ti=self.fonts["title"].render("RETROCORE",True,ACCENT)
        s.blit(ti,(SCREEN_W//2-ti.get_width()//2,12))
        ri=self.fonts["xs"].render(f"{len(self.roms)} ROMs",True,DIM)
        s.blit(ri,(SCREEN_W-ri.get_width()-8,16))
        tw=SCREEN_W//len(CATS)
        for i,cat in enumerate(CATS):
            sel=(i==self.cat%len(CATS))
            pygame.draw.rect(s,CARD_S if sel else CARD,(i*tw,48,tw-1,20))
            if sel: pygame.draw.rect(s,ACCENT,(i*tw,48,tw-1,20),1)
            ti2=self.fonts["xs"].render(cat,True,ACCENT if sel else DIM)
            s.blit(ti2,(i*tw+tw//2-ti2.get_width()//2,52))
        if self.detail: self._detail(s)
        else: self._list(s)
        if self.msg_t>0:
            mi=self.fonts["xs"].render(self.msg,True,ACCENT)
            s.blit(mi,(SCREEN_W//2-mi.get_width()//2,SCREEN_H-58))
        pygame.draw.line(s,BORDER,(0,SCREEN_H-34),(SCREEN_W,SCREEN_H-34),1)
        hx=6
        for k,a in[("Z","SELECT"),("←/→","CATEGORY"),("X","BACK")]:
            ki=self.fonts["xs"].render(k,True,(5,10,8)); kw=ki.get_width()+8
            pygame.draw.rect(s,ACCENT,(hx,SCREEN_H-26,kw,18)); s.blit(ki,(hx+4,SCREEN_H-24)); hx+=kw+4
            ai=self.fonts["xs"].render(a,True,DIM); s.blit(ai,(hx,SCREEN_H-24)); hx+=ai.get_width()+16

    def _list(self,s):
        roms=self.filtered(); y0=72
        if not roms:
            ei=self.fonts["menu"].render("No ROMs found",True,DIM)
            s.blit(ei,(SCREEN_W//2-ei.get_width()//2,SCREEN_H//2-20))
            di=self.fonts["sm"].render(str(ROM_DIRS[0]),True,DIM)
            s.blit(di,(SCREEN_W//2-di.get_width()//2,SCREEN_H//2+14)); return
        ih=min(44,(SCREEN_H-y0-40)//len(roms))
        for i,rom in enumerate(roms):
            y=y0+i*ih
            if y+ih>SCREEN_H-40: break
            sel=(i==self.cur)
            pygame.draw.rect(s,CARD_S if sel else CARD,(4,y,SCREEN_W-8,ih-2))
            if sel: pygame.draw.rect(s,ACCENT,(4,y,SCREEN_W-8,ih-2),1)
            bi=self.fonts["xs"].render(rom["system"],True,(5,10,8)); bw=bi.get_width()+8
            pygame.draw.rect(s,rom["color"],(10,y+ih//2-8,bw,16)); s.blit(bi,(14,y+ih//2-6))
            s.blit(self.fonts["sm"].render(rom["name"][:44],True,WHITE),(16+bw,y+6))
            ec=ACCENT if rom["emulator"] else RED
            ei=self.fonts["xs"].render(rom["emulator"] or "no emu",True,ec)
            s.blit(ei,(SCREEN_W-ei.get_width()-10,y+ih//2-ei.get_height()//2))

    def _detail(self,s):
        rom=self.detail; y=80
        s.blit(self.fonts["big"].render(rom["system"],True,rom["color"]),(16,y))
        s.blit(self.fonts["menu"].render(rom["name"][:40],True,WHITE),(16,y+46))
        s.blit(self.fonts["xs"].render(str(rom["path"]),True,DIM),(16,y+68))
        pygame.draw.line(s,BORDER,(0,y+88),(SCREEN_W,y+88),1)
        ev=rom["emulator"] or f"NOT FOUND (need: {', '.join(rom['emus'])})"
        ec=ACCENT if rom["emulator"] else RED
        s.blit(self.fonts["sm"].render("Emulator:",True,DIM),(16,y+98))
        s.blit(self.fonts["sm"].render(ev,True,ec),(110,y+98))
        bt="Launch" if rom["emulator"] else "Install emulator first"
        bc=ACCENT if rom["emulator"] else RED
        bi=self.fonts["menu"].render(bt,True,bc); bw=bi.get_width()+24
        bx=SCREEN_W//2-bw//2; by2=SCREEN_H-100
        pygame.draw.rect(s,CARD_S,(bx,by2,bw,34)); pygame.draw.rect(s,bc,(bx,by2,bw,34),1)
        s.blit(bi,(bx+12,by2+7))

def main():
    pygame.init(); screen=pygame.display.set_mode((SCREEN_W,SCREEN_H))
    pygame.display.set_caption("RetroCore"); clock=pygame.time.Clock()
    fonts={"big":pygame.font.SysFont("Courier New",36,bold=True),
           "title":pygame.font.SysFont("Courier New",20,bold=True),
           "menu":pygame.font.SysFont("Courier New",19,bold=True),
           "sm":pygame.font.SysFont("Courier New",14),
           "xs":pygame.font.SysFont("Courier New",12)}
    app=RetroCore(screen,fonts)
    while True:
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: pygame.quit(); sys.exit()
            act,_=app.handle(ev)
            if act=="back": pygame.quit(); sys.exit()
        app.draw(); pygame.display.flip(); clock.tick(FPS)

if __name__=="__main__": main()