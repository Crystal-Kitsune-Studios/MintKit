#!/usr/bin/env python3
# rootfs/apps/mintnotes/main.py  --  MintNotes v1.0
import os, sys, platform
from pathlib import Path
from datetime import datetime

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

NOTES_DIR=(Path("/home/mintkit/.mintkit/notes") if IS_LINUX
           else Path(__file__).parent/"notes")
NOTES_DIR.mkdir(parents=True, exist_ok=True)

def list_notes():
    return sorted(NOTES_DIR.glob("*.txt"), key=lambda f: f.stat().st_mtime, reverse=True)

class MintNotes:
    def __init__(self,screen,fonts):
        self.screen=screen; self.fonts=fonts
        self.mode="list"; self.notes=list_notes(); self.cur=0
        self.lines=[]; self.cur_file=None; self.dirty=False
        self.cursor_line=0; self.cursor_col=0; self.scroll=0
        self.new_name=""; self.msg=""; self.msg_t=0; self.blink=0
        self.LINE_H=17; self.EDIT_Y=48
        self.EDIT_H=SCREEN_H-48-44; self.VIS=self.EDIT_H//17

    def open_note(self,path):
        try: text=path.read_text(encoding="utf-8")
        except: text=""
        self.lines=text.split("\n"); self.cur_file=path
        self.dirty=False; self.cursor_line=0; self.cursor_col=0; self.scroll=0
        self.mode="edit"

    def save_note(self):
        if not self.cur_file: return
        try:
            self.cur_file.write_text("\n".join(self.lines),encoding="utf-8")
            self.dirty=False; self.msg=f"Saved: {self.cur_file.name}"; self.msg_t=FPS*2
        except Exception as e:
            self.msg=f"Error: {e}"; self.msg_t=FPS*3

    def delete_note(self):
        if self.cur<len(self.notes):
            p=self.notes[self.cur]
            try:
                p.unlink(); self.notes=list_notes()
                self.cur=max(0,self.cur-1)
                self.msg=f"Deleted {p.name}"; self.msg_t=FPS*2
            except Exception as e: self.msg=str(e); self.msg_t=FPS*3

    def clamp(self):
        self.cursor_line=max(0,min(self.cursor_line,len(self.lines)-1))
        self.cursor_col=max(0,min(self.cursor_col,len(self.lines[self.cursor_line])))
        if self.cursor_line<self.scroll: self.scroll=self.cursor_line
        elif self.cursor_line>=self.scroll+self.VIS: self.scroll=self.cursor_line-self.VIS+1

    def handle(self,ev):
        if self.msg_t>0: self.msg_t-=1
        if ev.type!=pygame.KEYDOWN: return None,None
        if self.mode=="new_name":
            if ev.key==pygame.K_RETURN:
                name=self.new_name.strip()
                if not name.endswith(".txt"): name+=".txt"
                p=NOTES_DIR/name; p.write_text("",encoding="utf-8")
                self.notes=list_notes(); self.open_note(p)
            elif ev.key==pygame.K_ESCAPE: self.mode="list"
            elif ev.key==pygame.K_BACKSPACE: self.new_name=self.new_name[:-1]
            elif ev.unicode.isprintable() and len(self.new_name)<40: self.new_name+=ev.unicode
            return None,None
        if self.mode=="list":
            if ev.key in(pygame.K_DOWN,pygame.K_s):   self.cur=(self.cur+1)%max(1,len(self.notes))
            elif ev.key in(pygame.K_UP,pygame.K_w):   self.cur=(self.cur-1)%max(1,len(self.notes))
            elif ev.key in(pygame.K_RETURN,pygame.K_z):
                if self.notes: self.open_note(self.notes[self.cur])
            elif ev.key==pygame.K_n:
                self.new_name=datetime.now().strftime("%Y%m%d-%H%M"); self.mode="new_name"
            elif ev.key==pygame.K_DELETE: self.delete_note()
            elif ev.key in(pygame.K_ESCAPE,pygame.K_x): return"back",None
            return None,None
        # edit mode
        if ev.key==pygame.K_ESCAPE:
            if self.dirty: self.save_note()
            self.mode="list"; self.notes=list_notes(); return None,None
        mods=pygame.key.get_mods()
        if ev.key==pygame.K_s and(mods&pygame.KMOD_CTRL): self.save_note(); return None,None
        ln=self.lines[self.cursor_line]
        if ev.key==pygame.K_RETURN:
            rest=ln[self.cursor_col:]; self.lines[self.cursor_line]=ln[:self.cursor_col]
            self.cursor_line+=1; self.lines.insert(self.cursor_line,rest); self.cursor_col=0; self.dirty=True
        elif ev.key==pygame.K_BACKSPACE:
            if self.cursor_col>0:
                self.lines[self.cursor_line]=ln[:self.cursor_col-1]+ln[self.cursor_col:]; self.cursor_col-=1
            elif self.cursor_line>0:
                prev=self.lines[self.cursor_line-1]; curr=self.lines.pop(self.cursor_line)
                self.cursor_line-=1; self.cursor_col=len(prev); self.lines[self.cursor_line]=prev+curr
            self.dirty=True
        elif ev.key==pygame.K_DELETE:
            if self.cursor_col<len(ln): self.lines[self.cursor_line]=ln[:self.cursor_col]+ln[self.cursor_col+1:]
            elif self.cursor_line<len(self.lines)-1:
                nxt=self.lines.pop(self.cursor_line+1); self.lines[self.cursor_line]=ln+nxt
            self.dirty=True
        elif ev.key==pygame.K_LEFT:
            if self.cursor_col>0: self.cursor_col-=1
            elif self.cursor_line>0: self.cursor_line-=1; self.cursor_col=len(self.lines[self.cursor_line])
        elif ev.key==pygame.K_RIGHT:
            if self.cursor_col<len(ln): self.cursor_col+=1
            elif self.cursor_line<len(self.lines)-1: self.cursor_line+=1; self.cursor_col=0
        elif ev.key==pygame.K_UP:
            if self.cursor_line>0: self.cursor_line-=1
        elif ev.key==pygame.K_DOWN:
            if self.cursor_line<len(self.lines)-1: self.cursor_line+=1
        elif ev.key==pygame.K_HOME: self.cursor_col=0
        elif ev.key==pygame.K_END:  self.cursor_col=len(self.lines[self.cursor_line])
        elif ev.unicode and ev.unicode.isprintable():
            self.lines[self.cursor_line]=ln[:self.cursor_col]+ev.unicode+ln[self.cursor_col:]
            self.cursor_col+=len(ev.unicode); self.dirty=True
        self.clamp(); return None,None

    def draw(self):
        self.blink=(self.blink+1)%60; s=self.screen; s.fill(BG)
        if self.mode=="new_name": self._draw_new_name(s); return
        pygame.draw.rect(s,BAR,(0,0,SCREEN_W,48))
        pygame.draw.line(s,BORDER,(0,48),(SCREEN_W,48),1)
        if self.mode=="list":
            ti=self.fonts["title"].render("MINTNOTES",True,ACCENT)
            s.blit(ti,(SCREEN_W//2-ti.get_width()//2,12))
            ni=self.fonts["xs"].render(f"{len(self.notes)} notes",True,DIM)
            s.blit(ni,(SCREEN_W-ni.get_width()-8,16))
            self._draw_list(s)
        elif self.mode=="edit" and self.cur_file:
            di="●" if self.dirty else ""
            fi=self.fonts["sm"].render(f"{di} {self.cur_file.name}",True,GOLD if self.dirty else ACCENT)
            s.blit(fi,(8,14))
            ll=self.fonts["xs"].render(f"L{self.cursor_line+1}:C{self.cursor_col+1}",True,DIM)
            s.blit(ll,(SCREEN_W-ll.get_width()-8,16))
            self._draw_editor(s)
        if self.msg_t>0:
            mi=self.fonts["xs"].render(self.msg,True,ACCENT)
            s.blit(mi,(SCREEN_W//2-mi.get_width()//2,SCREEN_H-50))

    def _draw_list(self,s):
        y0=52
        if not self.notes:
            ei=self.fonts["menu"].render("No notes yet",True,DIM)
            s.blit(ei,(SCREEN_W//2-ei.get_width()//2,SCREEN_H//2-20))
            hi=self.fonts["sm"].render("Press N to create a new note",True,DIM)
            s.blit(hi,(SCREEN_W//2-hi.get_width()//2,SCREEN_H//2+14))
        else:
            ih=min(50,(SCREEN_H-y0-40)//len(self.notes))
            for i,note in enumerate(self.notes):
                y=y0+i*ih; sel=(i==self.cur)
                pygame.draw.rect(s,CARD_S if sel else CARD,(4,y,SCREEN_W-8,ih-2))
                if sel: pygame.draw.rect(s,ACCENT,(4,y,SCREEN_W-8,ih-2),1)
                ni=self.fonts["menu"].render(note.stem[:40],True,ACCENT if sel else WHITE)
                s.blit(ni,(16,y+6))
                try: preview=note.read_text(encoding="utf-8").split("\n")[0][:50]
                except: preview=""
                if preview:
                    pi=self.fonts["xs"].render(preview,True,DIM); s.blit(pi,(16,y+26))
                dt=datetime.fromtimestamp(note.stat().st_mtime).strftime("%m/%d %H:%M")
                di2=self.fonts["xs"].render(dt,True,DIM)
                s.blit(di2,(SCREEN_W-di2.get_width()-10,y+6))
        pygame.draw.line(s,BORDER,(0,SCREEN_H-34),(SCREEN_W,SCREEN_H-34),1)
        hx=6
        for key,act in[("Z","OPEN"),("N","NEW"),("Del","DELETE"),("X","BACK")]:
            ki=self.fonts["xs"].render(key,True,(5,10,8)); kw=ki.get_width()+6
            pygame.draw.rect(s,ACCENT,(hx,SCREEN_H-26,kw,18)); s.blit(ki,(hx+3,SCREEN_H-24)); hx+=kw+3
            ai=self.fonts["xs"].render(act,True,DIM); s.blit(ai,(hx,SCREEN_H-24)); hx+=ai.get_width()+12

    def _draw_editor(self,s):
        gw=40
        pygame.draw.rect(s,CARD,(0,self.EDIT_Y,gw,self.EDIT_H))
        pygame.draw.line(s,BORDER,(gw,self.EDIT_Y),(gw,self.EDIT_Y+self.EDIT_H),1)
        for i in range(self.VIS):
            ln=self.scroll+i
            if ln>=len(self.lines): break
            y=self.EDIT_Y+i*self.LINE_H
            if ln==self.cursor_line: pygame.draw.rect(s,CARD_S,(0,y,SCREEN_W,self.LINE_H))
            lni=self.fonts["xs"].render(str(ln+1),True,BORDER)
            s.blit(lni,(gw-lni.get_width()-4,y+2))
            li=self.fonts["xs"].render(self.lines[ln][:90],True,WHITE)
            s.blit(li,(gw+6,y+2))
            if ln==self.cursor_line and self.blink<30:
                cx=gw+6+self.fonts["xs"].size(self.lines[ln][:self.cursor_col])[0]
                pygame.draw.line(s,ACCENT,(cx,y+2),(cx,y+self.LINE_H-2),2)
        total=max(1,len(self.lines))
        bh=max(12,int(self.VIS/total*self.EDIT_H))
        by=self.EDIT_Y+int(self.scroll/total*self.EDIT_H)
        pygame.draw.rect(s,BORDER,(SCREEN_W-4,self.EDIT_Y,3,self.EDIT_H))
        pygame.draw.rect(s,ACCENT,(SCREEN_W-4,by,3,bh))
        pygame.draw.line(s,BORDER,(0,SCREEN_H-34),(SCREEN_W,SCREEN_H-34),1)
        hx=6
        for key,act in[("Arrows","MOVE"),("Ctrl+S","SAVE"),("Esc","SAVE+CLOSE")]:
            ki=self.fonts["xs"].render(key,True,(5,10,8)); kw=ki.get_width()+6
            pygame.draw.rect(s,ACCENT,(hx,SCREEN_H-26,kw,18)); s.blit(ki,(hx+3,SCREEN_H-24)); hx+=kw+3
            ai=self.fonts["xs"].render(act,True,DIM); s.blit(ai,(hx,SCREEN_H-24)); hx+=ai.get_width()+12

    def _draw_new_name(self,s):
        s.fill(BG)
        bx,by,bw,bh=80,SCREEN_H//2-70,SCREEN_W-160,140
        pygame.draw.rect(s,CARD,(bx,by,bw,bh))
        pygame.draw.rect(s,ACCENT,(bx,by,bw,bh),1)
        ti=self.fonts["menu"].render("New Note",True,ACCENT)
        s.blit(ti,(SCREEN_W//2-ti.get_width()//2,by+12))
        s.blit(self.fonts["sm"].render("Filename:",True,DIM),(bx+16,by+44))
        s.blit(self.fonts["menu"].render(self.new_name+"_",True,WHITE),(bx+16,by+64))
        hi=self.fonts["xs"].render("Enter = create   Esc = cancel",True,DIM)
        s.blit(hi,(SCREEN_W//2-hi.get_width()//2,by+108))

def main():
    pygame.init(); screen=pygame.display.set_mode((SCREEN_W,SCREEN_H))
    pygame.display.set_caption("MintNotes"); clock=pygame.time.Clock()
    fonts={"big":pygame.font.SysFont("Courier New",36,bold=True),
           "title":pygame.font.SysFont("Courier New",20,bold=True),
           "menu":pygame.font.SysFont("Courier New",19,bold=True),
           "sm":pygame.font.SysFont("Courier New",14),
           "xs":pygame.font.SysFont("Courier New",12)}
    app=MintNotes(screen,fonts)
    while True:
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: pygame.quit(); sys.exit()
            act,_=app.handle(ev)
            if act=="back": pygame.quit(); sys.exit()
        app.draw(); pygame.display.flip(); clock.tick(FPS)

if __name__=="__main__": main()