"""Vues aériennes du parking concerné par les zones bleues (secteur du gymnase des Yvris).

Point fourni par le cabinet : 48°49'35.57" N, 2°35'00.63" E. Fond : orthophotographies IGN.
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
LAT = 48 + 49 / 60 + 35.57 / 3600
LON = 2 + 35 / 60 + 0.63 / 3600


def vue(largeur_m, taille, nom, avec_epingle):
    w, h = taille
    v = Vue(*merc(LON, LAT), largeur_m / math.cos(math.radians(LAT)), w, h)
    img = ImageEnhance.Contrast(v.photo(zoom_max=19)).enhance(1.05).convert("RGBA")
    if avec_epingle:
        x, y = v.px(LON, LAT)
        epingle(img, x, y, int(h * 0.17))
    chemin = os.path.join(SORTIE, nom)
    img.convert("RGB").save(chemin, quality=92)
    print("Écrit :", chemin)


if __name__ == "__main__":
    os.makedirs(SORTIE, exist_ok=True)
    vue(200, (2400, 1600), "Securite_03_zone_bleue_parking.jpg", avec_epingle=False)
    vue(900, (1800, 1200), "Securite_04_zone_bleue_situation.jpg", avec_epingle=True)
