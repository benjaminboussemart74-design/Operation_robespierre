"""Vue aérienne du quartier des Cormiers et des Hauts-Bâtons (Noisy-le-Grand) :
écoles (contours BD TOPO de l'IGN) et lignes de bus (tracés Île-de-France Mobilités)."""
import json, math
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import LineString, MultiLineString, box
from shapely.ops import linemerge

R = 6378137
bbox = json.load(open('bbox_bus.json'))
W = H = 2800
B = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
N = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
f_lab = ImageFont.truetype(B, 48); f_tit = ImageFont.truetype(B, 62)
f_num = ImageFont.truetype(B, 40); f_leg = ImageFont.truetype(N, 36); f_src = ImageFont.truetype(N, 32)

def px(lon, lat):
    x = math.radians(lon) * R
    y = math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * R
    return ((x - bbox[0]) / (bbox[2] - bbox[0]) * W, (bbox[3] - y) / (bbox[3] - bbox[1]) * H)

def hexrgb(h):
    h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

img = Image.open('ortho_bus.jpg').convert('RGBA')
# léger assombrissement du fond pour faire ressortir les tracés
img = Image.alpha_composite(img, Image.new('RGBA', img.size, (0, 0, 0, 60)))
cadre = box(0, 0, W, H)

# --- Lignes de bus ---------------------------------------------------------
def segments(geom):
    if geom.geom_type == 'LineString': return [geom]
    return [g for g in getattr(geom, 'geoms', []) if g.geom_type == 'LineString']
lignes = []
EXCLUES = {'213'}          # passe sur l'avenue au nord, ne dessert pas le quartier
for f in json.load(open('bus_large.geojson'))['features']:
    if f['properties']['linename'] in EXCLUES: continue
    g = f['geometry']
    parts = g['coordinates'] if g['type'] == 'MultiLineString' else [g['coordinates']]
    # fusion des deux sens : on garde le premier tracé, et du second seulement ce qui s'en écarte de plus de 25 m
    lignes_px = [LineString([px(*c) for c in p]) for p in parts]
    base = lignes_px[0]; seuil = 25 / ((bbox[2] - bbox[0]) * math.cos(math.radians(48.846)) / W)
    morceaux = [base]
    for autre in lignes_px[1:]:
        reste = autre.difference(base.buffer(seuil))
        morceaux += [m for m in segments(reste) if m.length > seuil * 2]
    geom = MultiLineString([list(m.coords) for m in morceaux]).intersection(cadre)
    if geom.is_empty or geom.length < 50:
        continue
    p = f['properties']
    lignes.append(dict(nom=p['linename'], col=hexrgb(p['linecolor']), op=p['operatorid'], geom=geom))
lignes.sort(key=lambda l: (len(l['nom']), l['nom']))

ov = Image.new('RGBA', img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
def segments(geom):
    if geom.geom_type == 'LineString': return [geom]
    return [g for g in getattr(geom, 'geoms', []) if g.geom_type == 'LineString']
# décalage latéral pour que les lignes empruntant la même rue restent visibles côte à côte
n = len(lignes)
for i, l in enumerate(lignes):
    off = (i - (n - 1) / 2) * 9
    l['draw'] = []
    for s in segments(linemerge(l['geom']) if l['geom'].geom_type != 'LineString' else l['geom']):
        o = s.offset_curve(off, join_style=2) if abs(off) > 0.1 else s
        for t in segments(o):
            l['draw'].append(list(t.coords))
for l in lignes:
    for c in l['draw']:
        d.line(c, fill=(15, 15, 15, 255), width=17, joint='curve')
for l in lignes:
    for c in l['draw']:
        d.line(c, fill=l['col'] + (255,), width=10, joint='curve')
img = Image.alpha_composite(img, ov)

# --- Écoles ----------------------------------------------------------------
ov = Image.new('RGBA', img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
noms = {'Groupe Scolaire Van Gogh': 'École Van Gogh',
        'Groupe Scolaire Jules Ferry': 'École Jules Ferry',
        'Groupe Scolaire Hauts Bâtons': 'École des Hauts-Bâtons'}
etiq = []
for f in json.load(open('ecoles.json')):
    allp = []
    for poly in f['geometry']['coordinates']:
        pts = [px(*c) for c in poly[0]]; allp += pts
        d.polygon(pts, fill=(255, 255, 255, 80))
        d.line(pts + [pts[0]], fill=(255, 255, 255, 255), width=8, joint='curve')
    etiq.append((noms[f['properties']['toponyme']], allp))
img = Image.alpha_composite(img, ov); d = ImageDraw.Draw(img)

occupe = []
def libre(r):
    return all(r[2] < o[0] or r[0] > o[2] or r[3] < o[1] or r[1] > o[3] for o in occupe)

for name, allp in etiq:
    cx = sum(p[0] for p in allp) / len(allp)
    tw = d.textlength(name, font=f_lab); pad = 18; th = 60
    ymin = min(p[1] for p in allp); ymax = max(p[1] for p in allp)
    ty = ymin - th - 2 * pad - 25 if 'Ferry' in name else ymax + 25
    tx = min(max(cx - tw / 2 - pad, 20), W - tw - 2 * pad - 20)
    r = [tx, ty, tx + tw + 2 * pad, ty + th + pad]
    d.rounded_rectangle(r, radius=14, fill=(255, 255, 255, 245), outline=(20, 20, 20), width=4)
    d.text((tx + pad, ty + pad * 0.4), name, font=f_lab, fill=(20, 20, 20))
    occupe.append(r)

# pastilles de numéro de ligne, placées le long du tracé visible
zones_interdites = [[0, 0, W, 125], [W - 200, 130, W, 330], [W - 1050, 340, W, 800]]
occupe += zones_interdites
for l in lignes:
    segs = sorted(l['draw'], key=lambda c: -LineString(c).length)
    txt = l['nom'].replace('Express ', 'Exp. ')
    tw = d.textlength(txt, font=f_num); bw = tw + 30; bh = 58
    place = False
    for c in segs:
        ls = LineString(c)
        for frac in (0.5, 0.3, 0.7, 0.15, 0.85, 0.4, 0.6):
            p = ls.interpolate(frac, normalized=True)
            r = [p.x - bw / 2, p.y - bh / 2, p.x + bw / 2, p.y + bh / 2]
            if r[0] > 10 and r[2] < W - 10 and r[1] > 130 and r[3] < H - 10 and libre(r):
                tc = (0, 0, 0) if sum(l['col']) > 380 else (255, 255, 255)
                d.rounded_rectangle(r, radius=12, fill=l['col'], outline=(15, 15, 15), width=4)
                d.text((r[0] + 15, r[1] + 7), txt, font=f_num, fill=tc)
                occupe.append([r[0] - 30, r[1] - 30, r[2] + 30, r[3] + 30]); place = True
                break
        if place: break

# --- Habillage ---------------------------------------------------------------
d.rectangle([0, 0, W, 120], fill=(20, 20, 20))
d.text((40, 24), "Quartier des Cormiers et des Hauts-Bâtons — écoles et lignes de bus", font=f_tit, fill=(255, 255, 255))
# légende
lh = 52
lw = 40 + max(d.textlength(f"Ligne {l['nom']}  ({l['op']})", font=f_leg) for l in lignes) + 110
lx, ly = W - lw - 40, 360
d.rounded_rectangle([lx, ly, lx + lw, ly + 110 + lh * (len(lignes) + 2)], radius=16, fill=(20, 20, 20, 235))
d.text((lx + 25, ly + 18), "Lignes de bus", font=f_lab, fill=(255, 255, 255))
for i, l in enumerate(lignes):
    y = ly + 95 + i * lh
    d.line([(lx + 25, y + 20), (lx + 95, y + 20)], fill=l['col'], width=12)
    d.text((lx + 115, y), f"Ligne {l['nom']}  ({l['op']})", font=f_leg, fill=(255, 255, 255))
y = ly + 95 + len(lignes) * lh
d.rectangle([lx + 30, y + 4, lx + 90, y + 36], fill=(255, 255, 255, 120), outline=(255, 255, 255), width=5)
d.text((lx + 115, y), "Groupe scolaire", font=f_leg, fill=(255, 255, 255))
d.text((lx + 30, y + lh), "Ligne 213 : avenue au nord du quartier", font=ImageFont.truetype(N, 32), fill=(190, 190, 190))
# échelle
mpp = (bbox[2] - bbox[0]) * math.cos(math.radians(48.846)) / W; L = 200 / mpp
x0, y0 = 60, H - 130
d.rectangle([x0 - 25, y0 - 70, x0 + L + 25, y0 + 45], fill=(20, 20, 20))
d.rectangle([x0, y0, x0 + L, y0 + 14], fill=(255, 255, 255)); d.text((x0, y0 - 55), "200 m", font=f_src, fill=(255, 255, 255))
# nord
nx, ny = W - 110, 230
d.ellipse([nx - 65, ny - 65, nx + 65, ny + 65], fill=(20, 20, 20))
d.polygon([(nx, ny - 48), (nx - 24, ny + 26), (nx, ny + 10), (nx + 24, ny + 26)], fill=(255, 255, 255))
d.text((nx - 12, ny + 20), "N", font=f_src, fill=(255, 255, 255))
src = "Sources : IGN (orthophotographie, BD TOPO) ; Île-de-France Mobilités (tracés des lignes de bus)"
tw = d.textlength(src, font=f_src)
d.rectangle([W - tw - 50, H - 64, W, H], fill=(20, 20, 20)); d.text((W - tw - 25, H - 54), src, font=f_src, fill=(255, 255, 255))
img.convert('RGB').save('/home/user/Operation_robespierre/images/vue_aerienne_ecoles_et_bus_cormiers_hauts_batons.jpg', quality=90)
print([l['nom'] for l in lignes])
