#!/usr/bin/env python3
# rootfs/apps/chiptune/main.py  --  ChipTune Player v1.0
import os, sys, platform, random
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
GOLD   = (240, 200,  60)
BAR    = (  6,  13,   8)

MEDIA_DIRS = [
    Path("/home/mintkit/Music"),
] if IS_LINUX else [Path(__file__).parent / "music"]
EXTS = {".mp3",".ogg",".wav",".flac",".xm",".mod",".it",".s3m"}

def scan_tracks():
    tracks=[]
    for d in MEDIA_DIRS:
        if d.exists():
            for f in sorted(d.rglob("*")):
                if f.suffix.lower() in EXTS: tracks.append(f)
    return tracks

class ChipTune:
    BARS = 32
    def __init__(self,screen,fonts):
        self.screen=screen; self.fonts=fonts
        pygame.mixer.init(frequency=44100,size=-16,channels=2,buffer=512)
        self.tracks=scan_tracks(); self.cur=0
        self.playing=False; self.paused=False
        self.shuffle=False; self.repeat=False
        self.vol=80; pygame.mixer.music.set_volume(0.8)
        self.track_start=0
        self.bars=[random.uniform(0.05,0.3) for _ in range(self.BARS)]
        self.btgt=[random.uniform(0.1,1.0) for _ in range(self.BARS)]

    def play(self,idx=None):
        if idx is not None: self.cur=max(0,min(idx,len(self.tracks)-1))
        if not self.tracks: return
        try:
            pygame.mixer.music.load(str(self.tracks[self.cur]))
            pygame.mixer.music.play()
            self.playing=True; self.paused=False
            self.track_start=pygame.time.get_ticks()
        except: self.playing=False

    def stop(self): pygame.mixer.music.stop(); self.playing=False; self.paused=False

    def toggle_pause(self):
        if self.playing and not self.paused: pygame.mixer.music.pause(); self.paused=True
        elif self.paused: pygame.mixer.music.unpause(); self.paused=False

    def next_track(self):
        if not self.tracks: return
        self.cur=(random.randint(0,len(self.tracks)-1) if self.shuffle
                  else (self.cur+1)%len(self.tracks))
        self.play()

    def prev_track(self):
        if not self.tracks: return
        self.cur=(self.cur-1)%len(self.tracks); self.play()

    def update(self):
        for i in range(self.BARS):
            if self.playing and not self.paused:
                if random.random()<0.12: self.btgt[i]=random.uniform(0.1,1.0)
                self.bars[i]+=(self.btgt[i]-self.bars[i])*0.09
            else: self.bars[i]*=0.92
        if self.playing and not self.paused and not pygame.mixer.music.get_busy():
            self.next_track() if not self.repeat else self.play()

    def handle(self,ev):
        if ev.type!=pygame.KEYDOWN: return None,None
        if ev.key in(pygame.K_DOWN,pygame.K_s):   self.cur=(self.cur+1)%max(1,len(self.tracks))
        elif ev.key in(pygame.K_UP,pygame.K_w):   self.cur=(self.cur-1)%max(1,len(self.tracks))
        elif ev.key in(pygame.K_RETURN,pygame.K_z,pygame.K_SPACE):
            if self.playing or self.paused: self.toggle_pause()
            else: self.play(self.cur)
        elif ev.key in(pygame.K_RIGHT,pygame.K_d): self.next_track()
        elif ev.key in(pygame.K_LEFT,pygame.K_a):  self.prev_track()
        elif ev.key==pygame.K_r: self.repeat=not self.repeat
        elif ev.key==pygame.K_f: self.shuffle=not self.shuffle
        elif ev.key==pygame.K_PERIOD:
            self.vol=min(100,self.vol+10); pygame.mixer.music.set_volume(self.vol/100)
        elif ev.key==pygame.K_COMMA:
            self.vol=max(0,self.vol-10); pygame.mixer.music.set_volume(self.vol/100)
        elif ev.key==pygame.K_x: self.stop()
        elif ev.key==pygame.K_ESCAPE: self.stop(); return"back",None
        return None,None

    def draw(self):
        self.update(); s=self.screen; s.fill(BG)
        pygame.draw.rect(s,BAR,(0,0,SCREEN_W,48))
        pygame.draw.line(s,BORDER,(0,48),(SCREEN_W,48),1)
        ti=self.fonts["title"].render("CHIPTUNE PLAYER",True,ACCENT)
        s.blit(ti,(SCREEN_W//2-ti.get_width()//2,12))
        # Now playing strip
        NP_Y=52
        pygame.draw.rect(s,CARD,(0,NP_Y,SCREEN_W,64))
        pygame.draw.line(s,BORDER,(0,NP_Y+64),(SCREEN_W,NP_Y+64),1)
        if self.tracks:
            t=self.tracks[self.cur]
            icon="⏸" if self.paused else("▶" if self.playing else "■")
            s.blit(self.fonts["menu"].render(f"{icon}  {t.stem[:38]}",True,ACCENT),(12,NP_Y+6))
            s.blit(self.fonts["xs"].render(t.suffix[1:].upper(),True,GOLD),(12,NP_Y+32))
            if self.playing or self.paused:
                el=(pygame.time.get_ticks()-self.track_start)/1000
                bf=int((el%180)/180*(SCREEN_W-40))
                pygame.draw.rect(s,BORDER,(20,NP_Y+52,SCREEN_W-40,6))
                pygame.draw.rect(s,ACCENT,(20,NP_Y+52,bf,6))
            fx=SCREEN_W-8
            for lbl,col in reversed([("SHUFFLE",ACCENT) if self.shuffle else None,
                                      ("REPEAT",GOLD) if self.repeat else None]):
                if lbl is None: continue
                fi=self.fonts["xs"].render(lbl,True,col); fx-=fi.get_width()+4; s.blit(fi,(fx,NP_Y+8))
            vi=self.fonts["xs"].render(f"VOL {self.vol}%",True,DIM)
            s.blit(vi,(SCREEN_W-vi.get_width()-8,NP_Y+30))
        else:
            ei=self.fonts["menu"].render("No tracks found",True,DIM)
            s.blit(ei,(SCREEN_W//2-ei.get_width()//2,NP_Y+20))
        # Visualizer
        VZ_Y=NP_Y+68; VZ_H=80
        bw=SCREEN_W//self.BARS
        for i,bar in enumerate(self.bars):
            h=int(bar*VZ_H); bx=i*bw
            g=int(bar*255)
            pygame.draw.rect(s,(g//4,min(255,g),g//2),(bx+1,VZ_Y+VZ_H-h,bw-2,h))
        pygame.draw.line(s,BORDER,(0,VZ_Y+VZ_H),(SCREEN_W,VZ_Y+VZ_H),1)
        # Track list
        LY=VZ_Y+VZ_H+4; LH=SCREEN_H-LY-40
        ih=min(38,LH//max(1,len(self.tracks)))
        for i,track in enumerate(self.tracks):
            y=LY+i*ih
            if y+ih>SCREEN_H-40: break
            sel=(i==self.cur)
            pygame.draw.rect(s,CARD_S if sel else BG,(4,y,SCREEN_W-8,ih-1))
            if sel: pygame.draw.rect(s,ACCENT,(4,y,SCREEN_W-8,ih-1),1)
            ic=self.fonts["xs"].render("♪" if(sel and self.playing) else "♩",True,ACCENT if sel else BORDER)
            s.blit(ic,(10,y+(ih-ic.get_height())//2))
            ni=self.fonts["sm"].render(track.stem[:46],True,WHITE if sel else DIM)
            s.blit(ni,(28,y+(ih-ni.get_height())//2))
            ei=self.fonts["xs"].render(track.suffix[1:].upper(),True,GOLD)
            s.blit(ei,(SCREEN_W-ei.get_width()-8,y+(ih-ei.get_height())//2))
        pygame.draw.line(s,BORDER,(0,SCREEN_H-34),(SCREEN_W,SCREEN_H-34),1)
        hx=6
        for k,a in[("Z","PLAY"),("←/→","PREV/NEXT"),("R","REPEAT"),("F","SHUFFLE"),("X","STOP"),("Esc","EXIT")]:
            ki=self.fonts["xs"].render(k,True,(5,10,8)); kw=ki.get_width()+6
            pygame.draw.rect(s,ACCENT,(hx,SCREEN_H-26,kw,18)); s.blit(ki,(hx+3,SCREEN_H-24)); hx+=kw+3
            ai=self.fonts["xs"].render(a,True,DIM); s.blit(ai,(hx,SCREEN_H-24)); hx+=ai.get_width()+12

def main():
    pygame.init(); screen=pygame.display.set_mode((SCREEN_W,SCREEN_H))
    pygame.display.set_caption("ChipTune Player"); clock=pygame.time.Clock()
    fonts={"big":pygame.font.SysFont("Courier New",36,bold=True),
           "title":pygame.font.SysFont("Courier New",20,bold=True),
           "menu":pygame.font.SysFont("Courier New",19,bold=True),
           "sm":pygame.font.SysFont("Courier New",14),
           "xs":pygame.font.SysFont("Courier New",12)}
    app=ChipTune(screen,fonts)
    while True:
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: pygame.quit(); sys.exit()
            act,_=app.handle(ev)
            if act=="back": pygame.quit(); sys.exit()
        app.draw(); pygame.display.flip(); clock.tick(FPS)

if __name__=="__main__": main()