"""Carte de la commune avec la localisation des praticiens de santé.

Source unique : fichier « Adresses Profes. Santé » transmis par le cabinet, feuille « 2026 »
(mise à jour du 1er août 2025 indiquée dans le fichier). Le fichier contient des données
personnelles (noms, téléphones, courriels) : il n'est pas versionné et seuls la profession et
l'adresse sont lues. Les adresses sont géocodées par le service de géocodage de l'IGN.

L'image ne porte aucun texte : la légende et les chiffres sont posés dans la diapositive.

Usage : python3 visuel_praticiens.py CHEMIN_DU_FICHIER.xlsx
"""
import json
import math
import os
import re
import subprocess
import sys
import time
import urllib.parse
from collections import Counter

import openpyxl
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps
from shapely.geometry import Point, shape
from shapely.ops import unary_union

from build_richardets import merc
from visuels_richardets import SECTEUR_REUNION, Vue, geojson, masque, pointilles

ICI = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(ICI, ".cache", "geocodage_praticiens.json")
SORTIE = os.path.join(ICI, "Visuels_Richardets", "Sante", "Sante_01_praticiens_ville.jpg")
GEOCODAGE = "https://data.geopf.fr/geocodage/search?limit=1&citycode=93051&q="

# Catégories de la carte (couleur des points). Les professions non listées ne sont pas des
# praticiens au sens retenu ici : commerces (pharmacies, opticiens, audioprothèse), établissements
# (EHPAD, hôpitaux, laboratoires, centres), ambulances, vétérinaires, pratiques non réglementées.
GENERALISTES = "Médecins généralistes"
SPECIALISTES = "Médecins spécialistes"
DENTISTES = "Chirurgiens-dentistes"
PARAMEDICAUX = "Autres professions de santé"
COULEURS = {GENERALISTES: (232, 72, 85), SPECIALISTES: (242, 140, 40),
            DENTISTES: (66, 165, 245), PARAMEDICAUX: (114, 196, 147)}


def categorie(profession):
    p = profession.lower()
    if p.startswith("médecin généraliste"):
        return GENERALISTES
    if p.startswith(("chirurgien dentiste", "orthodontiste")):
        return DENTISTES
    if p.startswith(("cardiologue", "allergologue", "chirurgien", "dermatologue", "endocrinologue",
                     "gastro", "gynécologue", "médecin hypnothérapeute", "neurologue", "ophtalmologue",
                     "pneumologie", "psychiatre", "pédiatre", "rhumatologue")):
        return SPECIALISTES
    if p.startswith(("infirmi", "masseur kinésithérapeute", "sage femme", "orthophoniste", "orthoptiste",
                     "pédicure podologue", "psychomotricienne", "ergothérapeute", "diététicien",
                     "psychologue", "neuropsychologue", "ostéopathe", "chiropracteur")):
        return PARAMEDICAUX
    return None


def lire(chemin):
    """Renvoie [(catégorie, adresse)] ; les soins à domicile sans cabinet sont écartés."""
    feuille = openpyxl.load_workbook(chemin, read_only=True, data_only=True)["2026"]
    retenus, ecartes = [], Counter()
    for ligne in feuille.iter_rows(min_row=2, values_only=True):
        profession, numero, voie = ligne[0], ligne[3], ligne[4]
        if not profession or not categorie(profession):
            continue
        voie = " ".join(str(voie or "").split())
        if not voie or "domicile" in voie.lower() or "distance" in voie.lower():
            ecartes["sans adresse de cabinet"] += 1
            continue
        voie = re.sub(r"^.*?(\d+\s)", r"\1", voie) if not numero else voie   # « Centre médical … 3 place … »
        voie = re.split(r"\s+-\s*|\s*-\s+", voie)[0]       # « … - Centre médical Galien » : nom du cabinet retiré
        retenus.append((categorie(profession), f"{numero or ''} {voie}".strip()))
    return retenus, ecartes


def geocoder(adresses):
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    for a in sorted(set(adresses) - set(cache)):
        for essai in range(6):
            r = subprocess.run(["curl", "-sS", "-m", "30",
                                GEOCODAGE + urllib.parse.quote(a + " 93160 Noisy-le-Grand")],
                               capture_output=True, text=True)
            try:
                f = json.loads(r.stdout)["features"]
                break
            except (ValueError, KeyError):
                time.sleep(1 + essai)
        else:
            raise RuntimeError(f"Géocodage impossible : {a}")
        cache[a] = (f[0]["geometry"]["coordinates"] + [f[0]["properties"]["score"], f[0]["properties"]["label"]]
                    if f else None)
        json.dump(cache, open(CACHE, "w"), ensure_ascii=False, indent=0)
    return cache


def carte(points, quartiers):
    """points : [(catégorie, lon, lat)]. Les praticiens d'une même adresse sont disposés en
    petite grappe autour du point, pour que chacun reste visible."""
    secteur = unary_union([quartiers[n] for n in SECTEUR_REUNION])
    ville = unary_union(list(quartiers.values()))
    (x0, y0), (x1, y1) = merc(*ville.bounds[:2]), merc(*ville.bounds[2:])
    largeur, hauteur = 2920, 2000          # format du cadre de la diapositive (10,2 x 7 pouces)
    w = max((x1 - x0) * 1.05, (y1 - y0) * 1.05 * largeur / hauteur)
    vue = Vue((x0 + x1) / 2, (y0 + y1) / 2, w, largeur, hauteur)
    photo = vue.photo(zoom_max=17)
    # commune en photo atténuée, extérieur en gris sombre, secteur de la réunion éclairci
    gris = ImageEnhance.Brightness(ImageOps.grayscale(photo).convert("RGB")).enhance(0.45)
    commune = ImageEnhance.Brightness(ImageEnhance.Color(photo).enhance(0.45)).enhance(0.6)
    img = Image.composite(commune, gris, masque(vue, ville).filter(ImageFilter.GaussianBlur(2)))
    vif = ImageEnhance.Color(ImageEnhance.Brightness(photo).enhance(1.12)).enhance(1.15)
    img = Image.composite(vif, img,
                          masque(vue, secteur).filter(ImageFilter.GaussianBlur(2))).convert("RGBA")
    d = ImageDraw.Draw(img)
    for a in vue.anneaux(ville):
        d.line(a + [a[0]], fill=(255, 255, 255, 170), width=5, joint="curve")
    for a in vue.anneaux(secteur):
        pointilles(d, a, (255, 255, 255, 255), 9, 34, 22)
    r = 22
    par_lieu = {}
    for cat, lon, lat in points:
        par_lieu.setdefault((round(lon, 5), round(lat, 5)), []).append(cat)
    ordre = list(COULEURS)
    ombre = Image.new("RGBA", img.size, (0, 0, 0, 0))
    do = ImageDraw.Draw(ombre)
    pastilles = []
    for (lon, lat), cats in par_lieu.items():
        cx, cy = vue.px(lon, lat)
        for k, cat in enumerate(sorted(cats, key=ordre.index)):
            # spirale de Vogel : grappe compacte et régulière
            rayon, angle = 2.15 * r * math.sqrt(k), k * 2.39996
            x, y = cx + rayon * math.cos(angle), cy + rayon * math.sin(angle)
            rr = r if cat != PARAMEDICAUX else round(r * 0.72)   # médecins et dentistes mis en avant
            pastilles.append((x, y, rr, COULEURS[cat]))
            do.ellipse([x - rr + 3, y - rr + 5, x + rr + 3, y + rr + 5], fill=(0, 0, 0, 140))
    img.alpha_composite(ombre.filter(ImageFilter.GaussianBlur(5)))
    d = ImageDraw.Draw(img)
    # les autres professions de santé d'abord, pour que médecins et dentistes restent au-dessus
    for x, y, rr, c in sorted(pastilles, key=lambda p: p[2]):
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=c + (255,), outline=(255, 255, 255, 255),
                  width=5 if rr == r else 3)
    os.makedirs(os.path.dirname(SORTIE), exist_ok=True)
    img.convert("RGB").save(SORTIE, quality=92)
    print("Écrit :", SORTIE)


def main(chemin):
    retenus, ecartes = lire(chemin)
    geo = geocoder([a for _, a in retenus])
    quartiers = {f["properties"]["nom_quarti"]: shape(f["geometry"]) for f in geojson("quartiers-de-noisy-le-grand")}
    secteur = unary_union([quartiers[n] for n in SECTEUR_REUNION])
    points, non_localises = [], []
    for cat, a in retenus:
        g = geo.get(a)
        if g is None or g[2] < 0.5:
            non_localises.append((cat, a, g))
            continue
        points.append((cat, g[0], g[1]))
    carte(points, quartiers)
    ville, dans_secteur = Counter(c for c, *_ in points), Counter(c for c, lon, lat in points
                                                                    if secteur.contains(Point(lon, lat)))
    print(f"\nPraticiens localisés : {len(points)} ; dans le secteur : {sum(dans_secteur.values())}")
    for c in COULEURS:
        print(f"  {c:30s} ville {ville[c]:4d}   secteur {dans_secteur[c]}")
    print("Écartés :", dict(ecartes), "; non localisés :", len(non_localises))
    for n in non_localises:
        print("   ", n)


if __name__ == "__main__":
    main(sys.argv[1])
