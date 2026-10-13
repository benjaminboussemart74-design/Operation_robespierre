"""Compte les signalements du formulaire de la Ville (dysfonctionnements du réseau de bus) pour les
arrêts du quartier, et écrit signalements_par_arret.csv.

Les noms d'arrêts ont été saisis librement : on les normalise (minuscules, sans accents ni
ponctuation) puis on les rattache à un arrêt Île-de-France Mobilités par des règles explicites.
Les saisies ambiguës (deux arrêts possibles) ne sont pas comptées. Aucune donnée personnelle
(nom, prénom, courriel) n'est lue.

Usage : python3 compter_signalements_bus.py chemin/vers/Signalements.xlsx
"""
import collections
import csv
import os
import re
import sys
import unicodedata

import openpyxl

ICI = os.path.dirname(os.path.abspath(__file__))
SORTIE = os.path.join(ICI, "signalements_par_arret.csv")
SYNTHESE = os.path.join(ICI, "signalements_synthese.csv")

# forme normalisée de la saisie -> arrêt IDFM du quartier
REGLES = [
    (r"^(place du )?combat$", "Place du Combat"),
    (r"^(cite|cote|les)? ?des hetres$|^les hetres$", "Cité des Hêtres"),
    (r"^rue du ballon( circulaire exterieure)?$", "Rue du Ballon"),
    (r"^le fort$", "Le Fort"),
    (r"^(les )?richardets( centre)?$", "Les Richardets - Centre"),
    (r"^rue de la chapelle$", "Rue de la Chapelle"),
    (r"^college des yvris$", "Collège des Yvris"),
    (r"^(les )?graviers$", "Les Graviers"),
    (r"^victor hugo$", "Victor Hugo"),
    (r"^(le )?closeau$", "Le Closeau"),
    (r"^rue des aerostiers?$", "Rue des Aérostiers"),
    (r"^gabriel peri$", "Gabriel Péri"),
    (r"^(la )?butte aux cailles$", "La Butte aux Cailles"),
    (r"^moulin a vent$", "Moulin à Vent"),
    (r"^ballon chapelle$", "Ballon - Chapelle"),
    (r"^chapelle$", "Chapelle"),
    (r"^les aerostiers$", "Les Aérostiers"),
    # gare des Yvris : toutes les formes qui désignent la gare RER
    (r"^(la )?gare (des )?yvris( noisy le grand)?$|^les yvris noisy le grand( rer)?$|"
     r"^noisy le grand les yi?vris$|^les yvris$", "Les Yvris - Noisy-le-Grand RER"),
]
PROBLEMES = ["Non passage du bus", "Retard inférieur à 15 min", "Retard de 16 à 30 min",
             "Retard supérieur à 30 min", "Horaires erronés sur l'affichage en temps réel",
             "Horaires erronés sur l'affichage papier", "Autre"]


def norme(s):
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def arret(saisie):
    n = norme(saisie)
    for motif, nom in REGLES:
        if re.search(motif, n):
            return nom
    return None


def main(classeur):
    ws = openpyxl.load_workbook(classeur, read_only=True, data_only=True).active
    lignes = [r[:5] for r in ws.iter_rows(min_row=2, values_only=True) if any(r[:5])]  # colonnes A à E
    par_arret = collections.Counter()
    par_ligne_ville = collections.Counter(norme(r[0]) for r in lignes)
    probleme_quartier = collections.Counter()
    for num, nom, _jour, _heure, probleme in lignes:
        a = arret(nom)
        if a:
            par_arret[a] += 1
            for p in str(probleme or "").split(","):
                if p.strip():
                    probleme_quartier[p.strip()] += 1
    # mise à jour du fichier des arrêts (colonne « signalements »)
    rows = list(csv.DictReader(open(SORTIE, encoding="utf-8")))
    for r in rows:
        r["signalements"] = str(par_arret.get(r["arret"], 0))
    with open(SORTIE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    with open(SYNTHESE, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["indicateur", "libelle", "valeur"])
        w.writerow(["total_ville", "Signalements dans toute la ville", len(lignes)])
        w.writerow(["total_quartier", "Signalements aux arrêts du quartier", sum(par_arret.values())])
        for l in ("310", "312", "320"):
            w.writerow(["ligne_ville", l, par_ligne_ville.get(l, 0)])
        for p in PROBLEMES:
            w.writerow(["probleme_quartier", p, probleme_quartier.get(p, 0)])
    print("Signalements :", len(lignes), "- aux arrêts du quartier :", sum(par_arret.values()))
    for a, n in par_arret.most_common():
        print(f"  {n:3}  {a}")
    print("Problèmes (quartier) :", probleme_quartier.most_common())
    print("Lignes (ville) :", par_ligne_ville.most_common())


if __name__ == "__main__":
    main(sys.argv[1])
