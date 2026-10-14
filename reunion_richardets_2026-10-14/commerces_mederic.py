"""Commerces de l'avenue Médéric, d'après la base Sirene (données ouvertes de la Ville).

Source : jeu « sirene-v3-consolidee-noisy-le-grand » du portail opendata.noisylegrand.fr
(mise à jour du 15 août 2026). On ne garde que les établissements actifs qui tiennent une
boutique ou une salle ouverte au public : alimentation, restaurants et cafés, coiffure et
beauté, pharmacie, optique, vétérinaire, garage, station-service et autres boutiques.

Sont écartés : la vente à distance ou à domicile, les meublés de tourisme, les cabinets de
santé libéraux (comptés à part dans les notes), les domiciliations, et les anciens exploitants
d'un même local quand un nouvel établissement y a été créé depuis (EXCLUS ci-dessous).

Écrit commerces_mederic.csv et met en cache le tracé des rues autour de l'avenue (IGN, BD TOPO).

Usage : python3 commerces_mederic.py
"""
import csv
import json
import os
import urllib.parse
import urllib.request

ICI = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(ICI, ".cache")
SORTIE = os.path.join(ICI, "commerces_mederic.csv")
SIRENE = ("https://opendata.noisylegrand.fr/api/explore/v2.1/catalog/datasets/"
          "sirene-v3-consolidee-noisy-le-grand/exports/json?")
WFS = "https://data.geopf.fr/wfs/ows?"
EMPRISE = (2.554, 48.826, 2.582, 48.833)          # lon min, lat min, lon max, lat max

# Catégories de la diapositive, par code d'activité (NAF) : premier préfixe qui correspond
CATEGORIES = [
    ("Alimentation", ("10.71", "47.11", "47.2")),
    ("Restaurants et cafés", ("56.",)),
    ("Coiffure et beauté", ("96.02",)),
    ("Santé", ("47.73", "47.78A", "75.00")),
    ("Autres commerces", ("45.11", "45.20", "47.30", "47.5", "47.76", "47.78C")),
]

# Établissements actifs dans Sirene mais sans boutique propre sur l'avenue
EXCLUS = {
    "TAWLAWALTE",        # 78 : alimentation, remplacée par Médéric Supérette (2025)
    "LES RICHARDETS",    # 102 : débit de boissons, remplacé par Le 102 (2017)
    "ATLAS RETAIL",      # 150 B : sans salarié, local partagé avec un autre établissement
    "BODY GOLD",         # 150 B : idem
    "LIVIAAESTHETIC",    # 128 B : soins de beauté sans salarié, à domicile
    "AUTOEXELL", "A.Z", "VSM", "RJ AUTOPLUS",   # négoce automobile sans salarié, à domicile
}


def nom(r):
    return (r["enseigne1etablissement"] or r["denominationusuelleetablissement"]
            or r["denominationunitelegale"] or r["nomunitelegale"] or "").strip()


def categorie(code):
    for libelle, prefixes in CATEGORIES:
        if code.startswith(prefixes):
            return libelle
    return None


def telecharger(url, chemin):
    if not os.path.exists(chemin):
        os.makedirs(CACHE, exist_ok=True)
        urllib.request.urlretrieve(url, chemin)
    return json.load(open(chemin, encoding="utf-8"))


def main():
    sirene = telecharger(SIRENE + urllib.parse.urlencode({
        "where": 'libellevoieetablissement like "MEDERIC" and etatadministratifetablissement="Actif"'}),
        os.path.join(CACHE, "sirene_mederic_actifs.json"))
    lignes = []
    for r in sirene:
        cat = categorie(r["activiteprincipaleetablissement"] or "")
        if not cat or nom(r) in EXCLUS or not r["geolocetablissement"]:
            continue
        lignes.append({"numero": f'{r["numerovoieetablissement"]}{(" " + r["indicerepetitionetablissement"]) if r["indicerepetitionetablissement"] else ""}',
                       "nom": nom(r), "categorie": cat, "activite": r["classeetablissement"],
                       "longitude": r["geolocetablissement"]["lon"], "latitude": r["geolocetablissement"]["lat"],
                       "siret": r["siret"]})
    lignes.sort(key=lambda l: (int(l["numero"].split()[0]), l["nom"]))
    with open(SORTIE, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(lignes[0]))
        w.writeheader()
        w.writerows(lignes)
    print("Écrit :", SORTIE, "-", len(lignes), "commerces")
    for libelle, _ in CATEGORIES:
        print(f"  {libelle} : {sum(l['categorie'] == libelle for l in lignes)}")

    telecharger(WFS + urllib.parse.urlencode({
        "SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature", "TYPENAMES": "BDTOPO_V3:troncon_de_route",
        "OUTPUTFORMAT": "application/json", "COUNT": 5000,
        "BBOX": ",".join(map(str, EMPRISE)) + ",urn:ogc:def:crs:OGC:1.3:CRS84"}),
        os.path.join(CACHE, "routes_mederic.json"))


if __name__ == "__main__":
    main()
