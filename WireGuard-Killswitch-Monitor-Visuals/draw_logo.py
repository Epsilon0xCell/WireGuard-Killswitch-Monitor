#!/usr/bin/env python3
"""Killswitch logo: one wind carved ridge in profile on pine black, diagonal crest
lower left to upper right, smooth cream lee side, stepped flint windward side, one
ember red survey flag behind the crest. Wordmark beneath in Arsenal SC cream."""
import sys, math
from PIL import Image, ImageDraw, ImageFont
import numpy as np
W=H=1024
v=sys.argv[1] if len(sys.argv)>1 else "ship"
PINE=(16,22,20); CREAM=(243,238,222); FLINT=(110,118,124); EMBER=(198,52,34)
img=Image.new("RGB",(W,H),PINE); d=ImageDraw.Draw(img,"RGBA")
# ridge profile: crest from (90,600) to (900,300)
crest=[]
for t in range(101):
    x=90+810*t/100; y=600-300*t/100+int(18*math.sin(t/22))
    crest.append((x,y))
base=[(934,760),(90,760)]
d.polygon(crest+base,fill=CREAM)  # lee smooth side
# windward stepped face: upper-left portion cut in steps
for si in range(5):
    pts=[]
    for t in range(48):
        x=90+ (470)*t/48; y=612-165*t/48+int(12*math.sin(t/16))+si*24
        pts.append((x,y))
    d.line(pts,fill=FLINT,width=10 if v!="v1" else 5)
d.line(crest,fill=(255,255,250),width=10 if v!="v1" else 5)
# survey flag just behind crest near top right
fx,fy=800,318
d.line([(fx,fy),(fx,fy+150)],fill=PINE,width=9)
d.polygon([(fx,fy),(fx+118,fy+22),(fx,fy+48)],fill=EMBER)
f=ImageFont.truetype("fonts/ArsenalSC.ttf",54)
txt="WireGuard-Killswitch-Monitor"
# Arsenal SC renders small caps; draw letter-spaced
tw=sum(d.textlength(c,font=f)+6 for c in txt)
x=(W-tw)/2
for c in txt:
    d.text((x,842),c,font=f,fill=CREAM); x+=d.textlength(c,font=f)+6
rng=np.random.default_rng(3); a=np.asarray(img).astype(np.int16); n=rng.normal(0,4,a.shape[:2])[...,None]
img=Image.fromarray(np.clip(a+n,0,255).astype(np.uint8))
out="logo.png" if v=="ship" else f"scratch/logo-{v}.png"
img.save(out); print(out)
img.resize((64,64),Image.LANCZOS).save(f"scratch/logo64-{v}.png"); print("64px saved")
