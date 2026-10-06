#!/usr/bin/env python3
"""Cartes en vue aérienne pour la réunion publique de La Varenne (Noisy-le-Grand, 8 octobre 2026).

Fond : orthophotographies IGN (Géoplateforme, WMTS, couche ORTHOIMAGERY.ORTHOPHOTOS,
grille PM_0_19). Tracés : BD TOPO (rues, bâtiments) et Parcellaire Express (parcelles)
de l'IGN, interrogés en WFS sur la même Géoplateforme. Arrêts de bus : données ouvertes
d'Île-de-France Mobilités. Toutes ces données sont sous licence ouverte Etalab.

Usage :
    python3 cartes_varenne.py            # produit les huit cartes dans cartes_varenne/
    python3 cartes_varenne.py --travail  # produit les vues de travail (numéros de bâtiments)
"""
import io
import json
import math
import os
import subprocess
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# PARAMÈTRES (à remplacer par ceux de la charte graphique)
# ---------------------------------------------------------------------------
LARGEUR, HAUTEUR = 1920, 1080          # taille des images produites, en pixels
COULEUR_CONTOUR = "#F28C28"            # contours (bâtiments, lot, parcelles)
EPAISSEUR_CONTOUR = 6                  # épaisseur des contours, en pixels
COULEUR_CONTOUR_2 = "#FFFFFF"          # second contour (parcelle des Restos du Cœur)
COULEUR_TRACE = "#F28C28"              # rues surlignées
EPAISSEUR_TRACE = 12                   # épaisseur des rues surlignées
COULEUR_TRACE_2 = "#FFD166"            # contre-allée de la rue de Verdun
COULEUR_ETIQUETTE_FOND = (31, 58, 95)  # #1F3A5F
OPACITE_ETIQUETTE = 215                # 0 = transparent, 255 = opaque
COULEUR_ETIQUETTE_TEXTE = "#FFFFFF"
POLICE = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
TAILLE_TEXTE = 38                      # taille des étiquettes, en pixels (36 au minimum)
TAILLE_SOURCE = 24                     # taille de la mention de source
MENTION_SOURCE = "© IGN – BD ORTHO"
COULEUR_REPERE = "#F28C28"             # repères ronds (MPT, école, arrêts)
RAYON_REPERE = 30
ASSOMBRIR_FOND = 0.92                  # 1 = photo d'origine ; < 1 assombrit pour faire ressortir les annotations
ZOOM_MAX = 19                          # niveau WMTS le plus fin utilisé (0,3 m par pixel environ)

WMTS = ("https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0"
        "&LAYER=ORTHOIMAGERY.ORTHOPHOTOS&STYLE=normal&TILEMATRIXSET=PM_0_19"
        "&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&FORMAT=image/jpeg")
ICI = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(ICI, ".cache")
DONNEES = os.path.join(ICI, "donnees")

# ---------------------------------------------------------------------------
# Outils géographiques (Web Mercator)
# ---------------------------------------------------------------------------
R = 6378137.0


def merc(lon, lat):
    return (math.radians(lon) * R, math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * R)


def lonlat(x, y):
    return (math.degrees(x / R), math.degrees(2 * math.atan(math.exp(y / R)) - math.pi / 2))


def curl(url, binaire=False, essais=5):
    for i in range(essais):
        r = subprocess.run(["curl", "-sS", "-m", "60", url], capture_output=True)
        if r.returncode == 0 and r.stdout:
            return r.stdout if binaire else r.stdout.decode("utf-8")
        time.sleep(1 + i)
    raise RuntimeError("Téléchargement impossible : " + url)


class Vue:
    """Une emprise centrée sur (lon, lat), de largeur `largeur_m` mètres au sol."""

    def __init__(self, lon, lat, largeur_m):
        self.cx, self.cy = merc(lon, lat)
        k = 1 / math.cos(math.radians(lat))           # facteur d'échelle de Mercator
        self.w = largeur_m * k
        self.h = self.w * HAUTEUR / LARGEUR
        self.x0, self.y1 = self.cx - self.w / 2, self.cy + self.h / 2

    def px(self, lon, lat):
        x, y = merc(lon, lat)
        return ((x - self.x0) / self.w * LARGEUR, (self.y1 - y) / self.h * HAUTEUR)

    def fond(self):
        """Télécharge les tuiles WMTS, les assemble et recadre exactement sur l'emprise."""
        res_voulue = self.w / LARGEUR                  # mètres Mercator par pixel de sortie
        z = min(ZOOM_MAX, max(0, math.ceil(math.log2(2 * math.pi * R / 256 / res_voulue))))
        n = 2 ** z
        taille = 2 * math.pi * R / n                   # taille d'une tuile, en mètres Mercator
        tx0 = int((self.x0 + math.pi * R) // taille)
        tx1 = int((self.x0 + self.w + math.pi * R) // taille)
        ty0 = int((math.pi * R - self.y1) // taille)
        ty1 = int((math.pi * R - (self.y1 - self.h)) // taille)
        os.makedirs(CACHE, exist_ok=True)
        mosaique = Image.new("RGB", ((tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256))
        tuiles = [(tx, ty) for tx in range(tx0, tx1 + 1) for ty in range(ty0, ty1 + 1)]

        def telecharger(t):
            f = os.path.join(CACHE, f"{z}_{t[0]}_{t[1]}.jpg")
            for essai in range(8):
                if os.path.exists(f):
                    break
                donnees = curl(WMTS.format(z=z, x=t[0], y=t[1]), binaire=True)
                if donnees[:3] == b"\xff\xd8\xff":      # vraie image JPEG, pas un message d'erreur
                    open(f + ".tmp", "wb").write(donnees)
                    os.replace(f + ".tmp", f)
                else:
                    time.sleep(1 + essai)
            else:
                raise RuntimeError(f"Tuile {z}/{t[0]}/{t[1]} indisponible")
            return t, f

        with ThreadPoolExecutor(max_workers=12) as pool:
            for (tx, ty), f in pool.map(telecharger, tuiles):
                mosaique.paste(Image.open(f).convert("RGB"), ((tx - tx0) * 256, (ty - ty0) * 256))
        ox = tx0 * taille - math.pi * R
        oy = math.pi * R - ty0 * taille
        echelle = 256 / taille
        boite = ((self.x0 - ox) * echelle, (oy - self.y1) * echelle,
                 (self.x0 + self.w - ox) * echelle, (oy - self.y1 + self.h) * echelle)
        img = mosaique.crop(tuple(int(round(v)) for v in boite)).resize((LARGEUR, HAUTEUR), Image.LANCZOS)
        if ASSOMBRIR_FOND != 1:
            img = Image.eval(img, lambda v: int(v * ASSOMBRIR_FOND))
        return img


# ---------------------------------------------------------------------------
# Données vectorielles (IGN)
# ---------------------------------------------------------------------------
WFS = ("https://data.geopf.fr/wfs/ows?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature"
       "&TYPENAMES={couche}&SRSNAME=EPSG:4326&OUTPUTFORMAT=application/json"
       "&BBOX={bbox},CRS:84&COUNT=5000")


def wfs(nom, couche, bbox):
    os.makedirs(DONNEES, exist_ok=True)
    f = os.path.join(DONNEES, nom + ".json")
    if not os.path.exists(f):
        open(f, "w").write(curl(WFS.format(couche=couche, bbox=bbox)))
    return json.load(open(f))["features"]


def anneaux(geom):
    """Contours extérieurs d'un (multi)polygone, en listes de (lon, lat)."""
    if geom["type"] == "Polygon":
        return [[tuple(p[:2]) for p in geom["coordinates"][0]]]
    return [[tuple(p[:2]) for p in poly[0]] for poly in geom["coordinates"]]


def lignes(geom):
    if geom["type"] == "LineString":
        return [[tuple(p[:2]) for p in geom["coordinates"]]]
    return [[tuple(p[:2]) for p in l] for l in geom["coordinates"]]


def nom_voie(f):
    p = f["properties"]
    return p.get("nom_voie_ban_gauche") or p.get("nom_collaboratif_gauche") or ""


def centre(anneau):
    return (sum(p[0] for p in anneau) / len(anneau), sum(p[1] for p in anneau) / len(anneau))


# ---------------------------------------------------------------------------
# Géocodage (Géoplateforme) et arrêts (Île-de-France Mobilités)
# ---------------------------------------------------------------------------
def geocode(q, index="address", postcode="93160"):
    u = ("https://data.geopf.fr/geocodage/search?" +
         urllib.parse.urlencode({"q": q, "index": index, "limit": 1, "postcode": postcode}))
    f = json.loads(curl(u))["features"]
    if not f:
        raise SystemExit(f"Introuvable : {q}. Arrêt du script : précisez l'emplacement.")
    p, c = f[0]["properties"], f[0]["geometry"]["coordinates"]
    libelle = p.get("label") or p.get("name")
    print(f"  géocodage « {q} » -> {libelle} | type {p.get('type') or p.get('category')} "
          f"| score {p.get('score', 0):.2f} | {c[1]:.6f}, {c[0]:.6f}")
    return c[0], c[1], p


# ---------------------------------------------------------------------------
# Dessin
# ---------------------------------------------------------------------------
def police(t):
    return ImageFont.truetype(POLICE, t)


def calque(img):
    return Image.new("RGBA", img.size, (0, 0, 0, 0))


def etiquette(d, xy, texte, ancre="mm", taille=TAILLE_TEXTE, marge=14):
    f = police(taille)
    l, t, r, b = d.textbbox(xy, texte, font=f, anchor=ancre)
    d.rounded_rectangle((l - marge, t - marge, r + marge, b + marge), radius=10,
                        fill=COULEUR_ETIQUETTE_FOND + (OPACITE_ETIQUETTE,))
    d.text(xy, texte, font=f, fill=COULEUR_ETIQUETTE_TEXTE, anchor=ancre)
    return (l - marge, t - marge, r + marge, b + marge)


def contour(d, vue, anneau, couleur=COULEUR_CONTOUR, ep=EPAISSEUR_CONTOUR):
    pts = [vue.px(*p) for p in anneau]
    d.line(pts + [pts[0]], fill=couleur, width=ep, joint="curve")


def trace(d, vue, ligne, couleur=COULEUR_TRACE, ep=EPAISSEUR_TRACE):
    pts = [vue.px(*p) for p in ligne]
    d.line(pts, fill=(255, 255, 255, 230), width=ep + 6, joint="curve")
    d.line(pts, fill=couleur, width=ep, joint="curve")


def repere(d, vue, lon, lat, texte=None, couleur=COULEUR_REPERE, rayon=RAYON_REPERE):
    x, y = vue.px(lon, lat)
    d.ellipse((x - rayon, y - rayon, x + rayon, y + rayon), fill=couleur, outline="white", width=5)
    if texte:
        d.text((x, y), texte, font=police(int(rayon * 1.2)), fill="white", anchor="mm")
    return x, y


def source(d):
    etiquette(d, (LARGEUR - 24, HAUTEUR - 22), MENTION_SOURCE, ancre="rs", taille=TAILLE_SOURCE, marge=10)


def enregistrer(img, couche, nom):
    sortie = os.path.join(ICI, nom)
    Image.alpha_composite(img.convert("RGBA"), couche).convert("RGB").save(sortie, optimize=True)
    print("  ->", sortie)


# ---------------------------------------------------------------------------
# Vues de travail : numéros des bâtiments BD TOPO, pour repérer MPT et école
# ---------------------------------------------------------------------------
def vues_de_travail(bati):
    lon, lat, _ = geocode("16 rue de Verdun")
    vue = Vue(lon + 0.0004, lat - 0.0002, 260)
    img = vue.fond()
    c = calque(img)
    d = ImageDraw.Draw(c)
    for i, f in enumerate(bati):
        for a in anneaux(f["geometry"]):
            pts = [vue.px(*p) for p in a]
            if not any(0 < x < LARGEUR and 0 < y < HAUTEUR for x, y in pts):
                continue
            d.line(pts + [pts[0]], fill=(0, 255, 255, 255), width=2)
            x, y = vue.px(*centre(a))
            d.text((x, y), str(i), font=police(20), fill="yellow", anchor="mm", stroke_width=3, stroke_fill="black")
    repere(d, vue, lon, lat, rayon=10)
    enregistrer(img, c, "travail_verdun.png")


# ---------------------------------------------------------------------------
# Éléments identifiés (voir le compte rendu de contrôle)
# ---------------------------------------------------------------------------
# MPT Varenne : bâtiment BD TOPO situé entre le groupe scolaire et le parc de la Varenne
# (le « 14 rue de Verdun » n'existe pas dans la Base Adresse Nationale).
POINT_MPT = (2.534489, 48.846544)
# Lot M7 : parcelles cadastrales du 42 au 54 rue Pierre-Brossolette (plan SOCAREN).
PARCELLES_M7 = ["AW0601", "AW0602", "AW0603", "AW0604", "AW0625", "AW0627", "AW0053",
                "AW0054", "AW0629", "AW0657", "AW0631", "AW0633", "AW0064", "AW0065"]
# Future parcelle des Restos du Cœur, dans un repère aligné sur la rue (origine : n° 42,
# axe : du n° 42 vers le n° 54), en mètres : le long de la rue, puis vers l'intérieur de l'îlot.
RESTOS_LE_LONG = (30.1, 70.0)
RESTOS_PROFONDEUR = (-31.3, 5.0)
# Contre-allée de la rue de Verdun : tronçon BD TOPO sans nom, parallèle à la rue, côté est.
CONTRE_ALLEE = "TRONROUT0000002341984611"
# Arrêts de bus (données ouvertes Île-de-France Mobilités, poteaux moyennés par ligne)
ARRETS = [
    ("1", "Verdun", [(2.532180, 48.846752), (2.532288, 48.846906)]),
    ("2", "Route de Neuilly (220)", [(2.537442, 48.848005), (2.539661, 48.846781)]),
    ("2", "Route de Neuilly (303)", [(2.540601, 48.848260), (2.540638, 48.847154)]),
    ("3", "Marx Dormoy – Carnot", [(2.528417, 48.845452), (2.528567, 48.845425)]),
    ("4", "René Navier", [(2.535102, 48.850604), (2.535389, 48.850560)]),
    ("5", "Gare de Bry-sur-Marne", [(2.526291, 48.844257)]),
]
LEGENDE_BUS = ["1  Verdun", "2  Route de Neuilly (220 et 303)", "3  Marx Dormoy – Carnot",
               "4  René Navier", "5  Gare de Bry-sur-Marne"]


def portion_visible(vue, lignes_, marge=110):
    """Plus longue suite de points visibles (en pixels) parmi les tronçons d'une rue."""
    meilleure, longueur_max = [], 0
    for l in lignes_:
        pts = []
        # densifie pour que le découpage au bord du cadre reste précis
        for a, b in zip(l, l[1:]):
            pa, pb = vue.px(*a), vue.px(*b)
            n = max(1, int(math.dist(pa, pb) / 8))
            pts += [(pa[0] + (pb[0] - pa[0]) * i / n, pa[1] + (pb[1] - pa[1]) * i / n) for i in range(n)]
        pts.append(vue.px(*l[-1]))
        courant = []
        for p in pts + [(-1e9, -1e9)]:
            if marge < p[0] < LARGEUR - marge and marge < p[1] < HAUTEUR - marge:
                courant.append(p)
            else:
                lg = sum(math.dist(u, v) for u, v in zip(courant, courant[1:]))
                if lg > longueur_max:
                    meilleure, longueur_max = courant, lg
                courant = []
    return meilleure


def etiquette_rue(img_calque, vue, lignes_, texte, decalage=0, taille=TAILLE_TEXTE, position=0.5):
    """Étiquette posée sur une rue, dans l'axe de celle-ci (lisible de gauche à droite)."""
    pts = portion_visible(vue, lignes_)
    if len(pts) < 2:
        raise SystemExit(f"La rue « {texte} » n'est pas visible dans le cadre : revoir l'emprise.")
    longueurs = [0]
    for u, v in zip(pts, pts[1:]):
        longueurs.append(longueurs[-1] + math.dist(u, v))
    cible = longueurs[-1] * position
    i = next(j for j, lg in enumerate(longueurs) if lg >= cible)
    a, b = pts[max(0, i - 6)], pts[min(len(pts) - 1, i + 6)]
    angle = math.degrees(math.atan2(-(b[1] - a[1]), b[0] - a[0]))
    if angle > 90:
        angle -= 180
    if angle < -90:
        angle += 180
    f = police(taille)
    l, t, r, bb = ImageDraw.Draw(img_calque).textbbox((0, 0), texte, font=f)
    w, h = r - l + 36, bb - t + 28
    etq = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    de = ImageDraw.Draw(etq)
    de.rounded_rectangle((0, 0, w - 1, h - 1), radius=10, fill=COULEUR_ETIQUETTE_FOND + (OPACITE_ETIQUETTE,))
    de.text((w / 2, h / 2), texte, font=f, fill=COULEUR_ETIQUETTE_TEXTE, anchor="mm")
    etq = etq.rotate(angle, expand=True, resample=Image.BICUBIC)
    cx, cy = pts[i]
    rad = math.radians(angle)
    cx += -math.sin(rad) * decalage
    cy += -math.cos(rad) * decalage
    x0 = int(min(max(cx - etq.width / 2, 10), LARGEUR - etq.width - 10))
    y0 = int(min(max(cy - etq.height / 2, 10), HAUTEUR - etq.height - 70))
    img_calque.alpha_composite(etq, (x0, y0))


def dans_cadre(d, xy, texte, taille=TAILLE_TEXTE, marge=14):
    """Pose une étiquette centrée sur xy, en la ramenant à l'intérieur de l'image si besoin."""
    f = police(taille)
    l, t, r, b = d.textbbox((0, 0), texte, font=f, anchor="mm")
    x = min(max(xy[0], -l + marge + 20), LARGEUR - r - marge - 20)
    y = min(max(xy[1], -t + marge + 20), HAUTEUR - b - marge - 70)
    etiquette(d, (x, y), texte, ancre="mm", taille=taille, marge=marge)
    return x, y


def fleche(d, depart, arrivee, couleur="white", ep=5):
    d.line([depart, arrivee], fill=couleur, width=ep)
    r = 9
    d.ellipse((arrivee[0] - r, arrivee[1] - r, arrivee[0] + r, arrivee[1] + r), fill=couleur)


def troncons(routes, nom):
    return [l for f in routes if nom_voie(f) == nom for l in lignes(f["geometry"])]


def troncon_proche(routes, nom, lon, lat):
    """Tronçon d'une rue dont le milieu est le plus proche d'un point donné (pour poser une étiquette)."""
    proches = [l for l in troncons(routes, nom) if math.dist(l[len(l) // 2], (lon, lat)) < 0.0008]
    if not proches:
        raise SystemExit(f"Aucun tronçon de « {nom} » près du point indiqué.")
    return [plus_long(proches)]   # le plus long des tronçons proches : évite les virages et bretelles


def plus_long(lignes_):
    def longueur(l):
        return sum(math.dist(merc(*a), merc(*b)) for a, b in zip(l, l[1:]))
    return max(lignes_, key=longueur)


def chaine(lignes_):
    """Assemble des tronçons bout à bout en une seule ligne (pour poser une étiquette)."""
    restants = [list(l) for l in lignes_]
    ligne = restants.pop(0)
    progres = True
    while restants and progres:
        progres = False
        for l in restants:
            for cand, inv_debut in ((l, False), (l[::-1], True)):
                if math.dist(cand[0], ligne[-1]) < 1e-5:
                    ligne += cand[1:]
                elif math.dist(cand[-1], ligne[0]) < 1e-5:
                    ligne = cand[:-1] + ligne
                else:
                    continue
                restants.remove(l)
                progres = True
                break
            if progres:
                break
    return ligne


def repere_etiquete(d, vue, lon, lat, texte, cote="droite"):
    x, y = repere(d, vue, lon, lat)
    if cote == "droite":
        etiquette(d, (x + RAYON_REPERE + 26, y), texte, ancre="lm")
    elif cote == "gauche":
        etiquette(d, (x - RAYON_REPERE - 26, y), texte, ancre="rm")
    elif cote == "haut":
        etiquette(d, (x, y - RAYON_REPERE - 30), texte, ancre="ms")
    else:
        etiquette(d, (x, y + RAYON_REPERE + 30), texte, ancre="mt")


# ---------------------------------------------------------------------------
# Les huit cartes
# ---------------------------------------------------------------------------
def produire(brouillon=False):
    from shapely.geometry import Point, Polygon, box
    from shapely.ops import unary_union
    from shapely import affinity

    print("Géocodage et données de référence :")
    ecole_lon, ecole_lat, _ = geocode("16 rue de Verdun")
    bati = wfs("batiments", "BDTOPO_V3:batiment", "2.527,48.842,2.543,48.851")
    routes = wfs("routes", "BDTOPO_V3:troncon_de_route", "2.515,48.838,2.548,48.857")
    zones = wfs("zones_activite", "BDTOPO_V3:zone_d_activite_ou_d_interet", "2.528,48.843,2.540,48.851")
    parcelles = wfs("parcelles", "CADASTRALPARCELS.PARCELLAIRE_EXPRESS:parcelle", "2.5370,48.8455,2.5405,48.8478")

    # MPT : bâtiment contenant le point de référence
    mpt = next(a for f in bati for a in anneaux(f["geometry"]) if Polygon(a).contains(Point(POINT_MPT)))
    mpt_c = Polygon(mpt).centroid
    print(f"  MPT Varenne : bâtiment BD TOPO, centre {mpt_c.y:.6f}, {mpt_c.x:.6f}")
    # École : emprise « Groupe Scolaire Varenne » de la BD TOPO
    ecole = next(a for f in zones if f["properties"].get("toponyme") == "Groupe Scolaire Varenne"
                 for a in anneaux(f["geometry"]))
    ecole_c = Polygon(ecole).centroid
    print(f"  École de la Varenne : emprise BD TOPO, centre {ecole_c.y:.6f}, {ecole_c.x:.6f}")
    parc = next(a for f in zones if f["properties"].get("toponyme") == "Parc de la Varenne"
                for a in anneaux(f["geometry"]))
    quartier = (2.532200, 48.847853)   # toponyme « la Varenne » (géocodeur IGN, index POI)

    # Lot M7 : union des parcelles, en Mercator puis reconverti
    polys = [Polygon([merc(*p) for p in a]) for f in parcelles
             if f["properties"]["section"] + f["properties"]["numero"] in PARCELLES_M7
             for a in anneaux(f["geometry"])]
    lot_m = unary_union([p.buffer(1.5) for p in polys]).buffer(-1.5)
    if lot_m.geom_type != "Polygon":
        morceaux = sorted(lot_m.geoms, key=lambda g: g.area, reverse=True)
        if any(g.area > 5 for g in morceaux[1:]):   # plus de 5 m² isolés : anomalie réelle
            raise SystemExit("Les parcelles du lot M7 ne forment pas un ensemble continu : vérifier PARCELLES_M7.")
        lot_m = morceaux[0]                          # éclats de géométrie négligeables
    lot = [lonlat(x, y) for x, y in lot_m.exterior.coords]
    # Parcelle des Restos du Cœur : rectangle dans le repère de la rue, découpé par le lot
    a, b = merc(2.538604, 48.846488), merc(2.539368, 48.846694)
    ux, uy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(ux, uy)
    ux, uy = ux / n, uy / n
    k = 1 / math.cos(math.radians(48.8466))

    def depuis_repere(le_long, prof):
        return (a[0] + (le_long * ux - prof * uy) * k, a[1] + (le_long * uy + prof * ux) * k)
    l0, l1 = RESTOS_LE_LONG
    p0, p1 = RESTOS_PROFONDEUR
    rect = Polygon([depuis_repere(l0, p0), depuis_repere(l1, p0), depuis_repere(l1, p1), depuis_repere(l0, p1)])
    restos_m = rect.intersection(lot_m)
    restos = [lonlat(x, y) for x, y in restos_m.exterior.coords]
    print(f"  Lot M7 : {len(polys)} parcelles, {lot_m.area * math.cos(math.radians(48.8466)) ** 2:.0f} m² ; "
          f"parcelle des Restos du Cœur : {restos_m.area * math.cos(math.radians(48.8466)) ** 2:.0f} m²")
    brossolette = troncons(routes, "Rue Pierre Brossolette")

    suffixe = "_projet" if brouillon else ""

    # 1. Situation du quartier ------------------------------------------------
    print("Carte 1 – situation du quartier")
    vue = Vue(2.5318, 48.8472, 1150)
    img = vue.fond(); c = calque(img); d = ImageDraw.Draw(c)
    x, y = vue.px(*quartier)
    etiquette(d, (x - 120, y - 40), "LA VARENNE", taille=56, marge=18)
    repere_etiquete(d, vue, mpt_c.x, mpt_c.y, "MPT Varenne", "droite")
    repere_etiquete(d, vue, ecole_c.x, ecole_c.y + 0.00012, "École de la Varenne", "haut")
    source(d); enregistrer(img, c, "01_situation_quartier.png")

    # 2. MPT Varenne ----------------------------------------------------------
    print("Carte 2 – MPT Varenne")
    vue = Vue(mpt_c.x + 0.00005, mpt_c.y - 0.00012, 200)
    img = vue.fond(); c = calque(img); d = ImageDraw.Draw(c)
    contour(d, vue, mpt)
    x, y = vue.px(mpt_c.x, mpt_c.y)
    ex, ey = dans_cadre(d, (x - 420, y - 170), "MPT Varenne")
    fleche(d, (ex + 150, ey + 25), (x - 40, y - 20))
    pc = Polygon(parc).centroid
    px_, py_ = vue.px(pc.x, pc.y)
    dans_cadre(d, (px_ - 40, py_ + 60), "Parc de la Varenne", taille=TAILLE_TEXTE - 2)
    source(d); enregistrer(img, c, f"02_mpt{suffixe}.png")

    # 3. École de la Varenne --------------------------------------------------
    print("Carte 3 – École de la Varenne")
    vue = Vue(ecole_c.x, ecole_c.y - 0.0001, 300)
    img = vue.fond(); c = calque(img); d = ImageDraw.Draw(c)
    contour(d, vue, ecole)
    xs = [vue.px(*p)[0] for p in ecole]; ys = [vue.px(*p)[1] for p in ecole]
    etiquette(d, ((min(xs) + max(xs)) / 2, max(70, min(ys) - 40)), "École de la Varenne")
    source(d); enregistrer(img, c, "03_ecole.png")

    # 4. Lot M7 – Restos du Cœur ----------------------------------------------
    print("Carte 4 – Lot M7 – Restos du Cœur")
    lc = lot_m.centroid
    clon, clat = lonlat(lc.x, lc.y)
    vue = Vue(clon + 0.00025, clat + 0.0001, 240)
    img = vue.fond(); c = calque(img); d = ImageDraw.Draw(c)
    contour(d, vue, lot)
    contour(d, vue, restos, COULEUR_CONTOUR_2, EPAISSEUR_CONTOUR)
    xs = [vue.px(*p)[0] for p in lot]; ys = [vue.px(*p)[1] for p in lot]
    dans_cadre(d, (min(xs) + 110, (min(ys) + max(ys)) / 2 + 120), "Lot M7")
    rc = restos_m.centroid
    x, y = vue.px(*lonlat(rc.x, rc.y))
    bx = max(xs) + 60
    etiquette(d, (bx, y + 200), "Restos du Cœur –", ancre="lm")
    etiquette(d, (bx, y + 268), "futur local municipal", ancre="lm")
    fleche(d, (bx - 10, y + 200), (x + 40, y + 10))
    etiquette_rue(c, vue, brossolette, "Rue Pierre-Brossolette", decalage=0, position=0.3)
    d = ImageDraw.Draw(c)
    source(d); enregistrer(img, c, f"04_lot_m7_restos_du_coeur{suffixe}.png")

    # 5. Rue de Verdun --------------------------------------------------------
    print("Carte 5 – Rue de Verdun")
    verdun = troncons(routes, "Rue de Verdun")
    contre = [l for f in routes if f["properties"]["cleabs"] == CONTRE_ALLEE for l in lignes(f["geometry"])]
    vue = Vue(2.5296, 48.8480, 1000)
    img = vue.fond(); c = calque(img); d = ImageDraw.Draw(c)
    for l in verdun:
        trace(d, vue, l)
    for l in contre:
        trace(d, vue, l, COULEUR_TRACE_2, EPAISSEUR_TRACE - 4)
    etiquette_rue(c, vue, verdun, "Rue de Verdun", decalage=-58, position=0.3)
    x, y = vue.px(*contre[0][len(contre[0]) // 2])
    d = ImageDraw.Draw(c)
    ex, ey = dans_cadre(d, (x + 240, y - 110), "Contre-allée")
    fleche(d, (ex - 60, ey + 30), (x + 10, y - 6), COULEUR_TRACE_2)
    etiquette_rue(c, vue, troncon_proche(routes, "Rue de la Plaine", 2.5278, 48.8501), "Rue de la Plaine")
    etiquette_rue(c, vue, troncon_proche(routes, "Rue de la Passerelle", 2.5252, 48.8484), "Rue de la Passerelle")
    d = ImageDraw.Draw(c)
    source(d); enregistrer(img, c, "05_rue_de_verdun.png")

    # 6. Projet rue de la Plaine ----------------------------------------------
    print("Carte 6 – Projet rue de la Plaine")
    plaine = troncons(routes, "Rue de la Plaine")
    lon, lat, _ = geocode("rue de la Plaine")
    vue = Vue(lon, lat, 450)
    img = vue.fond(); c = calque(img)
    etiquette_rue(c, vue, plaine, "Rue de la Plaine", decalage=0)
    d = ImageDraw.Draw(c)
    source(d); enregistrer(img, c, "06_projet_rue_de_la_plaine.png")

    # 7. Plan de circulation ----------------------------------------------------
    print("Carte 7 – Plan de circulation")
    rues = [("Rue Marx Dormoy", "Rue Marx-Dormoy"), ("Rue Léo Lagrange", "Rue Léo-Lagrange"),
            ("Rue Carnot", "Rue Carnot"), ("Rue du 26 Aout 1944", "Rue du 26-Août-1944")]
    vue = Vue(2.5296, 48.8467, 560)
    img = vue.fond(); c = calque(img); d = ImageDraw.Draw(c)
    for nom, _ in rues:
        for l in troncons(routes, nom):
            trace(d, vue, l)
    for nom, libelle in rues:
        etiquette_rue(c, vue, troncons(routes, nom), libelle, decalage=0)
    d = ImageDraw.Draw(c)
    source(d); enregistrer(img, c, "07_plan_de_circulation.png")

    # 8. Bus -------------------------------------------------------------------
    print("Carte 8 – Bus")
    vue = Vue(2.5330, 48.84745, 1550)
    img = vue.fond(); c = calque(img); d = ImageDraw.Draw(c)
    for num, nom, poteaux in ARRETS:
        lon = sum(p[0] for p in poteaux) / len(poteaux)
        lat = sum(p[1] for p in poteaux) / len(poteaux)
        print(f"  arrêt {num} {nom} : {lat:.6f}, {lon:.6f}")
        repere(d, vue, lon, lat, num)
    f = police(TAILLE_TEXTE)
    lh = TAILLE_TEXTE + 22
    larg = max(d.textbbox((0, 0), t, font=f)[2] for t in LEGENDE_BUS) + 60
    x0, y0 = LARGEUR - larg - 40, HAUTEUR - 70 - lh * len(LEGENDE_BUS) - 40
    d.rounded_rectangle((x0, y0, x0 + larg, y0 + lh * len(LEGENDE_BUS) + 30), radius=14,
                        fill=COULEUR_ETIQUETTE_FOND + (OPACITE_ETIQUETTE,))
    for i, t in enumerate(LEGENDE_BUS):
        d.text((x0 + 30, y0 + 20 + i * lh), t, font=f, fill=COULEUR_ETIQUETTE_TEXTE)
    source(d); enregistrer(img, c, "08_bus.png")


if __name__ == "__main__":
    if "--travail" in sys.argv:
        vues_de_travail(wfs("batiments", "BDTOPO_V3:batiment", "2.527,48.842,2.543,48.851"))
    else:
        produire(brouillon="--projet" in sys.argv)
