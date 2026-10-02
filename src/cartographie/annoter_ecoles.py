import json, math
from PIL import Image, ImageDraw, ImageFont
R=6378137
bbox=json.load(open('bbox.json')); W=H=2400
def px(lon,lat):
    x=math.radians(lon)*R; y=math.log(math.tan(math.pi/4+math.radians(lat)/2))*R
    return ((x-bbox[0])/(bbox[2]-bbox[0])*W, (bbox[3]-y)/(bbox[3]-bbox[1])*H)
img=Image.open('ortho.jpg').convert('RGBA')
ov=Image.new('RGBA',img.size,(0,0,0,0)); d=ImageDraw.Draw(ov)
B='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'; N='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
f_lab=ImageFont.truetype(B,46); f_tit=ImageFont.truetype(B,58); f_src=ImageFont.truetype(N,30)
style={'Groupe Scolaire Van Gogh':((230,57,70),'École Van Gogh'),
       'Groupe Scolaire Jules Ferry':((255,183,3),'École Jules Ferry'),
       'Groupe Scolaire Hauts Bâtons':((0,180,216),'École des Hauts-Bâtons')}
labels=[]
for f in json.load(open('ecoles.json')):
    col,name=style[f['properties']['toponyme']]
    allp=[]
    for poly in f['geometry']['coordinates']:
        pts=[px(*c) for c in poly[0]]; allp+=pts
        d.polygon(pts,fill=col+(70,))
        d.line(pts+[pts[0]],fill=col+(255,),width=9,joint='curve')
    cx=sum(p[0] for p in allp)/len(allp); cy=sum(p[1] for p in allp)/len(allp)
    labels.append((cx,cy,col,name,max(p[1] for p in allp),min(p[1] for p in allp)))
img=Image.alpha_composite(img,ov); d=ImageDraw.Draw(img)
for cx,cy,col,name,ymax,ymin in labels:
    tw=d.textlength(name,font=f_lab); th=58; pad=18
    # étiquette placée sous le contour (au-dessus pour Jules Ferry, pour éviter les chevauchements)
    above = 'Ferry' in name
    ty = ymin-th-2*pad-30 if above else ymax+30
    tx=min(max(cx-tw/2-pad,20),W-tw-2*pad-20)
    d.rounded_rectangle([tx,ty,tx+tw+2*pad,ty+th+2*pad*0.6],radius=14,fill=(20,20,20,235),outline=col,width=6)
    d.text((tx+pad,ty+pad*0.45),name,font=f_lab,fill=(255,255,255))
# bandeau titre
d.rectangle([0,0,W,110],fill=(20,20,20,230))
d.text((40,22),"Quartier des Cormiers et des Hauts-Bâtons — Noisy-le-Grand",font=f_tit,fill=(255,255,255))
# échelle 100 m
mpp=(bbox[2]-bbox[0])*math.cos(math.radians(48.846))/W; L=100/mpp
x0,y0=60,H-120
d.rectangle([x0-25,y0-70,x0+L+25,y0+45],fill=(20,20,20,220))
d.rectangle([x0,y0,x0+L,y0+14],fill=(255,255,255)); d.text((x0,y0-55),"100 m",font=f_src,fill=(255,255,255))
# nord
nx,ny=W-110,190
d.ellipse([nx-60,ny-60,nx+60,ny+60],fill=(20,20,20,220))
d.polygon([(nx,ny-45),(nx-22,ny+25),(nx,ny+10),(nx+22,ny+25)],fill=(255,255,255))
d.text((nx-12,ny+18),"N",font=f_src,fill=(255,255,255))
src="Source : IGN — Géoplateforme, orthophotographie et BD TOPO (contours des groupes scolaires)"
tw=d.textlength(src,font=f_src); d.rectangle([W-tw-50,H-62,W,H],fill=(20,20,20,220)); d.text((W-tw-25,H-52),src,font=f_src,fill=(255,255,255))
img.convert('RGB').save('/home/user/Operation_robespierre/images/vue_aerienne_ecoles_van_gogh_jules_ferry_hauts_batons.jpg',quality=90)
