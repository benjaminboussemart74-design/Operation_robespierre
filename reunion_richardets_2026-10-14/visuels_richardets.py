"""Visuels du quartier des Richardets - Montfort, dans le style des réunions précédentes.

1. visuel_situation_richardets.jpg : la ville en photographie aérienne assombrie, le quartier
   en couleur, souligné d'un halo et d'un cartouche (modèle : visuel des Hauts-Bâtons).
2. visuel_richardets_vue_rapprochee.jpg : le quartier au format des diapositives (16/9), avec
   son contour et des repères sur les équipements (modèle : cartes de La Varenne).

Sources : contours des quartiers et établissements scolaires du portail de données ouvertes
de la Ville (opendata.noisylegrand.fr) ; orthophotographies IGN (BD ORTHO, Géoplateforme) ;
géocodage IGN pour la Maison pour tous.

Usage : python3 visuels_richardets.py
"""
import json
import math
import os
import urllib.request

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from shapely.geometry import Point, shape
from shapely.ops import unary_union

from build_richardets import CACHE, R, merc, tuile

ICI = os.path.dirname(os.path.abspath(__file__))
OPENDATA = "https://opendata.noisylegrand.fr/api/explore/v2.1/catalog/datasets/{}/exports/geojson"
CIBLE = "Les Richardets - Montfort"
TITRE = "Les Richardets – Montfort"

ACCENT = (232, 72, 85)          # rouge corail du visuel des Hauts-Bâtons
REPERE = (242, 140, 40)         # orange des repères des cartes de La Varenne
CARTOUCHE = (30, 32, 40)
ETIQUETTE = (27, 54, 93)        # bleu des étiquettes des cartes de La Varenne
GRAS = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
NORMAL = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
MENTION = "© IGN – BD ORTHO · Contours : Ville de Noisy-le-Grand"

# Repères de la vue rapprochée : (texte, lon, lat, côté de l'étiquette)
# Groupes scolaires : moyenne des points maternelle et élémentaire du fichier de la Ville.
MPT = (2.567482, 48.829731)     # 17, avenue Gabriel-Péri (géocodage IGN)

# Réunion publique du 14 octobre : secteur Richardets, Montfort, Charmilles et Yvris
SECTEUR_REUNION = ("Les Richardets - Montfort", "Les Yvris")
LIEU_REUNION = (2.575177, 48.833371)   # Victoria Park, 19, rue du Ballon (géocodage IGN)


def geojson(jeu):
    f = os.path.join(CACHE, jeu + ".geojson")
    if not os.path.exists(f):
        os.makedirs(CACHE, exist_ok=True)
        urllib.request.urlretrieve(OPENDATA.format(jeu), f)
    return json.load(open(f))["features"]


class Vue:
    """Emprise rectangulaire en Web Mercator, rendue sur largeur x hauteur pixels."""

    def __init__(self, cx, cy, w, largeur, hauteur):
        self.largeur, self.hauteur = largeur, hauteur
        self.w, self.h = w, w * hauteur / largeur
        self.x0, self.y1 = cx - self.w / 2, cy + self.h / 2

    def px(self, lon, lat):
        x, y = merc(lon, lat)
        return ((x - self.x0) / self.w * self.largeur, (self.y1 - y) / self.h * self.hauteur)

    def anneaux(self, g):
        for p in (g.geoms if g.geom_type == "MultiPolygon" else [g]):
            yield [self.px(*c) for c in p.exterior.coords]

    def photo(self, zoom_max=19):
        z = min(zoom_max, math.ceil(math.log2(2 * math.pi * R / 256 / (self.w / self.largeur))))
        taille = 2 * math.pi * R / 2 ** z
        tx0, tx1 = int((self.x0 + math.pi * R) // taille), int((self.x0 + self.w + math.pi * R) // taille)
        ty0 = int((math.pi * R - self.y1) // taille)
        ty1 = int((math.pi * R - (self.y1 - self.h)) // taille)
        from concurrent.futures import ThreadPoolExecutor
        tuiles = [(x, y) for x in range(tx0, tx1 + 1) for y in range(ty0, ty1 + 1)]
        mosaique = Image.new("RGB", ((tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256))
        with ThreadPoolExecutor(max_workers=12) as pool:
            for (x, y), f in zip(tuiles, pool.map(lambda t: tuile(z, *t), tuiles)):
                mosaique.paste(Image.open(f).convert("RGB"), ((x - tx0) * 256, (y - ty0) * 256))
        e = 256 / taille
        ox, oy = tx0 * taille - math.pi * R, math.pi * R - ty0 * taille
        boite = ((self.x0 - ox) * e, (oy - self.y1) * e, (self.x0 + self.w - ox) * e, (oy - self.y1 + self.h) * e)
        return mosaique.crop(tuple(round(v) for v in boite)).resize((self.largeur, self.hauteur), Image.LANCZOS)


def masque(vue, g, flou=0):
    m = Image.new("L", (vue.largeur, vue.hauteur), 0)
    d = ImageDraw.Draw(m)
    for a in vue.anneaux(g):
        d.polygon(a, fill=255)
    return m.filter(ImageFilter.GaussianBlur(flou)) if flou else m


def mention(img, taille, texte=MENTION):
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(NORMAL, taille)
    l, t, r, b = d.textbbox((0, 0), texte, font=f)
    x, y = img.width - (r - l) - taille * 1.6, img.height - (b - t) - taille * 1.4
    d.rectangle([x - taille * 0.5, y - taille * 0.4, x + (r - l) + taille * 0.5, y + (b - t) + taille * 0.6],
                fill=(20, 22, 30))
    d.text((x, y), texte, font=f, fill=(230, 230, 235))


def situation(quartiers, cible):
    """Ville entière en noir et blanc assombri, quartier en couleur avec halo et cartouche."""
    ville = unary_union(list(quartiers.values()))
    (x0, y0), (x1, y1) = merc(*ville.bounds[:2]), merc(*ville.bounds[2:])
    cote = max(x1 - x0, y1 - y0) * 1.08
    vue = Vue((x0 + x1) / 2, (y0 + y1) / 2, cote, 4000, 4000)
    photo = vue.photo(zoom_max=16)
    gris = ImageEnhance.Brightness(ImageOps.grayscale(photo).convert("RGB")).enhance(0.45)
    vif = ImageEnhance.Color(ImageEnhance.Contrast(photo).enhance(1.1)).enhance(1.25)
    m = masque(vue, cible)
    img = Image.composite(vif, gris, m).convert("RGBA")
    d = ImageDraw.Draw(img)
    for g in quartiers.values():
        for a in vue.anneaux(g):
            d.line(a + [a[0]], fill=(255, 255, 255, 90), width=3, joint="curve")
    for a in vue.anneaux(ville):
        d.line(a + [a[0]], fill=(255, 255, 255, 220), width=6, joint="curve")
    halo = Image.new("RGBA", m.size, ACCENT + (0,))
    halo.putalpha(m.filter(ImageFilter.GaussianBlur(24)).point(lambda v: int(v * 0.9) if v < 250 else 0))
    img = Image.alpha_composite(img, halo)
    d = ImageDraw.Draw(img)
    for a in vue.anneaux(cible):
        d.line(a + [a[0]], fill=ACCENT + (255,), width=14, joint="curve")
        d.line(a + [a[0]], fill=(255, 255, 255, 255), width=4, joint="curve")
    # cartouche relié au quartier, placé au-dessus à gauche (le sud-est de la ville est boisé)
    p = cible.representative_point()
    x, y = vue.px(p.x, p.y)
    f1, f2 = ImageFont.truetype(GRAS, 64), ImageFont.truetype(NORMAL, 40)
    l1, l2 = TITRE, "Réunion publique · mercredi 14 octobre 2026"
    w = max(d.textlength(l1, font=f1), d.textlength(l2, font=f2)) + 90
    hh = 175
    bx, by = x - w - 260, y - 620
    d.line([(x, y), (bx + w, by + hh / 2)], fill=(255, 255, 255, 230), width=5)
    d.ellipse([x - 14, y - 14, x + 14, y + 14], fill=(255, 255, 255), outline=CARTOUCHE, width=5)
    d.rounded_rectangle([bx, by, bx + w, by + hh], radius=24, fill=CARTOUCHE)
    d.rectangle([bx, by + 22, bx + 14, by + hh - 22], fill=ACCENT)
    d.text((bx + 48, by + 22), l1, font=f1, fill=(255, 255, 255))
    d.text((bx + 48, by + 108), l2, font=f2, fill=(200, 205, 215))
    img = img.convert("RGB")
    mention(img, 30)
    sortie = os.path.join(ICI, "visuel_situation_richardets.jpg")
    img.save(sortie, quality=90)
    print("Écrit :", sortie)


def etiquette(d, x, y, texte, f, cote):
    """Étiquette bleue à droite ou à gauche d'un repère, comme sur les cartes de La Varenne."""
    l, t, r, b = d.textbbox((0, 0), texte, font=f)
    tw, th, marge = r - l, b - t, 14
    bx = x + 40 if cote == "d" else x - 40 - tw - 2 * marge
    by = y - th / 2 - marge
    d.rounded_rectangle([bx, by, bx + tw + 2 * marge, by + th + 2 * marge], radius=8, fill=ETIQUETTE)
    d.text((bx + marge - l, by + marge - t), texte, font=f, fill=(255, 255, 255))


def vue_rapprochee(quartiers, cible, ecoles):
    """Le quartier au format 16/9, l'extérieur légèrement assombri, avec ses équipements."""
    (x0, y0), (x1, y1) = merc(*cible.bounds[:2]), merc(*cible.bounds[2:])
    largeur, hauteur = 1920, 1080
    w = max((x1 - x0) * 1.25, (y1 - y0) * 1.25 * largeur / hauteur)
    vue = Vue((x0 + x1) / 2, (y0 + y1) / 2, w, largeur, hauteur)
    photo = vue.photo()
    m = masque(vue, cible, flou=2)
    sombre = ImageEnhance.Brightness(ImageEnhance.Color(photo).enhance(0.6)).enhance(0.55)
    img = Image.composite(photo, sombre, m).convert("RGBA")
    d = ImageDraw.Draw(img)
    for a in vue.anneaux(cible):
        d.line(a + [a[0]], fill=ACCENT + (255,), width=9, joint="curve")
        d.line(a + [a[0]], fill=(255, 255, 255, 255), width=3, joint="curve")

    reperes = []
    for nom, cote in (("Richardets", "d"), ("Charmilles", "d")):
        pts = [e for e in ecoles if nom in e["properties"]["nom"]]
        lon = sum(e["properties"]["geo_point_2d"]["lon"] for e in pts) / len(pts)
        lat = sum(e["properties"]["geo_point_2d"]["lat"] for e in pts) / len(pts)
        reperes.append((f"Groupe scolaire Les {nom}", lon, lat, cote))
    reperes.append(("Maison pour tous des Richardets", *MPT, "g"))

    f = ImageFont.truetype(GRAS, 30)
    for texte, lon, lat, cote in reperes:
        x, y = vue.px(lon, lat)
        etiquette(d, x, y, texte, f, cote)
    for texte, lon, lat, cote in reperes:
        x, y = vue.px(lon, lat)
        d.ellipse([x - 22, y - 22, x + 22, y + 22], fill=REPERE, outline=(255, 255, 255), width=5)

    # nom du quartier, dans le style des cartes de La Varenne
    ft = ImageFont.truetype(GRAS, 54)
    texte = TITRE.upper()
    l, t, r, b = d.textbbox((0, 0), texte, font=ft)
    d.rounded_rectangle([60, 56, 60 + r - l + 56, 56 + b - t + 44], radius=10, fill=ETIQUETTE)
    d.text((88 - l, 78 - t), texte, font=ft, fill=(255, 255, 255))
    img = img.convert("RGB")
    mention(img, 18)
    sortie = os.path.join(ICI, "visuel_richardets_vue_rapprochee.jpg")
    img.save(sortie, quality=92)
    print("Écrit :", sortie)


def vue_reunion(quartiers, avec_etiquette):
    """Vue du ciel du secteur de la réunion, avec un seul point sur le lieu de la réunion."""
    secteur = unary_union([quartiers[n] for n in SECTEUR_REUNION])
    (x0, y0), (x1, y1) = merc(*secteur.bounds[:2]), merc(*secteur.bounds[2:])
    largeur, hauteur = 1920, 1080
    w = max((x1 - x0) * 1.22, (y1 - y0) * 1.22 * largeur / hauteur)
    vue = Vue((x0 + x1) / 2, (y0 + y1) / 2, w, largeur, hauteur)
    photo = vue.photo()
    # le secteur en couleur, l'extérieur assombri, et le contour extérieur du secteur
    sombre = ImageEnhance.Brightness(ImageEnhance.Color(photo).enhance(0.6)).enhance(0.55)
    img = Image.composite(photo, sombre, masque(vue, secteur, flou=2)).convert("RGBA")
    d = ImageDraw.Draw(img)
    for a in vue.anneaux(secteur):
        d.line(a + [a[0]], fill=ACCENT + (255,), width=9, joint="curve")
        d.line(a + [a[0]], fill=(255, 255, 255, 255), width=3, joint="curve")
    x, y = vue.px(*LIEU_REUNION)
    halo = Image.new("RGBA", img.size, REPERE + (0,))
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).ellipse([x - 60, y - 60, x + 60, y + 60], fill=170)
    halo.putalpha(m.filter(ImageFilter.GaussianBlur(22)))
    img = Image.alpha_composite(img, halo)
    d = ImageDraw.Draw(img)
    d.ellipse([x - 26, y - 26, x + 26, y + 26], fill=REPERE, outline=(255, 255, 255), width=7)
    if avec_etiquette:
        etiquette(d, x - 6, y, "Victoria Park – 19, rue du Ballon", ImageFont.truetype(GRAS, 32), "g")
    img = img.convert("RGB")
    mention(img, 18)
    suffixe = "" if avec_etiquette else "_sans_texte"
    sortie = os.path.join(ICI, f"visuel_lieu_reunion{suffixe}.jpg")
    img.save(sortie, quality=92)
    print("Écrit :", sortie)


# Lieux-dits du secteur de la réunion. Seuls deux quartiers ont un contour officiel ;
# les quatre noms sont donc placés sur leur toponyme (IGN) ou sur l'équipement qui le porte.
# (nom, lon, lat, décalage de l'étiquette en pixels)
LIEUX_DITS = (
    ("Montfort", 2.553361, 48.834092, (-560, 420)),        # toponyme IGN « le Montfort »
    ("Richardets", 2.568632, 48.831611, (-180, -560)),      # toponyme IGN « les Richardets »
    ("Charmilles", 2.575400, 48.832264, (620, -60)),       # groupe scolaire des Charmilles
    ("Yvris", 2.574137, 48.827381, (330, 380)),             # toponyme IGN « les Yvris »
)


def situation_secteur(quartiers):
    """La ville entière assombrie, le secteur de la réunion en couleur, les quatre noms placés."""
    secteur = unary_union([quartiers[n] for n in SECTEUR_REUNION])
    ville = unary_union(list(quartiers.values()))
    (x0, y0), (x1, y1) = merc(*ville.bounds[:2]), merc(*ville.bounds[2:])
    largeur, hauteur = 3840, 2160
    w = max((x1 - x0) * 1.06, (y1 - y0) * 1.06 * largeur / hauteur)
    vue = Vue((x0 + x1) / 2, (y0 + y1) / 2, w, largeur, hauteur)
    photo = vue.photo(zoom_max=16)
    gris = ImageEnhance.Brightness(ImageOps.grayscale(photo).convert("RGB")).enhance(0.42)
    vif = ImageEnhance.Color(ImageEnhance.Contrast(photo).enhance(1.1)).enhance(1.25)
    m = masque(vue, secteur)
    img = Image.composite(vif, gris, m).convert("RGBA")
    d = ImageDraw.Draw(img)
    for g in quartiers.values():
        for a in vue.anneaux(g):
            d.line(a + [a[0]], fill=(255, 255, 255, 80), width=3, joint="curve")
    for a in vue.anneaux(ville):
        d.line(a + [a[0]], fill=(255, 255, 255, 220), width=6, joint="curve")
    halo = Image.new("RGBA", m.size, ACCENT + (0,))
    halo.putalpha(m.filter(ImageFilter.GaussianBlur(14)).point(lambda v: int(v * 0.8) if v < 250 else 0))
    img = Image.alpha_composite(img, halo)
    d = ImageDraw.Draw(img)
    # limite entre les deux quartiers officiels, en pointillé discret
    for a in vue.anneaux(quartiers["Les Yvris"]):
        for i in range(0, len(a) - 1):
            if secteur.boundary.distance(Point(*_lonlat(vue, a[i]))) > 1e-5:
                d.line([a[i], a[i + 1]], fill=(255, 255, 255, 170), width=4)
    for a in vue.anneaux(secteur):
        d.line(a + [a[0]], fill=ACCENT + (255,), width=9, joint="curve")
        d.line(a + [a[0]], fill=(255, 255, 255, 255), width=3, joint="curve")

    # les quatre noms, reliés à leur emplacement
    f = ImageFont.truetype(GRAS, 64)
    for nom, lon, lat, (dx, dy) in LIEUX_DITS:
        x, y = vue.px(lon, lat)
        l, t, r, b = d.textbbox((0, 0), nom, font=f)
        tw, th = r - l, b - t
        bx, by = x + dx - (tw + 90) / 2, y + dy - (th + 56) / 2
        cx = min(max(x, bx), bx + tw + 90)
        cy = by + th + 56 if dy < 0 else by
        d.line([(x, y), (cx, cy)], fill=(255, 255, 255, 235), width=5)
        d.rounded_rectangle([bx, by, bx + tw + 90, by + th + 56], radius=18, fill=CARTOUCHE)
        d.rectangle([bx, by + 14, bx + 12, by + th + 42], fill=ACCENT)
        d.text((bx + 50 - l, by + 28 - t), nom, font=f, fill=(255, 255, 255))
        d.ellipse([x - 15, y - 15, x + 15, y + 15], fill=(255, 255, 255), outline=CARTOUCHE, width=5)

    # titre, en haut à gauche
    f1, f2 = ImageFont.truetype(GRAS, 76), ImageFont.truetype(NORMAL, 46)
    l1 = "Richardets · Montfort · Charmilles · Yvris"
    l2 = "Réunion publique · mercredi 14 octobre 2026 · Victoria Park"
    w = max(d.textlength(l1, font=f1), d.textlength(l2, font=f2)) + 110
    d.rounded_rectangle([90, 90, 90 + w, 90 + 215], radius=26, fill=CARTOUCHE)
    d.rectangle([90, 114, 106, 281], fill=ACCENT)
    d.text((150, 114), l1, font=f1, fill=(255, 255, 255))
    d.text((150, 214), l2, font=f2, fill=(200, 205, 215))
    img = img.convert("RGB")
    mention(img, 30)
    sortie = os.path.join(ICI, "visuel_situation_secteur_reunion.jpg")
    img.save(sortie, quality=90)
    print("Écrit :", sortie)


SYNE = os.path.join(ICI, "polices", "Syne.ttf")   # police de la charte (SIL Open Font License)
NUIT = (14, 31, 91)              # bleu nuit de la présentation (#0E1F5B)
VERT = (114, 196, 147)           # vert de la présentation (#72C493)


def syne(taille, graisse="ExtraBold"):
    f = ImageFont.truetype(SYNE, taille)
    f.set_variation_by_name(graisse)
    return f


def visuel_reunion_epure(quartiers):
    """La ville en bleu nuit, seuls les quartiers de la réunion en couleur, et le lieu écrit."""
    secteur = unary_union([quartiers[n] for n in SECTEUR_REUNION])
    ville = unary_union(list(quartiers.values()))
    (x0, y0), (x1, y1) = merc(*ville.bounds[:2]), merc(*ville.bounds[2:])
    largeur, hauteur = 3840, 2160
    w = max((x1 - x0) * 1.06, (y1 - y0) * 1.06 * largeur / hauteur)
    vue = Vue((x0 + x1) / 2 + (x1 - x0) * 0.22, (y0 + y1) / 2, w, largeur, hauteur)
    photo = vue.photo(zoom_max=16)

    # fond : photographie virée en bleu nuit, la commune un peu plus claire que ses abords
    gris = ImageOps.autocontrast(ImageOps.grayscale(photo), cutoff=1)
    teinte = ImageOps.colorize(gris, black=(4, 10, 34), white=(120, 136, 190), mid=NUIT)
    commune = masque(vue, ville, flou=6)
    fond = Image.composite(ImageEnhance.Brightness(teinte).enhance(0.85), ImageEnhance.Brightness(teinte).enhance(0.6), commune)
    # quartiers de la réunion : couleurs naturelles, légèrement avivées
    vif = ImageEnhance.Color(ImageEnhance.Contrast(photo).enhance(1.08)).enhance(1.2)
    m = masque(vue, secteur, flou=1)
    img = Image.composite(vif, fond, m).convert("RGBA")

    lueur = Image.new("RGBA", img.size, VERT + (0,))
    net = masque(vue, secteur)
    flou = net.filter(ImageFilter.GaussianBlur(28))
    # la lueur ne s'étend qu'à l'extérieur du contour
    lueur.putalpha(Image.composite(Image.new("L", net.size, 0), flou.point(lambda v: int(v * 0.85)), net))
    img = Image.alpha_composite(img, lueur)
    d = ImageDraw.Draw(img)
    for a in vue.anneaux(ville):
        d.line(a + [a[0]], fill=(255, 255, 255, 70), width=3, joint="curve")
    for a in vue.anneaux(secteur):
        d.line(a + [a[0]], fill=(255, 255, 255, 255), width=5, joint="curve")

    # point du lieu de la réunion, avec deux cercles concentriques
    x, y = vue.px(*LIEU_REUNION)
    for r, a in ((70, 70), (46, 130)):
        d.ellipse([x - r, y - r, x + r, y + r], outline=(255, 255, 255, a), width=4)
    d.ellipse([x - 24, y - 24, x + 24, y + 24], fill=VERT + (255,), outline=(255, 255, 255, 255), width=7)

    # le lieu, écrit en Syne, en haut à droite (hors de la ville), relié au point
    f0, f1, f2 = syne(40, "Bold"), syne(122), syne(58, "Regular")
    tw = max(d.textlength("Victoria Park", font=f1), d.textlength("RÉUNION PUBLIQUE · 14 OCTOBRE · 19 H", font=f0))
    tx, ty = largeur - tw - 230, 360
    d.text((tx, ty), "RÉUNION PUBLIQUE · 14 OCTOBRE · 19 H", font=f0, fill=VERT + (255,))
    d.text((tx, ty + 70), "Victoria Park", font=f1, fill=(255, 255, 255, 255))
    d.text((tx, ty + 230), "19, rue du Ballon", font=f2, fill=(225, 230, 240, 255))
    d.rectangle([tx - 56, ty + 6, tx - 44, ty + 300], fill=VERT + (255,))
    d.line([(tx - 50, ty + 300), (x + 50, y - 50)], fill=(255, 255, 255, 210), width=4)

    img = img.convert("RGB")
    mention(img, 28)
    sortie = os.path.join(ICI, "visuel_reunion_epure.jpg")
    img.save(sortie, quality=92)
    print("Écrit :", sortie)


EPINGLE = (226, 59, 75)          # rouge de l'épingle


def pointilles(d, anneau, couleur, largeur, trait=46, espace=28):
    """Trace un contour fermé en pointillés réguliers."""
    pts = anneau + [anneau[0]]
    reste, dessine = trait, True
    for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
        lg = math.hypot(xb - xa, yb - ya)
        pos = 0
        while pos < lg:
            pas = min(reste, lg - pos)
            if dessine:
                t0, t1 = pos / lg, (pos + pas) / lg
                d.line([(xa + (xb - xa) * t0, ya + (yb - ya) * t0), (xa + (xb - xa) * t1, ya + (yb - ya) * t1)],
                       fill=couleur, width=largeur)
            pos += pas
            reste -= pas
            if reste <= 0:
                dessine = not dessine
                reste = trait if dessine else espace


def epingle(img, x, y, h):
    """Épingle de carte dont la pointe est en (x, y), de hauteur h, avec ombre portée."""
    r = h * 0.36
    cx, cy = x, y - h + r
    ombre = Image.new("RGBA", img.size, (0, 0, 0, 0))
    do = ImageDraw.Draw(ombre)
    do.ellipse([x - r * 0.9, y - r * 0.22, x + r * 0.9, y + r * 0.22], fill=(0, 0, 0, 120))
    do.ellipse([cx - r + 10, cy - r + 14, cx + r + 10, cy + r + 14], fill=(0, 0, 0, 90))
    do.polygon([(cx - r * 0.86 + 10, cy + r * 0.5 + 14), (cx + r * 0.86 + 10, cy + r * 0.5 + 14), (x + 10, y + 14)],
               fill=(0, 0, 0, 90))
    img.alpha_composite(ombre.filter(ImageFilter.GaussianBlur(h * 0.06)))
    d = ImageDraw.Draw(img)
    d.polygon([(cx - r * 0.86, cy + r * 0.5), (cx + r * 0.86, cy + r * 0.5), (x, y)], fill=EPINGLE + (255,))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=EPINGLE + (255,))
    d.ellipse([cx - r * 0.42, cy - r * 0.42, cx + r * 0.42, cy + r * 0.42], fill=(255, 255, 255, 255))
    d.ellipse([cx - r * 0.2, cy - r * 0.2, cx + r * 0.2, cy + r * 0.2], fill=EPINGLE + (255,))


def visuel_epingle(quartiers, avec_texte):
    """Vue rapprochée : quartiers en couleur, extérieur en gris, contour en pointillés, épingle."""
    secteur = unary_union([quartiers[n] for n in SECTEUR_REUNION])
    (x0, y0), (x1, y1) = merc(*secteur.bounds[:2]), merc(*secteur.bounds[2:])
    largeur, hauteur = 3840, 2160
    w = max((x1 - x0) * 1.18, (y1 - y0) * 1.18 * largeur / hauteur)
    vue = Vue((x0 + x1) / 2, (y0 + y1) / 2, w, largeur, hauteur)
    photo = vue.photo()
    gris = ImageEnhance.Brightness(ImageOps.grayscale(photo).convert("RGB")).enhance(0.72)
    vif = ImageEnhance.Color(ImageEnhance.Contrast(photo).enhance(1.06)).enhance(1.15)
    net = masque(vue, secteur)
    img = Image.composite(vif, gris, net.filter(ImageFilter.GaussianBlur(2))).convert("RGBA")
    # lueur blanche à l'extérieur du contour
    flou = net.filter(ImageFilter.GaussianBlur(34))
    lueur = Image.new("RGBA", img.size, (255, 255, 255, 0))
    lueur.putalpha(Image.composite(Image.new("L", net.size, 0), flou.point(lambda v: int(v * 0.8)), net))
    img = Image.alpha_composite(img, lueur)
    d = ImageDraw.Draw(img)
    for a in vue.anneaux(secteur):
        pointilles(d, a, (255, 255, 255, 255), 9)
    x, y = vue.px(*LIEU_REUNION)
    epingle(img, x, y, 230)
    if avec_texte:
        d = ImageDraw.Draw(img)
        f1, f2 = syne(76), syne(48, "Regular")
        bx, by = x + 150, y - 250
        l1, l2 = "Victoria Park", "19, rue du Ballon"
        tw = max(d.textlength(l1, font=f1), d.textlength(l2, font=f2))
        d.rounded_rectangle([bx, by, bx + tw + 100, by + 190], radius=22, fill=(255, 255, 255, 240))
        d.text((bx + 50, by + 26), l1, font=f1, fill=NUIT + (255,))
        d.text((bx + 50, by + 118), l2, font=f2, fill=(70, 80, 110, 255))
    img = img.convert("RGB")
    mention(img, 26)
    sortie = os.path.join(ICI, "visuel_epingle{}.jpg".format("" if avec_texte else "_sans_texte"))
    img.save(sortie, quality=92)
    print("Écrit :", sortie)


def _lonlat(vue, p):
    """Inverse de vue.px : pixel vers (lon, lat)."""
    x = vue.x0 + p[0] / vue.largeur * vue.w
    y = vue.y1 - p[1] / vue.hauteur * vue.h
    return math.degrees(x / R), math.degrees(2 * math.atan(math.exp(y / R)) - math.pi / 2)


if __name__ == "__main__":
    quartiers = {q["properties"]["nom_quarti"]: shape(q["geometry"]) for q in geojson("quartiers-de-noisy-le-grand")}
    cible = quartiers[CIBLE]
    ecoles = [e for e in geojson("etablissements-scolaire")
              if cible.contains(Point(e["properties"]["geo_point_2d"]["lon"], e["properties"]["geo_point_2d"]["lat"]))]
    situation_secteur(quartiers)
    vue_reunion(quartiers, avec_etiquette=True)
    vue_reunion(quartiers, avec_etiquette=False)
    vue_rapprochee(quartiers, cible, ecoles)
    situation(quartiers, cible)
