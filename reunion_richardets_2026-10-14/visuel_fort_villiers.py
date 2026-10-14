"""Vue aérienne du Fort de Villiers (orthophotographie IGN), sans texte.

Centre : point « Fort de Villiers » du géocodage IGN (ouvrage militaire, 2.555947 E, 48.833584 N).

Usage : python3 visuel_fort_villiers.py [largeur au sol en mètres]
"""
import math
import os
import sys

from PIL import ImageEnhance

from build_richardets import merc
from visuels_richardets import Vue

ICI = os.path.dirname(os.path.abspath(__file__))
FORT = (2.555947, 48.833584)
SORTIE = os.path.join(ICI, "Visuels_Richardets", "Equipements", "Equipements_04_fort_de_Villiers_vue_aerienne.jpg")


def vue_fort(largeur_m=600, taille=(2400, 1600)):
    lon, lat = FORT
    v = Vue(*merc(lon, lat), largeur_m / math.cos(math.radians(lat)), *taille)
    ImageEnhance.Contrast(v.photo(zoom_max=19)).enhance(1.05).save(SORTIE, quality=92)
    print("Écrit :", SORTIE)


if __name__ == "__main__":
    vue_fort(float(sys.argv[1]) if len(sys.argv) > 1 else 600)
