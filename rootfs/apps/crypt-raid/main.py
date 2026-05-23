#!/usr/bin/env python3
# rootfs/apps/crypt-raid/main.py  --  Crypt Raid v1.0
import os, sys, random, platform
from collections import deque

IS_LINUX = platform.system() == "Linux"
if IS_LINUX:
    os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")
    os.environ.setdefault("SDL_AUDIODRIVER", "alsa")

import pygame

SCREEN_W, SCREEN_H = 640, 480
TILE   = 20
MAP_W, MAP_H = 31, 21
FPS    = 60
VIEW_X = (SCREEN_W - MAP_W * TILE) // 2
VIEW_Y = 48

BG     = (10,  26,  16)
WALL_C = (13,  32,  16)
FLOOR_C= (18,  45,  22)
ACCENT = (61, 204, 112)
DIM    = (90, 150, 105)
WHITE  = (180, 240, 195)
RED    = (220,  60,  60)
GOLD   = (240, 200,  60)
BLUE   = ( 60, 140, 220)
FOG    = ( 12,  30,  18)
BORDER = ( 29, 100,  55)

WALL_T, FLOOR_T, STAIR_T = 0, 1, 2

# ---- Dungeon ----
class Room:
    def __init__(self, x, y, w, h): self.x,self.y,self.w,self.h=x,y,w,h
    def center(self): return self.x+self.w//2, self.y+self.h//2
    def intersects(self, o, p=1):
        return (self.x-p < o.x+o.w and self.x+self.w+p > o.x and
                self.y-p < o.y+o.h and self.y+self.h+p > o.y)

def make_dungeon(floor_num):
    tiles = [[WALL_T]*MAP_H for _ in range(MAP_W)]
    rooms = []
    for _ in range(30):
        w=random.randint(4,9); h=random.randint(3,7)
        x=random.randint(1,MAP_W-w-1); y=random.randint(1,MAP_H-h-1)
        r=Room(x,y,w,h)
        if any(r.intersects(o) for o in rooms): continue
        rooms.append(r)
        for rx in range(r.x,r.x+r.w):
            for ry in range(r.y,r.y+r.h): tiles[rx][ry]=FLOOR_T
        if len(rooms)>=2:
            cx,cy=r.center(); px,py=rooms[-2].center()
            for tx in range(min(cx,px),max(cx,px)+1): tiles[tx][cy]=FLOOR_T
            for ty in range(min(cy,py),max(cy,py)+1): tiles[px][ty]=FLOOR_T
    if rooms:
        sx,sy=rooms[-1].center(); tiles[sx][sy]=STAIR_T
    start=rooms[0].center() if rooms else (MAP_W//2,MAP_H//2)
    return tiles,rooms,start

# ---- Entities ----
class Entity:
    def __init__(self,x,y,char,color,name,hp,atk,dfn):
        self.x,self.y=x,y; self.char=char; self.color=color; self.name=name
        self.hp=hp; self.max_hp=hp; self.atk=atk; self.dfn=dfn; self.alive=True

ENEMY_TYPES=[("Skeleton","S",DIM,6,2,0),("Ghost","G",BLUE,5,3,1),("Demon","D",RED,10,4,1)]
ITEM_TYPES =[("Health Potion","!",ACCENT,"heal",15),("Steel Sword","/",GOLD,"atk",2),("Iron Shield","o",BLUE,"def",1)]

def spawn_enemies(rooms,ps,floor_num):
    out=[]; n=min(3+floor_num*2,12)
    for room in rooms[1:]:
        if n<=0: break
        t=random.choice(ENEMY_TYPES); ex,ey=room.center()
        if (ex,ey)!=ps:
            out.append(Entity(ex,ey,t[1],t[2],t[0],t[3]+floor_num,t[4]+floor_num//2,t[5]))
            n-=1
    return out

def spawn_items(rooms):
    out=[]
    for room in rooms[1::2]:
        t=random.choice(ITEM_TYPES); cx,cy=room.center()
        out.append({"x":cx+random.randint(-1,1),"y":cy+random.randint(-1,1),
                    "name":t[0],"char":t[1],"color":t[2],"type":t[3],"val":t[4]})
    return out

def compute_fov(tiles,px,py,r=8):
    vis=set()
    for dx in range(-r,r+1):
        for dy in range(-r,r+1):
            if dx*dx+dy*dy>r*r: continue
            tx,ty=px+dx,py+dy
            if not(0<=tx<MAP_W and 0<=ty<MAP_H): continue
            steps=max(abs(tx-px),abs(ty-py)); blocked=False
            for i in range(1,steps):
                ix=round(px+(tx-px)*i/steps); iy=round(py+(ty-py)*i/steps)
                if 0<=ix<MAP_W and 0<=iy<MAP_H and tiles[ix][iy]==WALL_T:
                    blocked=True; break
            if not blocked: vis.add((tx,ty))
    return vis

# ---- Game ----
class CryptRaid:
    def __init__(self,screen,fonts):
        self.screen=screen; self.fonts=fonts
        self.floor=1; self.score=0; self.log=deque(maxlen=3)
        self.game_over=False; self.won=False
        self.new_floor()

    def new_floor(self):
        self.tiles,self.rooms,ps=make_dungeon(self.floor)
        self.player=Entity(*ps,"@",ACCENT,"Player",20+self.floor*2,4+self.floor,2)
        self.player.xp=0
        self.enemies=spawn_enemies(self.rooms,ps,self.floor)
        self.items=spawn_items(self.rooms)
        self.seen=set(); self.update_fov()
        self.log.append(f"Floor {self.floor} - Descended.")

    def update_fov(self):
        self.visible=compute_fov(self.tiles,self.player.x,self.player.y)
        self.seen|=self.visible

    def enemy_at(self,x,y):
        return next((e for e in self.enemies if e.alive and e.x==x and e.y==y),None)

    def item_at(self,x,y):
        return next((i for i in self.items if i["x"]==x and i["y"]==y),None)

    def attack(self,a,d):
        dmg=max(0,a.atk-d.dfn+random.randint(-1,2)); d.hp-=dmg
        if d.hp<=0: d.alive=False
        return dmg

    def move_player(self,dx,dy):
        if self.game_over or self.won: return
        nx,ny=self.player.x+dx,self.player.y+dy
        if not(0<=nx<MAP_W and 0<=ny<MAP_H): return
        if self.tiles[nx][ny]==WALL_T: return
        e=self.enemy_at(nx,ny)
        if e:
            dmg=self.attack(self.player,e)
            if e.alive: self.log.append(f"Hit {e.name} {dmg}dmg ({e.hp}hp)")
            else:
                xp=5+self.floor; self.player.xp+=xp; self.score+=xp
                self.log.append(f"{e.name} slain! +{xp}XP")
                self.enemies=[en for en in self.enemies if en.alive]
            self.enemy_turn(); return
        it=self.item_at(nx,ny)
        if it:
            self.items.remove(it)
            if it["type"]=="heal":
                h=min(it["val"],self.player.max_hp-self.player.hp); self.player.hp+=h
                self.log.append(f"{it['name']} +{h}HP")
            elif it["type"]=="atk":
                self.player.atk+=it["val"]; self.log.append(f"{it['name']} +{it['val']}ATK")
            elif it["type"]=="def":
                self.player.dfn+=it["val"]; self.log.append(f"{it['name']} +{it['val']}DEF")
        self.player.x,self.player.y=nx,ny; self.update_fov()
        if self.tiles[nx][ny]==STAIR_T:
            self.floor+=1
            if self.floor>5: self.won=True; self.log.append("Escaped! Victory!")
            else: self.new_floor()
            return
        self.enemy_turn()

    def enemy_turn(self):
        px,py=self.player.x,self.player.y
        for e in self.enemies:
            if not e.alive or (e.x,e.y) not in self.visible: continue
            dx=0 if e.x==px else(1 if e.x<px else -1)
            dy=0 if e.y==py else(1 if e.y<py else -1)
            nx,ny=e.x+dx,e.y+dy
            if nx==px and ny==py:
                dmg=self.attack(e,self.player)
                self.log.append(f"{e.name} hits {dmg}! ({self.player.hp}hp)")
                if self.player.hp<=0:
                    self.player.alive=False; self.game_over=True
                    self.log.append("You died. Game Over.")
            elif self.tiles[nx][ny]!=WALL_T and not self.enemy_at(nx,ny):
                e.x,e.y=nx,ny

    def handle(self,ev):
        if ev.type==pygame.KEYDOWN:
            if self.game_over or self.won:
                if ev.key in(pygame.K_RETURN,pygame.K_z,pygame.K_ESCAPE): return"back",None
                return None,None
            moves={pygame.K_UP:(0,-1),pygame.K_w:(0,-1),pygame.K_DOWN:(0,1),pygame.K_s:(0,1),
                   pygame.K_LEFT:(-1,0),pygame.K_a:(-1,0),pygame.K_RIGHT:(1,0),pygame.K_d:(1,0)}
            if ev.key in moves: self.move_player(*moves[ev.key])
            elif ev.key in(pygame.K_ESCAPE,pygame.K_x): return"back",None
        return None,None

    def draw(self):
        s=self.screen; s.fill(BG)
        pygame.draw.line(s,BORDER,(0,28),(SCREEN_W,28),1)
        s.blit(self.fonts["title"].render("CRYPT RAID",True,ACCENT),
               (SCREEN_W//2-self.fonts["title"].size("CRYPT RAID")[0]//2,4))
        s.blit(self.fonts["sm"].render(f"Floor {self.floor}/5",True,DIM),(8,8))
        sc=self.fonts["sm"].render(f"Score:{self.score}",True,DIM)
        s.blit(sc,(SCREEN_W-sc.get_width()-8,8))
        for tx in range(MAP_W):
            for ty in range(MAP_H):
                sx=VIEW_X+tx*TILE; sy=VIEW_Y+ty*TILE
                if (tx,ty) in self.visible:
                    t=self.tiles[tx][ty]
                    if t==WALL_T:
                        pygame.draw.rect(s,WALL_C,(sx,sy,TILE,TILE))
                        pygame.draw.rect(s,BORDER,(sx,sy,TILE,TILE),1)
                    else:
                        pygame.draw.rect(s,FLOOR_C,(sx,sy,TILE,TILE))
                        if t==STAIR_T:
                            gi=self.fonts["sm"].render(">",True,GOLD)
                            s.blit(gi,(sx+TILE//2-gi.get_width()//2,sy+TILE//2-gi.get_height()//2))
                elif (tx,ty) in self.seen:
                    pygame.draw.rect(s,FOG,(sx,sy,TILE,TILE))
        for it in self.items:
            if (it["x"],it["y"]) in self.visible:
                sx=VIEW_X+it["x"]*TILE; sy=VIEW_Y+it["y"]*TILE
                ci=self.fonts["sm"].render(it["char"],True,it["color"])
                s.blit(ci,(sx+TILE//2-ci.get_width()//2,sy+TILE//2-ci.get_height()//2))
        for e in self.enemies:
            if e.alive and (e.x,e.y) in self.visible:
                sx=VIEW_X+e.x*TILE; sy=VIEW_Y+e.y*TILE
                ei=self.fonts["sm"].render(e.char,True,e.color)
                s.blit(ei,(sx+TILE//2-ei.get_width()//2,sy+TILE//2-ei.get_height()//2))
        px=VIEW_X+self.player.x*TILE; py=VIEW_Y+self.player.y*TILE
        pi=self.fonts["sm"].render("@",True,ACCENT)
        s.blit(pi,(px+TILE//2-pi.get_width()//2,py+TILE//2-pi.get_height()//2))
        hy=VIEW_Y+MAP_H*TILE+4
        hp_pct=self.player.hp/self.player.max_hp
        pygame.draw.rect(s,BORDER,(8,hy,120,10))
        pygame.draw.rect(s,RED if hp_pct<0.3 else ACCENT,(8,hy,int(120*hp_pct),10))
        s.blit(self.fonts["xs"].render(f"HP {self.player.hp}/{self.player.max_hp}",True,WHITE),(8,hy+12))
        s.blit(self.fonts["xs"].render(f"ATK:{self.player.atk} DEF:{self.player.dfn} XP:{self.player.xp}",True,DIM),(140,hy+12))
        ly=hy+26
        for msg in self.log:
            s.blit(self.fonts["xs"].render(msg[:80],True,DIM),(8,ly)); ly+=13
        if self.game_over or self.won:
            ov=pygame.Surface((SCREEN_W,SCREEN_H),pygame.SRCALPHA); ov.fill((0,0,0,160)); s.blit(ov,(0,0))
            col=GOLD if self.won else RED
            mi=self.fonts["big"].render("VICTORY!" if self.won else "GAME OVER",True,col)
            s.blit(mi,(SCREEN_W//2-mi.get_width()//2,SCREEN_H//2-30))
            si=self.fonts["sm"].render(f"Score:{self.score}  Press Z to exit",True,DIM)
            s.blit(si,(SCREEN_W//2-si.get_width()//2,SCREEN_H//2+20))

def main():
    pygame.init()
    screen=pygame.display.set_mode((SCREEN_W,SCREEN_H))
    pygame.display.set_caption("Crypt Raid")
    clock=pygame.time.Clock()
    fonts={"big":pygame.font.SysFont("Courier New",36,bold=True),
           "title":pygame.font.SysFont("Courier New",20,bold=True),
           "menu":pygame.font.SysFont("Courier New",16,bold=True),
           "sm":pygame.font.SysFont("Courier New",14),
           "xs":pygame.font.SysFont("Courier New",12)}
    game=CryptRaid(screen,fonts)
    while True:
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: pygame.quit(); sys.exit()
            act,_=game.handle(ev)
            if act=="back": pygame.quit(); sys.exit()
        game.draw(); pygame.display.flip(); clock.tick(FPS)

if __name__=="__main__": main()