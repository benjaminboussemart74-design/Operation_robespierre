"""Visuels d'annonce : quartier Champy - Les Hauts-Bâtons (Cormiers inclus) mis en valeur dans Noisy-le-Grand.
Contours : fichier des quartiers de la Ville de Noisy-le-Grand."""
import csv, json, math
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from shapely.geometry import shape
from shapely.ops import unary_union

R = 6378137; S = 2                        # dessin en double résolution puis réduction (bords lissés)
W = H = 4000
Q = [(r['Nom de quartier'], shape(json.loads(r['geo_shape']))) for r in csv.DictReader(open('quartiers.csv', encoding='utf-8-sig'))]
CIBLE = 'Champy - Les Hauts-Bâtons'
def merc(lon, lat): return math.radians(lon) * R, math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * R
ville = unary_union([g for _, g in Q])
x0, y0 = merc(ville.bounds[0], ville.bounds[1]); x1, y1 = merc(ville.bounds[2], ville.bounds[3])
cx, cy = (x0 + x1) / 2, (y0 + y1) / 2; h = max(x1 - x0, y1 - y0) / 2 * 1.08
bbox = [cx - h, cy - h, cx + h, cy + h]
def px(lon, lat):
    x, y = merc(lon, lat)
    return ((x - bbox[0]) / (bbox[2] - bbox[0]) * W * S, (bbox[3] - y) / (bbox[3] - bbox[1]) * H * S)
def anneaux(g):
    for p in (g.geoms if g.geom_type == 'MultiPolygon' else [g]):
        yield [px(*c) for c in p.exterior.coords]

ACCENT = (232, 72, 85)       # rouge corail : très visible, lisible en impression comme à l'écran
GRIS = (214, 218, 224); BORD = (255, 255, 255); TEXTE_GRIS = (120, 128, 140)
B = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'; N = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
cible = next(g for n, g in Q if n == CIBLE)

def calque_quartier():
    """Quartier en couleur avec halo lumineux et ombre portée."""
    m = Image.new('L', (W * S, H * S), 0); dm = ImageDraw.Draw(m)
    for a in anneaux(cible): dm.polygon(a, fill=255)
    halo = m.filter(ImageFilter.GaussianBlur(60))
    ombre = Image.new('RGBA', m.size, (0, 0, 0, 0)); ombre.putalpha(m.filter(ImageFilter.GaussianBlur(30)).point(lambda v: int(v * 0.45)))
    c = Image.new('RGBA', m.size, (0, 0, 0, 0))
    lum = Image.new('RGBA', m.size, ACCENT + (0,)); lum.putalpha(halo.point(lambda v: int(min(255, v * 1.6) * 0.8)))
    c = Image.alpha_composite(c, lum)
    dec = Image.new('RGBA', m.size, (0, 0, 0, 0)); dec.paste(ombre, (18, 26))
    c = Image.alpha_composite(c, dec)
    q = Image.new('RGBA', m.size, ACCENT + (255,)); q.putalpha(m)
    c = Image.alpha_composite(c, q)
    d = ImageDraw.Draw(c)
    for a in anneaux(cible): d.line(a + [a[0]], fill=(255, 255, 255, 255), width=14, joint='curve')
    return c

def etiquettes(img, couleur_autres, avec_autres=True):
    d = ImageDraw.Draw(img)
    if avec_autres:
        f = ImageFont.truetype(N, 34 * S)
        for n, g in Q:
            if n == CIBLE: continue
            p = g.representative_point(); x, y = px(p.x, p.y)
            for i, ligne in enumerate(n.replace(' - ', ' -\n').split('\n')):
                tw = d.textlength(ligne, font=f); d.text((x - tw / 2, y - 22 * S + i * 42 * S), ligne, font=f, fill=couleur_autres)
    # nom du quartier mis en valeur, dans un cartouche relié au quartier
    p = cible.representative_point(); x, y = px(p.x, p.y)
    f1 = ImageFont.truetype(B, 64 * S); f2 = ImageFont.truetype(N, 42 * S)
    l1, l2 = "Les Cormiers – Les Hauts-Bâtons", "Quartier Champy - Les Hauts-Bâtons"
    w = max(d.textlength(l1, font=f1), d.textlength(l2, font=f2)) + 80 * S; hh = 175 * S
    bx, by = x - w / 2 + 120 * S, y - 520 * S
    bx = min(bx, W * S - w - 40 * S)
    d.line([(x, y), (bx + w / 2, by + hh)], fill=(40, 40, 50), width=7 * S)
    d.ellipse([x - 16 * S, y - 16 * S, x + 16 * S, y + 16 * S], fill=(255, 255, 255), outline=(40, 40, 50), width=6 * S)
    d.rounded_rectangle([bx, by, bx + w, by + hh], radius=26 * S, fill=(30, 32, 40))
    d.rectangle([bx, by + 22 * S, bx + 14 * S, by + hh - 22 * S], fill=ACCENT)
    d.text((bx + 45 * S, by + 22 * S), l1, font=f1, fill=(255, 255, 255))
    d.text((bx + 45 * S, by + 105 * S), l2, font=f2, fill=(200, 205, 215))

# --- Version 1 : silhouette en aplat sur fond transparent --------------------------
img = Image.new('RGBA', (W * S, H * S), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
for n, g in Q:
    if n == CIBLE: continue
    for a in anneaux(g): d.polygon(a, fill=GRIS + (255,))
for n, g in Q:
    for a in anneaux(g): d.line(a + [a[0]], fill=BORD + (255,), width=8, joint='curve')
img = Image.alpha_composite(img, calque_quartier())
etiquettes(img, TEXTE_GRIS)
img.resize((W, H), Image.LANCZOS).save('/home/user/Operation_robespierre/images/visuel_quartier_hauts_batons_transparent.png')
# même chose sans les noms des autres quartiers (plus épuré pour une affiche)
img = Image.new('RGBA', (W * S, H * S), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
for n, g in Q:
    if n == CIBLE: continue
    for a in anneaux(g): d.polygon(a, fill=GRIS + (255,))
for n, g in Q:
    for a in anneaux(g): d.line(a + [a[0]], fill=BORD + (255,), width=8, joint='curve')
img = Image.alpha_composite(img, calque_quartier())
etiquettes(img, TEXTE_GRIS, avec_autres=False)
img.resize((W, H), Image.LANCZOS).save('/home/user/Operation_robespierre/images/visuel_quartier_hauts_batons_epure.png')
json.dump(bbox, open('bbox_visuel.json', 'w'))
print('ok', bbox)

# --- Version 2 : sur photographie aérienne ----------------------------------------
from PIL import ImageOps, ImageEnhance
photo = Image.new('RGB', (W, H))
for i in range(2):
    for j in range(2):
        photo.paste(Image.open(f'v_{i}{j}.jpg'), (i * 2000, j * 2000))
photo = photo.resize((W * S, H * S), Image.BICUBIC)
gris = ImageEnhance.Brightness(ImageOps.grayscale(photo).convert('RGB')).enhance(0.45)
vif = ImageEnhance.Color(ImageEnhance.Contrast(photo).enhance(1.1)).enhance(1.25)
m = Image.new('L', (W * S, H * S), 0); dm = ImageDraw.Draw(m)
for a in anneaux(cible): dm.polygon(a, fill=255)
img = Image.composite(vif, gris, m).convert('RGBA')
# limite communale et des quartiers, discrètes
d = ImageDraw.Draw(img)
for n, g in Q:
    for a in anneaux(g): d.line(a + [a[0]], fill=(255, 255, 255, 90), width=5, joint='curve')
for a in anneaux(ville): d.line(a + [a[0]], fill=(255, 255, 255, 200), width=10, joint='curve')
# halo et contour du quartier
halo = Image.new('RGBA', m.size, ACCENT + (0,)); halo.putalpha(m.filter(ImageFilter.GaussianBlur(45)).point(lambda v: int(v * 0.9) if v < 250 else 0))
img = Image.alpha_composite(img, halo)
d = ImageDraw.Draw(img)
for a in anneaux(cible):
    d.line(a + [a[0]], fill=ACCENT + (255,), width=26, joint='curve')
    d.line(a + [a[0]], fill=(255, 255, 255, 255), width=8, joint='curve')
etiquettes(img, (220, 220, 220), avec_autres=False)
img.resize((W, H), Image.LANCZOS).convert('RGB').save('/home/user/Operation_robespierre/images/visuel_quartier_hauts_batons_aerien.jpg', quality=92)
print('aérien ok')
