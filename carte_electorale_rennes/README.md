# Carte électorale de Rennes Métropole, bureau par bureau (1999-2026)

Carte interactive des résultats électoraux des 43 communes de Rennes Métropole à l'échelle du bureau de vote, pour les 56 tours de scrutin publiés depuis 1999.

## Fichiers

- `carte.html` : la page autonome (données incluses), à ouvrir dans un navigateur.
- `carte_template.html` : le gabarit de la page (mise en forme et code JavaScript).
- `build_data.py` : le script qui télécharge les sources, apparie résultats et contours, puis produit `data.json` et `carte.html`.
- `sources/perimetres-bureaux-de-vote-rennes.csv` : périmètres actuels des bureaux de la ville de Rennes (Rennes Métropole).

## Régénérer la carte

    pip install duckdb ijson shapely
    python3 build_data.py

Les sources volumineuses (environ 900 Mo) sont téléchargées dans `cache/`, qui n'est pas versionné.

## Sources

- Résultats : ministère de l'Intérieur, via le jeu « Données des élections agrégées » de data.gouv.fr.
- Contours : « Proposition de contours des bureaux de vote » (Insee et Etalab, répertoire électoral unique, situation 2022) et périmètres actuels de la ville de Rennes (Rennes Métropole).

## Limites

- Aucun résultat par bureau n'est publié en données ouvertes avant les européennes de 1999 : les scrutins de 1995 ne peuvent pas être cartographiés à cette échelle.
- Les périmètres changent au fil des redécoupages. Pour chaque scrutin et chaque commune, le script retient le référentiel dont les numéros de bureau correspondent le mieux. En deçà de 90 % de correspondance, la commune est affichée avec son résultat global (hachures). C'est le cas de Rennes avant 2015, la ville ayant renuméroté tous ses bureaux cette année-là.
- Un même numéro de bureau est supposé couvrir le même territoire d'un scrutin à l'autre.
