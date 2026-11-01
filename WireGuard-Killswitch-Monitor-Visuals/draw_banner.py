#!/usr/bin/env python3
"""Killswitch banner: polar plateau low across sastrugi, rope line between two cairns
with red flags, tent doorway window with frost ferns lit at left, ski tracks stopping
at the rope, crampon prints beyond, route board on near cairn lettered in Arsenal SC."""
import sys, math, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np
random.seed(17)
W,H=1600,900
v=sys.argv[1] if len(sys.argv)>1 else "ship"
PINE=(16,22,20); CREAM=(243,238,222); FLINT=(110,118,124); EMBER=(198,52,34)
img=Image.new("RGB",(W,H),(198,210,218)); d=ImageDraw.Draw(img,"RGBA")
for y in range(420):
    t=y/420; d.line([(0,y),(W,y)],fill=(int(198+18*t),int(210+12*t),int(218+6*t)))
for i,(ry,rh) in enumerate(((330,24),(366,32),(404,40))):
    pts=[(0,ry+rh)]
    for x in range(0,W+80,80): pts.append((x,ry+random.randint(-5,5)))
    pts.append((W,ry+rh)); d.polygon(pts,fill=(216,222,218) if i%2 else (228,230,224))
# tent at left with lit frost window
d.polygon([(90,500),(230,390),(370,500)],fill=(70,66,54)); d.polygon([(230,390),(370,500),(300,500),(230,436)],fill=(56,52,44))
d.rounded_rectangle([196,436,264,486],8,fill=(255,196,110),outline=(46,42,36),width=3)
for fx,fy in ((210,448),(250,448),(230,464),(212,472),(248,472)):
    for a in range(6): d.line([(fx,fy),(fx+int(8*math.cos(a*math.pi/3)),fy+int(8*math.sin(a*math.pi/3)))],fill=(255,240,210),width=2)
# cairns: near right (with route board), far middle
def cairn(cx,base,s=1.0):
    for i,(cw,ch) in enumerate(((70,22),(54,20),(38,17))):
        y=base-(i+1)*ch*s; d.polygon([(cx-cw*s/2,y+ch*s),(cx+cw*s/2,y+ch*s),(cx+cw*s/3,y),(cx-cw*s/3,y)],fill=(84,88,90) if i%2==0 else (102,106,108))
cairn(760,540,0.9); cairn(1330,560,1.15)
# rope line sagging in bays between cairns with red flags
prev=(760,486)
for bx in (950,1140,1330):
    for t in range(101):
        x=prev[0]+(bx-prev[0])*t/100; y=prev[1]+(492-prev[1])*t/100+math.sin(math.pi*t/100)*24
        d.ellipse([x-2,y-2,x+2,y+2],fill=(58,56,50))
    prev=(bx,492)
for fx,fy in ((950,500),(1140,502)):
    d.line([(fx,fy-22),(fx,fy+14)],fill=(48,46,42),width=4); d.polygon([(fx,fy-22),(fx+30,fy-14),(fx,fy-4)],fill=EMBER)
# ski tracks crossing foreground, stopping at rope line extension; crampon prints beyond
for off in (-14,14):
    pts=[(120+t*5.2,760-t*1.55+off) for t in range(80)]
    d.line(pts,fill=(146,160,170),width=6)
for i in range(8):
    x=560+i*46; y=520+i*11; d.polygon([(x,y),(x+18,y+3),(x+14,y+12),(x-3,y+8)],fill=(140,150,158))
# foreground sastrugi ridges leaning one way
for ry,ph in ((660,0),(770,2)):
    crest=[(x,ry+int(18*math.sin(x/240+ph))) for x in range(-20,W+40,40)]
    d.polygon(crest+[(W,ry+90),(0,ry+90)],fill=(176,190,200))
    d.polygon(crest+[(W,ry-22),(0,ry-22)],fill=(250,248,240))
    d.polygon(crest+[(W,ry+90),(0,ry+90)],fill=(180,194,204))
    for si in range(2):
        d.line([(x,y+20+si*26) for x,y in crest],fill=(156,170,182),width=5)
    d.line(crest,fill=(255,255,252),width=5)
# blowing snow sheets at ankle height
lay=Image.new("RGBA",(W,H),(0,0,0,0)); ld=ImageDraw.Draw(lay)
for i in range(40):
    x=random.randint(0,1500); y=random.randint(560,700); ld.line([(x,y),(x+70,y-4)],fill=(255,255,255,60),width=3)
img=Image.alpha_composite(img.convert("RGBA"),lay.filter(ImageFilter.GaussianBlur(2))).convert("RGB"); d=ImageDraw.Draw(img,"RGBA")
# route board nailed to near cairn, title in Arsenal SC, letters partly scoured
d.rectangle([1120,560,1570,706],fill=(96,74,48)); d.rectangle([1120,560,1570,706],outline=(60,44,26),width=5)
for nx,ny in ((1136,576),(1554,576),(1136,690),(1554,690)): d.ellipse([nx-5,ny-5,nx+5,ny+5],fill=(40,36,30))
f=ImageFont.truetype("fonts/ArsenalSC.ttf",37)
lines=["WireGuard-","Killswitch-Monitor"]
for i,ln in enumerate(lines):
    tw=d.textlength(ln,font=f); d.text(((1345-tw/2),590+i*50),ln,font=f,fill=PINE if v=="v1" else CREAM)
# wind scour streaks over board
for i in range(14):
    x=random.randint(1130,1520); y=random.randint(568,700); d.line([(x,y),(x+36,y)],fill=(200,180,150,110),width=3)
rng=np.random.default_rng(5); a=np.asarray(img).astype(np.int16); n=rng.normal(0,4,a.shape[:2])[...,None]
img=Image.fromarray(np.clip(a+n,0,255).astype(np.uint8))
out="banner.png" if v=="ship" else f"scratch/banner-{v}.png"
img.save(out); print(out)
