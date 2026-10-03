"""Reconstruction des secteurs électoraux à partir des adresses des électeurs.

Les contours proposés par Etalab sont très morcelés (jusqu'à huit morceaux par
bureau). On repart de la même source, les adresses du répertoire électoral
unique géolocalisées par l'INSEE, et on construit des secteurs d'un seul tenant :

1. Nettoyage : une petite adresse isolée au milieu des adresses d'un autre
   bureau (erreur de rattachement ou de géocodage) prend l'étiquette de ses voisines.
2. Diagramme de Voronoï : chaque point du territoire est attribué à l'adresse
   la plus proche, dans les limites de la commune.
3. Fusion des cellules par bureau.
4. Absorption des enclaves : un morceau détaché du corps principal d'un
   bureau, s'il regroupe moins de 10 % de ses électeurs, est rattaché au bureau
   voisin avec lequel il partage la plus longue frontière.

Contrôle : sur Noisy-le-Grand, comparé aux secteurs officiels de la Ville.
"""
import numpy as np
import pandas as pd
import geopandas as gpd
from scipy.spatial import cKDTree
from shapely.geometry import MultiPoint, Polygon, MultiPolygon
from shapely.ops import voronoi_diagram, unary_union

L93 = 2154  # Lambert 93, en mètres


def nettoyer(xy, lab, poids, k=8, tours=3, poids_max=3):
    """Réétiquette les adresses légères dont aucune voisine ne partage le bureau.

    Une adresse lourde (grand immeuble) n'est jamais modifiée : son isolement
    est alors réel, pas une erreur.
    """
    lab = lab.copy()
    arbre = cKDTree(xy)
    _, idx = arbre.query(xy, k=k + 1)
    for _ in range(tours):
        voisins = lab[idx[:, 1:]]
        change = 0
        for i in range(len(lab)):
            if poids[i] > poids_max:
                continue
            vals, n = np.unique(voisins[i], return_counts=True)
            if lab[i] not in vals and n.max() >= k // 2 + 1:
                lab[i] = vals[n.argmax()]
                change += 1
        if not change:
            break
    return lab


def morceaux(g):
    return list(g.geoms) if isinstance(g, MultiPolygon) else [g]


def secteurs(adresses, commune_geom, seuil=0.10):
    """adresses : DataFrame (x, y en Lambert 93, bv, nb) ; commune_geom : polygone Lambert 93.

    Un fragment détaché est rattaché au voisin s'il regroupe moins de `seuil`
    des électeurs du bureau ; au-delà, il est conservé (bureau en plusieurs parties).
    """
    a = (adresses.groupby(['x', 'y'], as_index=False)
         .agg(bv=('bv', lambda s: s.mode().iloc[0]), nb=('nb', 'sum')))
    xy = a[['x', 'y']].values
    a['bv'] = nettoyer(xy, np.asarray(a.bv, dtype=object), a.nb.values)
    pts = gpd.GeoDataFrame(a, geometry=gpd.points_from_xy(a.x, a.y), crs=L93)

    cellules = voronoi_diagram(MultiPoint(xy), envelope=commune_geom.buffer(2000))
    cel = gpd.GeoDataFrame(geometry=list(cellules.geoms), crs=L93)
    cel = gpd.sjoin(cel, pts[['bv', 'geometry']], predicate='contains').drop(columns='index_right')
    cel['geometry'] = cel.intersection(commune_geom)
    sect = cel.dissolve('bv').geometry.buffer(0)
    total = a.groupby('bv').nb.sum()

    def poids(p):
        return a.nb.values[pts.within(p).values].sum()

    # Absorption des petits fragments, jusqu'à stabilité
    for _ in range(10):
        geoms = dict(sect.items())
        bouge = False
        for bv in list(geoms):
            ps = sorted(morceaux(geoms[bv]), key=poids, reverse=True)
            for p in ps[1:]:
                if poids(p) >= seuil * total[bv]:
                    continue
                meilleur, lmax = None, 0
                for autre, g in geoms.items():
                    if autre != bv:
                        l = p.boundary.intersection(g.buffer(0.5)).length
                        if l > lmax:
                            meilleur, lmax = autre, l
                if meilleur is None:
                    continue
                geoms[bv] = geoms[bv].difference(p.buffer(0.01))
                geoms[meilleur] = unary_union([geoms[meilleur], p.buffer(0.01)])
                bouge = True
        sect = gpd.GeoSeries(geoms, crs=L93).buffer(0)
        if not bouge:
            break
    return sect.intersection(commune_geom)


def accord(sect, adresses):
    """Part des électeurs (pondérée) dont l'adresse tombe dans le secteur de leur bureau."""
    pts = gpd.GeoDataFrame(adresses, geometry=gpd.points_from_xy(adresses.x, adresses.y), crs=L93)
    s = gpd.GeoDataFrame({'bv_sect': sect.index}, geometry=sect.values, crs=L93)
    j = gpd.sjoin(pts, s, predicate='within', how='left')
    ok = j.bv == j.bv_sect
    return float((ok * j.nb).sum() / j.nb.sum())
