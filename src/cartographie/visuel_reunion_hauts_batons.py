"""Visuel d'annonce : vue aérienne du quartier Champy - Les Hauts-Bâtons (Cormiers inclus),
contour en pointillés lumineux et repère sur le City Stade, lieu de la réunion publique."""
import csv, json, math
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageOps, ImageFont, ImageChops
from shapely.geometry import shape, LineString

R = 6378137; W, H = 4000, 3000
bbox = json.load(open('bbox_sypa2.json'))
g = shape(json.load(open('perimetre_cormiers_hb.json')))
def px(lon, lat):
    x = math.radians(lon) * R; y = math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * R
    return ((x - bbox[0]) / (bbox[2] - bbox[0]) * W, (bbox[3] - y) / (bbox[3] - bbox[1]) * H)
contour = [px(*c) for c in g.exterior.coords]
ACCENT = (232, 72, 85)
B = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'; N = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'

photo = Image.new('RGB', (W, H))
for i in range(2):
    for j in range(2):
        photo.paste(Image.open(f's2_{i}{j}.jpg'), (i * 2000, j * 1500))

# intérieur : plus lumineux et plus saturé ; extérieur : désaturé, assombri, légèrement flou
dedans = ImageEnhance.Color(ImageEnhance.Contrast(ImageEnhance.Brightness(photo).enhance(1.08)).enhance(1.08)).enhance(1.2)
dehors = photo.filter(ImageFilter.GaussianBlur(2.5))
dehors = Image.blend(dehors, ImageOps.grayscale(dehors).convert('RGB'), 0.55)
dehors = ImageEnhance.Brightness(dehors).enhance(0.62)
masque = Image.new('L', (W, H), 0); ImageDraw.Draw(masque).polygon(contour, fill=255)
img = Image.composite(dedans, dehors, masque.filter(ImageFilter.GaussianBlur(6))).convert('RGBA')

# vignettage léger sur les bords
vig = Image.new('L', (W, H), 0); ImageDraw.Draw(vig).ellipse([-W * 0.15, -H * 0.2, W * 1.15, H * 1.2], fill=255)
vig = vig.filter(ImageFilter.GaussianBlur(350))
noir = Image.new('RGBA', (W, H), (0, 0, 0, 255)); noir.putalpha(ImageOps.invert(vig).point(lambda v: int(v * 0.55)))
img = Image.alpha_composite(img, noir)

# contour : halo blanc diffus puis pointillés nets
halo = Image.new('RGBA', (W, H), (255, 255, 255, 0)); dh = ImageDraw.Draw(halo)
dh.line(contour, fill=(255, 255, 255, 200), width=34, joint='curve')
halo = halo.filter(ImageFilter.GaussianBlur(22))
img = Image.alpha_composite(img, halo)
d = ImageDraw.Draw(img)
ls = LineString(contour); L = ls.length; t = 0; tiret, espace = 62, 30
while t < L:
    pts = [ls.interpolate(min(t + k * tiret / 6, L)) for k in range(7)]
    d.line([(p.x, p.y) for p in pts], fill=(255, 255, 255, 255), width=14, joint='curve')
    for p in (pts[0], pts[-1]): d.ellipse([p.x - 7, p.y - 7, p.x + 7, p.y + 7], fill=(255, 255, 255, 255))
    t += tiret + espace
base = img.copy()

def repere(img, avec_texte=True):
    """Repère « goutte » avec ondes concentriques sur le City Stade, et cartouche d'annonce."""
    sx, sy = px(2.57229, 48.84474)
    c = Image.new('RGBA', (W, H), (0, 0, 0, 0)); dc = ImageDraw.Draw(c)
    for r, a in ((230, 45), (165, 75), (105, 120)):           # ondes
        dc.ellipse([sx - r, sy - r * 0.42, sx + r, sy + r * 0.42], outline=ACCENT + (a,), width=10, fill=ACCENT + (a // 4,))
    img = Image.alpha_composite(img, c)
    # ombre portée de la goutte
    o = Image.new('RGBA', (W, H), (0, 0, 0, 0)); do = ImageDraw.Draw(o)
    do.ellipse([sx - 40, sy - 14, sx + 40, sy + 14], fill=(0, 0, 0, 150)); o = o.filter(ImageFilter.GaussianBlur(10))
    img = Image.alpha_composite(img, o)
    d = ImageDraw.Draw(img)
    rt, hgt = 95, 260                                          # goutte : tête ronde + pointe sur le City Stade
    cx, cy = sx, sy - hgt
    a = math.asin(rt / hgt)
    p1 = (cx - rt * math.cos(a), cy + rt * math.sin(a)); p2 = (cx + rt * math.cos(a), cy + rt * math.sin(a))
    e = 9                                                      # liseré blanc
    pe1 = (cx - (rt + e) * math.cos(a), cy + (rt + e) * math.sin(a)); pe2 = (cx + (rt + e) * math.cos(a), cy + (rt + e) * math.sin(a))
    d.polygon([pe1, pe2, (sx, sy + e * 1.6)], fill=(255, 255, 255))
    d.ellipse([cx - rt - e, cy - rt - e, cx + rt + e, cy + rt + e], fill=(255, 255, 255))
    d.polygon([p1, p2, (sx, sy)], fill=ACCENT)
    d.ellipse([cx - rt, cy - rt, cx + rt, cy + rt], fill=ACCENT)
    d.ellipse([cx - 40, cy - 40, cx + 40, cy + 40], fill=(255, 255, 255))
    d.ellipse([cx - 17, cy - 17, cx + 17, cy + 17], fill=ACCENT)
    if avec_texte:
        f1, f2, f3 = ImageFont.truetype(B, 92), ImageFont.truetype(B, 58), ImageFont.truetype(N, 54)
        l0, l1, l2 = "RÉUNION PUBLIQUE", "City Stade des Hauts-Bâtons", "Samedi 3 octobre · 16 h"
        w = max(d.textlength(l1, font=f1), d.textlength(l0, font=f2), d.textlength(l2, font=f3)) + 120
        bx, by = cx - w - 190, cy - 170
        bx = max(bx, 60)
        ombre = Image.new('RGBA', (W, H), (0, 0, 0, 0)); ImageDraw.Draw(ombre).rounded_rectangle([bx + 14, by + 22, bx + w + 14, by + 360], radius=36, fill=(0, 0, 0, 140))
        img = Image.alpha_composite(img, ombre.filter(ImageFilter.GaussianBlur(24))); d = ImageDraw.Draw(img)
        d.rounded_rectangle([bx, by, bx + w, by + 340], radius=36, fill=(255, 255, 255, 250))
        d.rounded_rectangle([bx, by, bx + 22, by + 340], radius=11, fill=ACCENT)
        d.text((bx + 70, by + 40), l0, font=f2, fill=ACCENT)
        d.text((bx + 70, by + 115), l1, font=f1, fill=(25, 28, 36))
        d.text((bx + 70, by + 240), l2, font=f3, fill=(70, 75, 88))
        d.line([(bx + w, by + 170), (cx - rt - 24, cy)], fill=(255, 255, 255), width=8)
    return img

repere(base.copy(), True).convert('RGB').save('/home/user/Operation_robespierre/images/visuel_reunion_hauts_batons.jpg', quality=93)
repere(base.copy(), False).convert('RGB').save('/home/user/Operation_robespierre/images/visuel_reunion_hauts_batons_sans_texte.jpg', quality=93)
print('ok')
