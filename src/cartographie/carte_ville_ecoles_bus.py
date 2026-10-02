"""Carte aérienne de Noisy-le-Grand : écoles (annuaire de l'Éducation nationale et
contours BD TOPO de l'IGN) et lignes de bus (tracés Île-de-France Mobilités)."""
import json, math, re, unicodedata
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from shapely.geometry import shape, Point, MultiLineString, LineString, box, Polygon
from shapely.ops import linemerge, transform

R = 6378137
T = 2500; W = H = 2 * T
bbox = json.load(open('bbox_ville.json'))
B = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
N = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
F = lambda p, s: ImageFont.truetype(p, s)
f_tit, f_sub, f_lab, f_num, f_leg, f_src = F(B, 84), F(N, 44), F(B, 34), F(B, 34), F(N, 38), F(N, 34)

def px(lon, lat, *_):
    x = math.radians(lon) * R
    y = math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * R
    return ((x - bbox[0]) / (bbox[2] - bbox[0]) * W, (bbox[3] - y) / (bbox[3] - bbox[1]) * H)
to_px = lambda g: transform(lambda xs, ys, z=None: tuple(zip(*[px(x, y) for x, y in zip(xs, ys)])), g)
hexrgb = lambda h: tuple(int(h.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4))

# --- Fond : assemblage des 4 tuiles, extérieur de la commune estompé -------------
img = Image.new('RGB', (W, H))
for i in range(2):
    for j in range(2):
        img.paste(Image.open(f'tuile_{i}{j}.jpg'), (i * T, j * T))
img = img.convert('RGBA')
commune = to_px(shape(json.load(open('commune.json'))['features'][0]['geometry']))
polys = list(commune.geoms) if commune.geom_type == 'MultiPolygon' else [commune]
masque = Image.new('L', (W, H), 0); dm = ImageDraw.Draw(masque)
for p in polys: dm.polygon(list(p.exterior.coords), fill=255)
dehors = Image.alpha_composite(img, Image.new('RGBA', (W, H), (25, 25, 25, 170)))
dedans = Image.alpha_composite(img, Image.new('RGBA', (W, H), (0, 0, 0, 55)))
img = Image.composite(dedans, dehors, masque)
d = ImageDraw.Draw(img)
for p in polys:
    c = list(p.exterior.coords)
    d.line(c, fill=(20, 20, 20), width=16, joint='curve'); d.line(c, fill=(255, 255, 255), width=7, joint='curve')

# --- Lignes de bus qui traversent la commune -----------------------------------
cadre = box(0, 0, W, H); lignes = []
for f in json.load(open('bus_ville.geojson'))['features']:
    g = shape(f['geometry'])
    if not to_px(g).intersects(commune): continue
    p = f['properties']
    lignes.append(dict(nom=p['linename'], col=hexrgb(p['linecolor']), op=p['operatorid'],
                       geom=to_px(g).intersection(cadre)))
def cle(n):
    m = re.match(r'(\D*)(\d+)', n); return (m.group(1) if m else n, int(m.group(2)) if m else 0)
lignes.sort(key=lambda l: cle(l['nom']))
def segs(g):
    if g.is_empty: return []
    if g.geom_type == 'LineString': return [g]
    return [s for s in getattr(g, 'geoms', []) if s.geom_type == 'LineString']
n = len(lignes)
for i, l in enumerate(lignes):
    off = (i - (n - 1) / 2) * 3.2          # léger décalage : lignes parallèles visibles côte à côte
    m = linemerge(l['geom']) if l['geom'].geom_type == 'MultiLineString' else l['geom']
    l['draw'] = [list(t.coords) for s in segs(m) for t in segs(s.offset_curve(off, join_style=2))]
ov = Image.new('RGBA', (W, H), (0, 0, 0, 0)); do = ImageDraw.Draw(ov)
for l in lignes:
    for c in l['draw']: do.line(c, fill=(10, 10, 10, 255), width=13, joint='curve')
for l in lignes:
    for c in l['draw']: do.line(c, fill=l['col'] + (255,), width=7, joint='curve')
img = Image.alpha_composite(img, ov)

# --- Écoles : annuaire officiel regroupé par site, contour BD TOPO si disponible ---
def base(nom):
    s = re.sub(r"(?i)^ecole (maternelle|élémentaires?|primaire)( privée)?( d'application)?\s*", '', nom)
    s = s.replace(' Noisy-le-Grand', '').replace('Vincent ', '')
    return s.strip()
def norm(s):
    return unicodedata.normalize('NFD', s.lower()).encode('ascii', 'ignore').decode().replace('-', ' ').replace("'", ' ')
sites = {}
for e in json.load(open('annuaire_ecoles.json')):
    k = norm(base(e['nom']))
    s = sites.setdefault(k, dict(nom=base(e['nom']), prive=e['statut'] == 'Privé', pts=[]))
    s['pts'].append(px(e['lon'], e['lat']))
zones = [(to_px(shape(f['geometry'])), f['properties']['toponyme']) for f in json.load(open('ecoles_ville.json'))]
ov = Image.new('RGBA', (W, H), (0, 0, 0, 0)); do = ImageDraw.Draw(ov)
for s in sites.values():
    cx = sum(p[0] for p in s['pts']) / len(s['pts']); cy = sum(p[1] for p in s['pts']) / len(s['pts'])
    s['c'] = (cx, cy)
    # contour BD TOPO situé à moins de 60 m (≈ 50 px) du point de l'annuaire et de même nom
    mot = [w for w in norm(s['nom']).split() if len(w) > 2][0]
    s['zones'] = [z for z, t in zones if z.distance(Point(cx, cy)) < 120 and mot in norm(t)]
    coul = (255, 140, 200) if s['prive'] else (255, 255, 255)
    for z in s['zones']:
        for p in (z.geoms if z.geom_type == 'MultiPolygon' else [z]):
            do.polygon(list(p.exterior.coords), fill=coul + (110,), outline=coul + (255,), width=6)
    if not s['zones']:
        do.ellipse([cx - 22, cy - 22, cx + 22, cy + 22], fill=coul + (220,), outline=(20, 20, 20, 255), width=5)
img = Image.alpha_composite(img, ov); d = ImageDraw.Draw(img)

# --- Placement des étiquettes sans chevauchement ---------------------------------
occupe = [[0, 0, W, 300], [W - 1250, 300, W, 1500], [0, H - 200, W, H], [W - 260, 320, W, 600]]
def libre(r): return all(r[2] < o[0] or r[0] > o[2] or r[3] < o[1] or r[1] > o[3] for o in occupe)
def dans(r): return r[0] > 10 and r[1] > 310 and r[2] < W - 10 and r[3] < H - 210
noms_aff = {"L'Oiseau Lyre": "L'Oiseau-Lyre", 'Hauts Bâtons': 'Hauts-Bâtons', 'Georges Brassens': 'Georges-Brassens',
            "Clos de L'Arche": "Clos de l'Arche", "S'épanouir Autrement": "S'Épanouir Autrement (privé)",
            'Françoise Cabrini': 'Françoise Cabrini (privé)'}
etiquettes = []
for s in sorted(sites.values(), key=lambda s: s['c'][1]):
    txt = noms_aff.get(s['nom'], s['nom'])
    tw = d.textlength(txt, font=f_lab); w, h = tw + 26, 50
    cx, cy = s['c']; rz = 70
    if s['zones']:
        b = [min(z.bounds[0] for z in s['zones']), min(z.bounds[1] for z in s['zones']),
             max(z.bounds[2] for z in s['zones']), max(z.bounds[3] for z in s['zones'])]
    else:
        b = [cx - 24, cy - 24, cx + 24, cy + 24]
    cands = [((b[0] + b[2]) / 2 - w / 2, b[3] + 12), ((b[0] + b[2]) / 2 - w / 2, b[1] - h - 12),
             (b[2] + 12, cy - h / 2), (b[0] - w - 12, cy - h / 2)]
    for dist in (60, 120, 180):
        for a in range(0, 360, 30):
            cands.append((cx + dist * math.cos(math.radians(a)) - w / 2, cy + dist * math.sin(math.radians(a)) - h / 2))
    for tx, ty in cands:
        r = [tx, ty, tx + w, ty + h]
        if dans(r) and libre(r):
            occupe.append([r[0] - 6, r[1] - 6, r[2] + 6, r[3] + 6]); etiquettes.append((r, txt, s)); break
    else:
        print('étiquette non placée :', txt)
    occupe.append(list(b))
for r, txt, s in etiquettes:
    cx, cy = s['c']
    # trait de rappel si l'étiquette est éloignée de l'école
    ex, ey = min(max(cx, r[0]), r[2]), min(max(cy, r[1]), r[3])
    if math.hypot(ex - cx, ey - cy) > 90: d.line([(cx, cy), (ex, ey)], fill=(255, 255, 255), width=4)
    fond = (255, 225, 240) if s['prive'] else (255, 255, 255)
    d.rounded_rectangle(r, radius=10, fill=fond, outline=(20, 20, 20), width=3)
    d.text((r[0] + 13, r[1] + 6), txt, font=f_lab, fill=(20, 20, 20))

# --- Pastilles des lignes : une par ligne d'abord, puis jusqu'à 3 par ligne --------
poses = {l['nom']: 0 for l in lignes}
fracs = [0.5] + [k / 40 for k in range(1, 40) if k != 20]
for passe in range(4):
    for l in lignes:
        if passe < 3 and poses[l['nom']] > passe: continue
        if passe == 3 and poses[l['nom']] > 0: continue
        txt = l['nom'].replace('Express ', 'Exp. ').replace('Magical Shuttle Orly', 'Shuttle')
        tw = d.textlength(txt, font=f_num); w, h = tw + 24, 50
        tc = (0, 0, 0) if sum(l['col']) > 380 else (255, 255, 255)
        fait = False
        for c in sorted(l['draw'], key=lambda c: -LineString(c).length):
            ls = LineString(c)
            for frac in fracs:
                p = ls.interpolate(frac, normalized=True)
                if passe < 3 and not commune.contains(p): continue
                r = [p.x - w / 2, p.y - h / 2, p.x + w / 2, p.y + h / 2]
                if dans(r) and libre(r):
                    d.rounded_rectangle(r, radius=10, fill=l['col'], outline=(10, 10, 10), width=4)
                    d.text((r[0] + 12, r[1] + 6), txt, font=f_num, fill=tc)
                    occupe.append([r[0] - 150, r[1] - 150, r[2] + 150, r[3] + 150]); poses[l['nom']] += 1
                    fait = True; break
            if fait: break
print('pastilles :', poses)

# --- Habillage -------------------------------------------------------------------
d.rectangle([0, 0, W, 290], fill=(20, 20, 20))
d.text((70, 50), "Noisy-le-Grand — écoles maternelles et élémentaires, lignes de bus", font=f_tit, fill=(255, 255, 255))
d.text((70, 170), f"{len(sites)} sites scolaires (annuaire de l'Éducation nationale) · {len(lignes)} lignes de bus traversant la commune",
       font=f_sub, fill=(220, 220, 220))
lh = 56; lx, ly = W - 1210, 330
lw = 1170; lhgt = 110 + lh * (len(lignes) + 3)
d.rounded_rectangle([lx, ly, lx + lw, ly + lhgt], radius=20, fill=(20, 20, 20, 240))
d.text((lx + 30, ly + 25), "Lignes de bus", font=F(B, 48), fill=(255, 255, 255))
for i, l in enumerate(lignes):
    y = ly + 105 + i * lh
    d.line([(lx + 30, y + 22), (lx + 110, y + 22)], fill=l['col'], width=14)
    d.text((lx + 135, y), f"{l['nom']}  —  {l['op']}", font=f_leg, fill=(255, 255, 255))
y = ly + 105 + len(lignes) * lh + 10
d.rectangle([lx + 35, y + 4, lx + 105, y + 40], fill=(255, 255, 255, 150), outline=(255, 255, 255), width=5)
d.text((lx + 135, y), "École publique", font=f_leg, fill=(255, 255, 255))
d.rectangle([lx + 35, y + lh + 4, lx + 105, y + lh + 40], fill=(255, 140, 200, 150), outline=(255, 140, 200), width=5)
d.text((lx + 135, y + lh), "École privée", font=f_leg, fill=(255, 255, 255))
d.line([(lx + 30, y + 2 * lh + 22), (lx + 110, y + 2 * lh + 22)], fill=(20, 20, 20), width=16)
d.line([(lx + 30, y + 2 * lh + 22), (lx + 110, y + 2 * lh + 22)], fill=(255, 255, 255), width=7)
d.text((lx + 135, y + 2 * lh), "Limite communale", font=f_leg, fill=(255, 255, 255))
mpp = (bbox[2] - bbox[0]) * math.cos(math.radians(48.83)) / W; L = 1000 / mpp
x0, y0 = 70, H - 300
d.rectangle([x0 - 30, y0 - 80, x0 + L + 30, y0 + 50], fill=(20, 20, 20))
d.rectangle([x0, y0, x0 + L, y0 + 18], fill=(255, 255, 255)); d.text((x0, y0 - 65), "1 km", font=f_src, fill=(255, 255, 255))
nx, ny = W - 1330, 420
d.ellipse([nx - 80, ny - 80, nx + 80, ny + 80], fill=(20, 20, 20))
d.polygon([(nx, ny - 60), (nx - 30, ny + 32), (nx, ny + 12), (nx + 30, ny + 32)], fill=(255, 255, 255))
d.text((nx - 14, ny + 26), "N", font=f_src, fill=(255, 255, 255))
d.rectangle([0, H - 190, W, H], fill=(20, 20, 20))
d.text((70, H - 150), "Sources : IGN — orthophotographie, BD TOPO (contours des écoles), Admin Express (limite communale) ; "
       "ministère de l'Éducation nationale — annuaire de l'éducation ;", font=f_src, fill=(220, 220, 220))
d.text((70, H - 95), "Île-de-France Mobilités — tracés des lignes régulières de bus. Les tracés indiquent le parcours des lignes, pas l'emplacement des arrêts.",
       font=f_src, fill=(220, 220, 220))
img.convert('RGB').save('/home/user/Operation_robespierre/images/carte_noisy_le_grand_ecoles_bus.jpg', quality=88)
print(len(sites), 'sites ;', [l['nom'] for l in lignes])
for s in sorted(sites.values(), key=lambda s: s['nom']): print(f"  {s['nom']:28} contour={'oui' if s['zones'] else 'non'}")
