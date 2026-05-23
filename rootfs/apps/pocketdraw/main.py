#!/usr/bin/env python3
# rootfs/apps/pocketdraw/main.py  --  PocketDraw v1.0
import os, sys, platform, json
from pathlib import Path

IS_LINUX = platform.system() == "Linux"
if IS_LINUX:
    os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")
    os.environ.setdefault("SDL_AUDIODRIVER", "alsa")

import pygame

SCREEN_W, SCREEN_H = 640, 480
FPS     = 60
CANVAS_W, CANVAS_H = 32, 24
ZOOM    = 16
PAD_X   = (SCREEN_W - CANVAS_W * ZOOM) // 2
PAD_Y   = 44

BG     = (10,  26,  16)
ACCENT = (61, 204, 112)
DIM    = (90, 150, 105)
WHITE  = (180, 240, 195)
BORDER = (29, 100,  55)
BLACK  = (5,   10,   8)
BAR    = (6,   13,   8)

PALETTE = [
    (  5,  10,   8),(180, 240, 195),( 61, 204, 112),(220,  60,  60),
    ( 60, 140, 220),(240, 200,  60),(139, 115,  85),(101,  67,  33),
    (128, 128, 128),(200, 100, 200),(255, 165,   0),(  0, 200, 200),
    ( 34, 139,  34),(210, 180, 140),(178,  34,  34),(255, 255, 255),
]

SAVE_DIR = Path(os.environ.get("HOME", ".")) / ".mintkit" / "drawings"
TOOL_PENCIL, TOOL_FILL, TOOL_ERASER, TOOL_LINE = 0, 1, 2, 3
TOOL_NAMES = ["PENCIL", "FILL", "ERASER", "LINE"]

def empty_canvas(): return [[(255,255,255)]*CANVAS_H for _ in range(CANVAS_W)]

def save_canvas(canvas, name="drawing"):
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    data = [[[c[0],c[1],c[2]] for c in row] for row in canvas]
    (SAVE_DIR / f"{name}.json").write_text(json.dumps(data))

def load_canvas(name="drawing"):
    f = SAVE_DIR / f"{name}.json"
    if f.exists():
        try: return [[tuple(c) for c in row] for row in json.loads(f.read_text())]
        except Exception: pass
    return empty_canvas()

def flood_fill(canvas, x, y, new_col, old_col=None):
    if old_col is None: old_col = canvas[x][y]
    if old_col == new_col: return
    stack = [(x, y)]
    while stack:
        cx, cy = stack.pop()
        if not (0<=cx<CANVAS_W and 0<=cy<CANVAS_H): continue
        if canvas[cx][cy] != old_col: continue
        canvas[cx][cy] = new_col
        stack += [(cx+1,cy),(cx-1,cy),(cx,cy+1),(cx,cy-1)]

class PocketDraw:
    def __init__(self, screen, fonts):
        self.screen=screen; self.fonts=fonts
        self.canvas=load_canvas(); self.undo_stack=[]
        self.color_idx=0; self.tool=TOOL_PENCIL
        self.cursor_x=CANVAS_W//2; self.cursor_y=CANVAS_H//2
        self.line_start=None; self.line_preview=[]
        self.msg=""; self.msg_t=0; self.show_palette=False

    @property
    def color(self): return PALETTE[self.color_idx]

    def push_undo(self):
        snap=[row[:] for row in self.canvas]; self.undo_stack.append(snap)
        if len(self.undo_stack)>30: self.undo_stack.pop(0)

    def line_pixels(self,x0,y0,x1,y1):
        pts=[]; dx,dy=abs(x1-x0),abs(y1-y0)
        sx=1 if x0<x1 else -1; sy=1 if y0<y1 else -1; err=dx-dy
        while True:
            pts.append((x0,y0))
            if x0==x1 and y0==y1: break
            e2=err*2
            if e2>-dy: err-=dy; x0+=sx
            if e2<dx:  err+=dx; y0+=sy
        return pts

    def apply_tool(self):
        x,y=self.cursor_x,self.cursor_y; self.push_undo()
        if self.tool==TOOL_PENCIL:  self.canvas[x][y]=self.color
        elif self.tool==TOOL_ERASER: self.canvas[x][y]=(255,255,255)
        elif self.tool==TOOL_FILL:  flood_fill(self.canvas,x,y,self.color)
        elif self.tool==TOOL_LINE:
            if self.line_start is None:
                self.line_start=(x,y); self.msg="Move to endpoint, Z to confirm"; self.msg_t=FPS*2
            else:
                for px,py in self.line_pixels(*self.line_start,x,y): self.canvas[px][py]=self.color
                self.line_start=None

    def handle(self,ev):
        if self.msg_t>0: self.msg_t-=1
        if ev.type!=pygame.KEYDOWN: return None,None
        if self.show_palette:
            if ev.key in(pygame.K_LEFT,pygame.K_a):   self.color_idx=(self.color_idx-1)%len(PALETTE)
            elif ev.key in(pygame.K_RIGHT,pygame.K_d): self.color_idx=(self.color_idx+1)%len(PALETTE)
            elif ev.key in(pygame.K_UP,pygame.K_w):   self.color_idx=(self.color_idx-8)%len(PALETTE)
            elif ev.key in(pygame.K_DOWN,pygame.K_s): self.color_idx=(self.color_idx+8)%len(PALETTE)
            elif ev.key in(pygame.K_RETURN,pygame.K_z,pygame.K_p,pygame.K_ESCAPE): self.show_palette=False
            return None,None
        if ev.key in(pygame.K_UP,pygame.K_w):     self.cursor_y=max(0,self.cursor_y-1)
        elif ev.key in(pygame.K_DOWN,pygame.K_s): self.cursor_y=min(CANVAS_H-1,self.cursor_y+1)
        elif ev.key in(pygame.K_LEFT,pygame.K_a): self.cursor_x=max(0,self.cursor_x-1)
        elif ev.key in(pygame.K_RIGHT,pygame.K_d):self.cursor_x=min(CANVAS_W-1,self.cursor_x+1)
        elif ev.key in(pygame.K_z,pygame.K_RETURN,pygame.K_SPACE): self.apply_tool()
        elif ev.key==pygame.K_p: self.show_palette=True
        elif ev.key==pygame.K_t:
            self.tool=(self.tool+1)%4; self.line_start=None
            self.msg=f"Tool: {TOOL_NAMES[self.tool]}"; self.msg_t=FPS*2
        elif ev.key==pygame.K_u:
            if self.undo_stack: self.canvas=self.undo_stack.pop(); self.msg="Undo"; self.msg_t=FPS
        elif ev.key==pygame.K_n:
            self.push_undo(); self.canvas=empty_canvas(); self.msg="New canvas"; self.msg_t=FPS*2
        elif ev.key==pygame.K_F5:
            save_canvas(self.canvas); self.msg="Saved!"; self.msg_t=FPS*2
        elif ev.key==pygame.K_F9:
            self.canvas=load_canvas(); self.msg="Loaded!"; self.msg_t=FPS*2
        elif ev.key==pygame.K_ESCAPE:
            save_canvas(self.canvas); return "back",None
        self.line_preview=self.line_pixels(*self.line_start,self.cursor_x,self.cursor_y) if(self.tool==TOOL_LINE and self.line_start) else []
        return None,None

    def draw(self):
        s=self.screen; s.fill(BG)
        for x in range(CANVAS_W):
            for y in range(CANVAS_H):
                px=PAD_X+x*ZOOM; py=PAD_Y+y*ZOOM
                pygame.draw.rect(s,self.canvas[x][y],(px,py,ZOOM,ZOOM))
        for x in range(CANVAS_W+1):
            lx=PAD_X+x*ZOOM; pygame.draw.line(s,BORDER,(lx,PAD_Y),(lx,PAD_Y+CANVAS_H*ZOOM),1)
        for y in range(CANVAS_H+1):
            ly=PAD_Y+y*ZOOM; pygame.draw.line(s,BORDER,(PAD_X,ly),(PAD_X+CANVAS_W*ZOOM,ly),1)
        for px,py in self.line_preview:
            rx=PAD_X+px*ZOOM; ry=PAD_Y+py*ZOOM
            surf=pygame.Surface((ZOOM,ZOOM),pygame.SRCALPHA); surf.fill((*self.color,140)); s.blit(surf,(rx,ry))
        cx=PAD_X+self.cursor_x*ZOOM; cy=PAD_Y+self.cursor_y*ZOOM
        pygame.draw.rect(s,ACCENT,(cx,cy,ZOOM,ZOOM),2)
        pygame.draw.rect(s,BAR,(0,0,SCREEN_W,40))
        pygame.draw.line(s,BORDER,(0,40),(SCREEN_W,40),1)
        s.blit(self.fonts["title"].render("POCKETDRAW",True,ACCENT),(8,10))
        tn=self.fonts["sm"].render(TOOL_NAMES[self.tool],True,DIM)
        s.blit(tn,(SCREEN_W//2-tn.get_width()//2,12))
        pygame.draw.rect(s,self.color,(SCREEN_W-40,8,24,24))
        pygame.draw.rect(s,ACCENT,(SCREEN_W-40,8,24,24),1)
        if self.show_palette:
            ov=pygame.Surface((SCREEN_W,SCREEN_H),pygame.SRCALPHA); ov.fill((0,0,0,180)); s.blit(ov,(0,0))
            cpr=8; sw=36; sh=36; sx0=SCREEN_W//2-cpr*sw//2
            sy0=SCREEN_H//2-(len(PALETTE)//cpr)*sh//2-20
            s.blit(self.fonts["menu"].render("SELECT COLOR",True,ACCENT),(SCREEN_W//2-80,sy0-30))
            for i,col in enumerate(PALETTE):
                rx=sx0+(i%cpr)*sw; ry=sy0+(i//cpr)*sh
                pygame.draw.rect(s,col,(rx,ry,sw-2,sh-2))
                if i==self.color_idx: pygame.draw.rect(s,ACCENT,(rx,ry,sw-2,sh-2),2)
        if self.msg_t>0:
            mi=self.fonts["sm"].render(self.msg,True,ACCENT)
            s.blit(mi,(SCREEN_W//2-mi.get_width()//2,14))
        hints=[("Z","DRAW"),("T","TOOL"),("P","COLOR"),("U","UNDO"),("N","NEW"),("F5","SAVE"),("F9","LOAD"),("Esc","EXIT")]
        hx=4; pygame.draw.rect(s,BAR,(0,SCREEN_H-20,SCREEN_W,20))
        pygame.draw.line(s,BORDER,(0,SCREEN_H-20),(SCREEN_W,SCREEN_H-20),1)
        for key,act in hints:
            ki=self.fonts["xs"].render(key,True,BLACK); kw=ki.get_width()+4
            pygame.draw.rect(s,ACCENT,(hx,SCREEN_H-17,kw,14)); s.blit(ki,(hx+2,SCREEN_H-16)); hx+=kw+2
            ai=self.fonts["xs"].render(act,True,DIM); s.blit(ai,(hx,SCREEN_H-16)); hx+=ai.get_width()+8

def main():
    pygame.init(); screen=pygame.display.set_mode((SCREEN_W,SCREEN_H))
    pygame.display.set_caption("PocketDraw"); clock=pygame.time.Clock()
    fonts={"big":pygame.font.SysFont("Courier New",36,bold=True),
           "title":pygame.font.SysFont("Courier New",20,bold=True),
           "menu":pygame.font.SysFont("Courier New",19,bold=True),
           "sm":pygame.font.SysFont("Courier New",13),
           "xs":pygame.font.SysFont("Courier New",10)}
    app=PocketDraw(screen,fonts)
    while True:
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: pygame.quit(); sys.exit()
            act,_=app.handle(ev)
            if act=="back": pygame.quit(); sys.exit()
        app.draw(); pygame.display.flip(); clock.tick(FPS)

if __name__=="__main__": main()