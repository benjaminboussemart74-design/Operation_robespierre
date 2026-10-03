# Typologie de l'électorat · 3e circonscription de la Seine-Saint-Denis

Classification des 82 bureaux de vote de la circonscription (Noisy-le-Grand 43,
Neuilly-sur-Marne 21, Neuilly-Plaisance 12, Gournay-sur-Marne 6) en familles
socio-électorales, avec la méthode de l'atlas électoral de Noisy-le-Grand.

- `build_data.py` : construction des indicateurs, classification (Ward), page.
- `typologie_template.html` : gabarit de la page ; `typologie.html` : page générée.
- `data.json` : données intermédiaires.

## Méthode

- 12 mesures de vote (participation aux municipales 2026, européennes 2024,
  législatives 2024 ; scores des grandes listes aux européennes et des candidats
  au premier tour des législatives 2024). Les scores municipaux ne sont pas
  utilisés : les listes diffèrent d'une commune à l'autre.
- 21 indicateurs sociaux INSEE (RP 2022, Filosofi 2021), mêmes définitions que l'atlas.
- Chaque bloc pèse la moitié du calcul ; CAH de Ward ; nombre de familles choisi
  par stabilité (300 sous-échantillons de 80 %).
- Revenu médian corrigé : le jeu source compte comme nuls les IRIS sans revenu
  publié ; le revenu de chaque IRIS est reconstitué puis chaque bureau repondéré.

## Reconstruire

Placer dans `cache/` (non versionné) :

| Fichier | Source |
|---|---|
| `gen_circo.parquet`, `cand_circo.parquet` | « Données des élections agrégées », data.gouv.fr, filtrées sur 93033, 93049, 93050, 93051 |
| `socio.parquet`, `corr.parquet` | « Profil sociodémographique des bureaux de vote », data.gouv.fr |
| `bvreu.parquet` | « Bureaux de vote et adresses de leurs électeurs » (table-bv-reu), INSEE |
| `circo_reu.geojson` | « Proposition de contours des bureaux de vote », Etalab, filtré sur les 4 communes |
| `D.json` | objet de données de l'atlas électoral de Noisy-le-Grand |

Puis : `python build_data.py 9 7`
