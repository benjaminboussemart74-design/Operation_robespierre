"""Vues aériennes des parkings concernés par les zones bleues.

Points fournis par le cabinet : secteur du gymnase des Yvris (48°49'35.57" N, 2°35'00.63" E)
et boulevard du Champy (48°50'14.62" N, 2°34'48.08" E). Fond : orthophotographies IGN.
Les images ne portent aucun texte ; les légendes sont posées dans la diapositive.

Usage : python3 visuels_zones_bleues.py
"""
import math
import os

from PIL import Image, ImageEnhance

from build_richardets import merc
from visuels_richardets import Vue, epingle

ICI = os.path.dirname(os.path.abspath(__file__))
SORTIE = os.path.join(ICI, "Visuels_Richardets", "Securite")
YVRIS = (2 + 35 / 60 + 0.63 / 3600, 48 + 49 / 60 + 35.57 / 3600)
CHAMPY = (2 + 34 / 60 + 48.08 / 3600, 48 + 50 / 60 + 14.62 / 3600)


def vue(point, largeur_m, taille, nom, avec_epingle):
    lon, lat = point
    w, h = taille
    v = Vue(*merc(lon, lat), largeur_m / math.cos(math.radians(lat)), w, h)
    img = ImageEnhance.Contrast(v.photo(zoom_max=19)).enhance(1.05).convert("RGBA")
    if avec_epingle:
        x, y = v.px(lon, lat)
        epingle(img, x, y, int(h * 0.17))
    chemin = os.path.join(SORTIE, nom)
    img.convert("RGB").save(chemin, quality=92)
    print("Écrit :", chemin)


if __name__ == "__main__":
    os.makedirs(SORTIE, exist_ok=True)
    vue(YVRIS, 200, (2400, 1800), "Securite_03_zone_bleue_parking.jpg", avec_epingle=False)
    vue(YVRIS, 900, (1800, 1200), "Securite_04_zone_bleue_situation.jpg", avec_epingle=True)
    vue(CHAMPY, 200, (2400, 1800), "Securite_05_zone_bleue_parking_Champy.jpg", avec_epingle=False)
    vue(CHAMPY, 900, (1800, 1200), "Securite_06_zone_bleue_situation_Champy.jpg", avec_epingle=True)
