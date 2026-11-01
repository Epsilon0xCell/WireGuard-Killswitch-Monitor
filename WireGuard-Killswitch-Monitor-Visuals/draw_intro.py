#!/usr/bin/env python3
"""WireGuard-Killswitch-Monitor intro: sastrugi field at the pole, wordless.
Three foreground ridges with streaming grains, rope line between cairns with red
flags, ski tracks ending at the rope, crampon prints beyond, tent with one lit
frost-ferned window at far right, stove smoke bent flat. No text of any kind."""
import sys, random, math
from PIL import Image, ImageDraw, ImageFilter
import numpy as np
random.seed(31)
W,H=1600,900
v=sys.argv[1] if len(sys.argv)>1 else "ship"
PINE=(16,22,20); CREAM=(243,238,222); FLINT=(110,118,124); EMBER=(198,52,34); SKY=(196,208,216)
img=Image.new("RGB",(W,H),SKY); d=ImageDraw.Draw(img,"RGBA")
for y in range(430):
    t=y/430; d.line([(0,y),(W,y)],fill=(int(196+20*t),int(208+14*t),int(216+8*t)))
# plateau bands ridge after ridge
for i,(ry,rh) in enumerate(((330,26),(368,34),(408,44))):
    col=(222,226,220) if i%2==0 else (208,216,214)
    pts=[(0,ry+rh)]
    for x in range(0,W+80,80): pts.append((x,ry+random.randint(-6,6)))
    pts.append((W,ry+rh)); d.polygon(pts,fill=col)
# tent far right, low against wind; lit frost window; stove pipe smoke bent flat
d.polygon([(1290,470),(1420,380),(1550,470)],fill=(74,70,58))
d.polygon([(1420,380),(1550,470),(1480,470),(1420,420)],fill=(60,56,48))
d.line([(1470,392),(1470,344)],fill=(40,40,40),width=7)
sm=Image.new("RGBA",(W,H),(0,0,0,0)); sd=ImageDraw.Draw(sm)
for i in range(26): sd.ellipse([1470+i*4,338-i*1-i*i//40,1496+i*4,352-i*1-i*i//40],fill=(230,232,230,60))
img=Image.alpha_composite(img.convert("RGBA"),sm.filter(ImageFilter.GaussianBlur(5))).convert("RGB"); d=ImageDraw.Draw(img,"RGBA")
win=(1396,428,1444,466)
d.rounded_rectangle(win,8,fill=(255,196,110),outline=(50,46,40),width=3)
for fx,fy in ((1406,438),(1434,438),(1420,452),(1408,458),(1432,458)):
    for a in range(6):
        d.line([(fx,fy),(fx+int(9*math.cos(a*math.pi/3)),fy+int(9*math.sin(a*math.pi/3)))],fill=(255,240,210),width=2)
# cairns and rope line traversing middle ground
def cairn(cx,base,s=1.0):
    for i,(cw,ch) in enumerate(((64,20),(50,18),(36,16))):
        y=base-(i+1)*ch*s; d.polygon([(cx-cw*s/2,y+ch*s),(cx+cw*s/2,y+ch*s),(cx+cw*s/3,y),(cx-cw*s/3,y)],fill=(86,90,92) if i%2==0 else (104,108,110))
cairn(180,520); cairn(1180,500,0.85)
# rope with sagging bays
prev=(180,462)
for bx in (430,680,930,1180):
    top_y=462 if bx==1180 else 448
    for t in range(101):
        x=prev[0]+(bx-prev[0])*t/100; y=prev[1]+(top_y-prev[1])*t/100+math.sin(math.pi*t/100)*26
        d.ellipse([x-2,y-2,x+2,y+2],fill=(60,58,52))
    prev=(bx,top_y)
# red flags along rope, limp and lifted
for fx,fy,lift in ((430,474,6),(680,476,-10),(930,472,14)):
    d.line([(fx,fy-24),(fx,fy+16)],fill=(50,48,44),width=4)
    d.polygon([(fx,fy-24),(fx+34,fy-24+lift),(fx,fy-6)],fill=EMBER)
# ski tracks ending at rope (left), crampon prints beyond at different angle
for off in (-15,15):
    pts=[]
    for t in range(60):
        x=40+t*6.2; y=596-t*1.7+off*0.4+ (off if t>50 else off*t/50); pts.append((x,y))
    d.line(pts,fill=(160,172,180),width=5)
for i in range(9):
    x=520+i*52; y=430+i*13
    d.polygon([(x,y),(x+20,y+4),(x+16,y+13),(x-3,y+9)],fill=(142,152,158))
# foreground: three large ridges crossing lower frame, sharp crests, stepped windward faces
for ry,drop,ph in ((600,110,0),(716,120,2),(832,130,4)):
    crest=[]
    for x in range(-20,W+40,40): crest.append((x,ry+int(22*math.sin(x/230+ph))-int(x*0.012)))
    # shadow side (lee, smooth blue grey) below crest
    d.polygon(crest+[(W,ry+drop),(0,ry+drop)],fill=(168,182,194))
    # windward stepped face above the smooth curve: ledges climbing to crest
    for si in range(4):
        sy=ry+drop-14-si*22
        pts=[]
        for x in range(0,W+40,40): pts.append((x,sy+int(18*math.sin(x/230+ph))-int(x*0.012)))
        d.line(pts,fill=(196,206,214),width=7)
    d.polygon(crest+[(W,ry-26),(0,ry-26)],fill=(250,248,240))
    d.polygon(crest+[(W,ry+drop),(0,ry+drop)],fill=(172,186,198))
    # re-draw stepped ledges on the shadow face
    for si in range(3):
        pts=[]
        for x in range(0,W+40,40):
            base=ry+int(22*math.sin(x/230+ph))-int(x*0.012)
            pts.append((x,base+18+si*26))
        d.line(pts,fill=(150,164,178),width=5)
    d.line(crest,fill=(255,255,252),width=5)
    for gx in range(60,W,120):
        gy=ry+int(22*math.sin(gx/230+ph))-int(gx*0.012)
        for k in range(8):
            x2=gx+k*14; y2=gy-4-k*2
            d.line([(x2,y2),(x2+11,y2-2)],fill=(255,255,252,190),width=2)
rng=np.random.default_rng(7); a=np.asarray(img).astype(np.int16); n=rng.normal(0,4,a.shape[:2])[...,None]
img=Image.fromarray(np.clip(a+n,0,255).astype(np.uint8))
out="intro-banner.png" if v=="ship" else f"scratch/intro-{v}.png"
img.save(out); print(out)
