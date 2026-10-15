import imageio.v2 as iio, numpy as np
from PIL import Image, ImageDraw
frames=[]
for i in range(96):  # 4 s a 24 fps: figura sentada que se pone de pie apoyada en una silla y luego suelta la silla
    t=i/95; im=Image.new("RGB",(480,360),(235,230,220)); d=ImageDraw.Draw(im)
    d.rectangle([0,300,480,360],fill=(150,120,90))                  # piso
    d.rectangle([300,200,360,300],outline=(80,50,30),width=6)       # silla
    h=min(1,t*1.6); x=230 if t<0.75 else 230-(t-0.75)*200            # sube y luego camina sin apoyo
    hip=300-30-90*h; head=hip-110
    d.ellipse([x-22,head-22,x+22,head+22],fill=(240,190,150))
    d.line([x,head+22,x,hip],fill=(60,90,160),width=14)
    d.line([x,hip,x-15,300],fill=(40,40,60),width=12); d.line([x,hip,x+15,300],fill=(40,40,60),width=12)
    hand=(305,215) if t<0.75 else (x+40,hip-40)
    d.line([x,head+50,*hand],fill=(240,190,150),width=10)
    frames.append(np.array(im))
iio.mimwrite("demo_pararse.mp4",frames,fps=24,codec="libx264",quality=6)
print("ok")
