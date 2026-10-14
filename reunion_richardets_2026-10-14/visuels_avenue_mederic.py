"""Vue aérienne de l'avenue Médéric, pour la diapositive des commerces.

Fond : orthophotographies IGN. L'image ne porte aucun texte ; la légende est posée dans la diapositive.

Usage : python3 visuels_avenue_mederic.py
"""
import os

from build_richardets import vue_aerienne

ICI = os.path.dirname(os.path.abspath(__file__))
SORTIE = os.path.join(ICI, "Visuels_Richardets", "Commerces")
CENTRE = (2.5685, 48.8294)          # milieu de la partie commerçante de l'avenue (numéros 33 à 150)


if __name__ == "__main__":
    os.makedirs(SORTIE, exist_ok=True)
    chemin = os.path.join(SORTIE, "Commerces_01_avenue_Mederic.jpg")
    vue_aerienne(*CENTRE, 1150, (3000, 1320)).save(chemin, quality=92)
    print("Écrit :", chemin)
