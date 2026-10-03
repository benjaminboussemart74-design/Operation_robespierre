"""Typologie de l'électorat de la 3e circonscription de la Seine-Saint-Denis.

Reprend, à l'échelle des 82 bureaux de vote de la circonscription (Noisy-le-Grand,
Neuilly-sur-Marne, Neuilly-Plaisance, Gournay-sur-Marne), la méthode de l'atlas
électoral de Noisy-le-Grand : classification ascendante hiérarchique (Ward) sur
des mesures de vote 2022-2024 et sur le profil social INSEE, à poids égal.

Différence de méthode avec l'atlas : seuls les scrutins nationaux (présidentielle
2022, européennes et législatives 2024) servent au calcul. Les municipales 2026
en sont exclues : listes et enjeux propres à chaque commune.

Entrées (dossier cache/, non versionné, cf. README.md) :
  gen_circo.parquet, cand_circo.parquet  résultats par bureau (data.gouv.fr, agrégation)
  socio.parquet                          profil social par bureau (INSEE RP 2022, Filosofi 2021)
  bvreu.parquet                          lieux de vote (REU, INSEE)
  circo_reu.geojson                      contours estimés des bureaux (Etalab), pour le contour des communes
  adresses_circo.parquet                 adresses des électeurs par bureau (REU, INSEE), pour les secteurs
  D.json                                 données de l'atlas de Noisy-le-Grand (secteurs officiels, typologie)
Sorties : data.json, typologie.html (page générée depuis typologie_template.html)
Usage : python build_data.py 8 8   (nombre de familles : socio-électorale, électorale seule)
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage, dendrogram
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from sklearn.metrics import adjusted_rand_score

HERE = Path(__file__).parent
C = HERE / 'cache'
COMMUNES = {'93051': 'Noisy-le-Grand', '93050': 'Neuilly-sur-Marne',
            '93049': 'Neuilly-Plaisance', '93033': 'Gournay-sur-Marne'}
# Bureaux créés en 2024, sans profil social publié : ils reçoivent celui du bureau dont ils sont issus.
PARENT = {'93051_0043': '93051_0021', '93050_0021': '93050_0004'}
SEED = 2026

gen = pd.read_parquet(C / 'gen_circo.parquet')
cand = pd.read_parquet(C / 'cand_circo.parquet')
gen['bv'] = gen.code_commune + '_' + gen.code_bv
cand['bv'] = cand.code_commune + '_' + cand.code_bv


def scrutin(eid):
    g = gen[gen.id_election == eid].set_index('bv')
    return g[['inscrits', 'votants', 'exprimes', 'blancs', 'nuls']].fillna(0).astype(int)


def voix(eid, key, groups):
    """Voix par bureau et par groupe ; groups = {libellé: [valeurs de la colonne key]}."""
    c = cand[cand.id_election == eid]
    out = {}
    for lab, vals in groups.items():
        out[lab] = c[c[key].isin(vals)].groupby('bv').voix.sum()
    return pd.DataFrame(out).fillna(0).astype(int)


# ── Scrutins (affichage et calcul) ───────────────────────────────────────────
EURO = {'LFI (Aubry)': ['LFI'], 'RN et Reconquête': ['LRN', 'LREC'],
        'PS, écologistes et PCF': ['LUG', 'LVEC', 'LCOM'], 'Renaissance (Hayer)': ['LENS'],
        'LR (Bellamy)': ['LLR']}
LEGI1 = {'Portes (NFP)': ['PORTES'], 'Cretin-Gielly (RN)': ['CRETIN-GIELLY'],
         'Centre (Anato, Richard, Diaby)': ['ANATO', 'RICHARD', 'DIABY'],
         'Droite (Allemon, Buttey)': ['ALLEMON', 'BUTTEY']}
LEGI2 = {'Portes (NFP)': ['PORTES'], 'Cretin-Gielly (RN)': ['CRETIN-GIELLY']}
PRES1 = {'Mélenchon': ['MÉLENCHON', 'MELENCHON'], 'Macron': ['MACRON'],
         'Le Pen et Zemmour': ['LE PEN', 'ZEMMOUR'], 'Pécresse': ['PÉCRESSE', 'PECRESSE'],
         'Gauche modérée (Jadot, Roussel, Hidalgo)': ['JADOT', 'ROUSSEL', 'HIDALGO']}

SCRUTINS = [
    ('2024_euro_t1', 'Européennes 2024', 'nuance', None, EURO),
    ('2024_legi_t1', 'Législatives 2024 · 1er tour', 'nom', None, LEGI1),
    ('2024_legi_t2', 'Législatives 2024 · 2d tour', 'nom', None, LEGI2),
    ('2022_pres_t1', 'Présidentielle 2022 · 1er tour', 'nom', None, PRES1),
    ('2022_pres_t2', 'Présidentielle 2022 · 2d tour', 'nom', None, {'Macron': ['MACRON'], 'Le Pen': ['LE PEN']}),
    ('2026_muni_t1', 'Municipales 2026 · 1er tour', None, None, None),
]

BV = sorted(gen[gen.id_election == '2024_legi_t1'].bv.unique())
assert len(BV) == 82, len(BV)

res = {}
for eid, titre, key, _, groups in SCRUTINS:
    g = scrutin(eid)
    d = {'titre': titre, 'bv': {}}
    if groups:
        if key == 'nom':
            cand.loc[cand.id_election == eid, 'nom'] = cand.loc[cand.id_election == eid, 'nom'].str.upper()
        v = voix(eid, key, groups)
        d['cands'] = list(groups)
    for bv in BV:
        if bv not in g.index:
            continue
        r = g.loc[bv]
        row = {'i': int(r.inscrits), 'v': int(r.votants), 'e': int(r.exprimes)}
        if groups:
            row['x'] = [int(v.loc[bv, k]) if bv in v.index else 0 for k in groups]
        d['bv'][bv] = row
    res[eid] = d

# ── Variables de vote (15 mesures comme l'atlas, ici 12 comparables entre communes) ──
def part(eid):
    return pd.Series({bv: 100 * r['v'] / r['i'] for bv, r in res[eid]['bv'].items()})


def score(eid, k):
    j = res[eid]['cands'].index(k)
    return pd.Series({bv: 100 * r['x'][j] / r['e'] for bv, r in res[eid]['bv'].items()})


def herite(serie):
    """Bureaux créés en 2024 : taux de 2022 du bureau dont ils sont issus."""
    for nouveau, ancien in PARENT.items():
        serie[nouveau] = serie[ancien]
    return serie


# Les municipales ne servent pas au calcul : listes et enjeux propres à chaque
# commune (trois communes sur quatre ont élu leur maire dès le premier tour).
VOTE = {
    'Participation · présidentielle 2022, 1er tour': herite(part('2022_pres_t1')),
    'Participation · européennes 2024': part('2024_euro_t1'),
    'Participation · législatives 2024, 1er tour': part('2024_legi_t1'),
}
for k in EURO:
    VOTE[f'{k} · européennes 2024'] = score('2024_euro_t1', k)
for k in LEGI1:
    VOTE[f'{k} · législatives 2024, 1er tour'] = score('2024_legi_t1', k)
for k in PRES1:
    VOTE[f'{k} · présidentielle 2022, 1er tour'] = herite(score('2022_pres_t1', k))
XV = pd.DataFrame(VOTE).loc[BV]
assert not XV.isna().any().any()

# ── Profil social (mêmes 21 indicateurs et mêmes définitions que l'atlas) ─────
so = pd.read_parquet(C / 'socio.parquet').set_index('id_brut_miom')
so = so[so.code_commune.isin(COMMUNES)].copy()


def revenu_corrige():
    """Revenu médian par bureau, sans les IRIS dont le revenu n'est pas publié.

    Le jeu source compte ces IRIS (Filosofi masqué) comme un revenu nul, ce qui
    abaisse la moyenne pondérée (ex. Neuilly-sur-Marne 12 : 1 811 €). On retrouve
    le revenu de chaque IRIS en inversant la pondération par logements
    (système exact, commune par commune), puis on repondère sur les seuls IRIS publiés.
    Renvoie aussi la part des logements du bureau couverte par un revenu publié.
    """
    corr = pd.read_parquet(C / 'corr.parquet')
    med, couv = {}, {}
    for com in COMMUNES:
        cc = corr[corr.code_commune == com]
        bvs, iris = sorted(cc.id_brut_miom.unique()), sorted(cc.iris_code.unique())
        A = np.zeros((len(bvs), len(iris)))
        for r in cc.itertuples():
            A[bvs.index(r.id_brut_miom), iris.index(r.iris_code)] = r.nlogh_sum
        m = np.linalg.lstsq(A / A.sum(1, keepdims=True), so.loc[bvs, 'MED21'].values, rcond=None)[0]
        ok = A * (m > 1000)
        for b, num, den, tot in zip(bvs, (ok * m).sum(1), ok.sum(1), A.sum(1)):
            med[b], couv[b] = num / den, den / tot
    return pd.Series(med), pd.Series(couv)


so['MED21'], COUV_REV = revenu_corrige()
for new, old in PARENT.items():
    COUV_REV[new] = COUV_REV[old]
    so.loc[new] = so.loc[old]
pc = lambda a, b: 100 * so[a] / so[b]
SOCIO = pd.DataFrame({
    'rev': so.MED21,
    'cad': pc('C_POP15P_CS3', 'P_POP15P'), 'pint': pc('C_POP15P_CS4', 'P_POP15P'),
    'emp': pc('C_POP15P_CS5', 'P_POP15P'), 'ouv': pc('C_POP15P_CS6', 'P_POP15P'),
    'ret': pc('C_POP15P_CS7', 'P_POP15P'),
    'dip': 100 * (so.P_NSCOL15P_SUP2 + so.P_NSCOL15P_SUP34 + so.P_NSCOL15P_SUP5) / so.P_NSCOL15P,
    'sdip': pc('P_NSCOL15P_DIPLMIN', 'P_NSCOL15P'),
    'cho': pc('P_CHOM1564', 'P_ACT1564'),
    'hlm': pc('P_RP_LOCHLMV', 'P_RP'), 'pro': pc('P_RP_PROP', 'P_RP'),
    'lpriv': 100 * (so.P_RP_LOC - so.P_RP_LOCHLMV) / so.P_RP,
    'mai': pc('P_RPMAISON', 'P_RP'), 'svoit': 100 * (so.P_RP - so.P_RP_VOIT1P) / so.P_RP,
    'imm': pc('P_POP_IMM', 'P_POP'), 'jeu': pc('P_POP1524', 'P_POP'),
    'p60': pc('P_POP60P', 'P_POP'), 'p80': pc('P_POP80P', 'P_POP'),
    'mono': pc('C_FAMMONO', 'C_FAM'), 'cpl': pc('C_COUPAENF', 'C_FAM'),
    'seul': pc('C_MENPSEUL', 'C_MEN'),
}).loc[BV]
assert not SOCIO.isna().any().any()

# ── Classification ───────────────────────────────────────────────────────────
def z(df):
    return (df - df.mean()) / df.std(ddof=0)


def matrice(blocs):
    """Chaque bloc standardisé pèse autant que les autres (variance totale égale)."""
    return np.hstack([z(b).values / np.sqrt(b.shape[1]) for b in blocs])


def r2(X, lab):
    tot = ((X - X.mean(0)) ** 2).sum()
    intra = sum(((X[lab == k] - X[lab == k].mean(0)) ** 2).sum() for k in np.unique(lab))
    return 1 - intra / tot


def stabilite(X, k, n=300, frac=0.8):
    """ARI moyen entre la partition complète et celle obtenue sur des sous-échantillons."""
    rng = np.random.default_rng(SEED)
    ref = fcluster(linkage(X, 'ward'), k, 'maxclust')
    s = []
    for _ in range(n):
        idx = np.sort(rng.choice(len(X), int(frac * len(X)), replace=False))
        lab = fcluster(linkage(X[idx], 'ward'), k, 'maxclust')
        s.append(adjusted_rand_score(ref[idx], lab))
    return float(np.mean(s))


def typologie(blocs, kmin=4, kmax=12):
    X = matrice(blocs)
    Z = linkage(X, 'ward')
    diag = []
    for k in range(kmin, kmax + 1):
        lab = fcluster(Z, k, 'maxclust')
        diag.append({'k': k, 'stab': round(stabilite(X, k), 3),
                     'r2': [round(r2(z(b).values, lab), 3) for b in blocs],
                     'min': int(np.bincount(lab)[1:].min())})
    return X, Z, diag


if __name__ == '__main__':
    import sys
    Xf, Zf, diag_f = typologie([XV, SOCIO])
    Xv, Zv, diag_v = typologie([XV])
    for nom, dg in (('fine', diag_f), ('vote', diag_v)):
        print(nom)
        for d in dg:
            print('  ', d)
    if len(sys.argv) < 3:
        sys.exit('Indiquer le nombre de familles retenu : python build_data.py K_FINE K_VOTE')
    KF, KV = int(sys.argv[1]), int(sys.argv[2])
    raw_f = pd.Series(fcluster(Zf, KF, 'maxclust'), index=BV)
    raw_v = pd.Series(fcluster(Zv, KV, 'maxclust'), index=BV)

    # Nommage des familles, établi à la lecture des profils (KF=8, KV=8).
    # Ordre d'affichage : des quartiers les plus populaires aux plus aisés.
    # Chaque entrée : numéro brut de scipy -> (rang affiché, bureau témoin, nom, couleur)
    NOMS_F = {
        1: (1, '93051_0023', 'Grands ensembles les plus précaires, bastions insoumis', '#1f5fae'),
        2: (2, '93050_0005', "Cités d'habitat social, vote insoumis majoritaire", '#6fa8dc'),
        3: (3, '93050_0009', 'Quartiers populaires cosmopolites en immeubles', '#eb6834'),
        4: (4, '93050_0001', 'Quartiers mixtes aux revenus modestes, RN un peu au-dessus de la moyenne', '#f3b98f'),
        5: (5, '93049_0006', 'Petits collectifs locatifs, jeunes actifs et personnes seules', '#eda100'),
        6: (6, '93051_0001', 'Classes moyennes diplômées en appartement, gauche modérée et centre', '#e87ba4'),
        8: (7, '93049_0001', 'Quartiers aisés de propriétaires, forte participation', '#008300'),
        7: (8, '93033_0001', 'Pavillonnaire aisé, droite et RN en tête', '#4a3aa7'),
    }
    NOMS_V = {
        1: ('A', '93051_0023', 'Bastions insoumis', '#A23B78'),
        2: ('B', '93051_0017', 'Vote insoumis majoritaire', '#C9578F'),
        3: ('C', '93050_0005', 'Vote insoumis, RN et centre présents', '#E58FB3'),
        4: ('D', '93050_0001', 'Bureaux partagés entre gauche et Rassemblement national', '#E0A458'),
        8: ('E', '93051_0001', 'Bureaux dans la moyenne de la circonscription', '#B9B2A0'),
        7: ('F', '93051_0002', 'Gauche modérée et centre, forte participation', '#0F9E86'),
        5: ('G', '93049_0001', 'Droite, centre et RN au-dessus de la moyenne', '#7C8FD6'),
        6: ('H', '93033_0001', 'Droite et RN en tête, vote insoumis marginal', '#2E4A9E'),
    }
    for raw, noms in ((raw_f, NOMS_F), (raw_v, NOMS_V)):
        for k, (_, temoin, nom, _) in noms.items():
            assert raw[temoin] == k, f'les familles ont changé : {nom} ({temoin}) — revoir le nommage'
    lab_f = raw_f.map(lambda k: NOMS_F[k][0])
    lab_v = raw_v.map(lambda k: NOMS_V[k][0])
    familles_f = {str(v[0]): {'nom': v[2], 'col': v[3]} for v in NOMS_F.values()}
    familles_v = {v[0]: {'nom': v[2], 'col': v[3]} for v in NOMS_V.values()}

    # Profils moyens (moyenne simple des bureaux, comme l'atlas)
    def profils(lab):
        out = {}
        for k in sorted(lab.unique(), key=str):
            m = lab.index[lab == k]
            out[str(k)] = {
                'bv': list(m),
                'inscrits': int(sum(res['2024_legi_t1']['bv'][b]['i'] for b in m)),
                'communes': {c: int(sum(b.startswith(c) for b in m)) for c in COMMUNES},
                'ins_communes': {c: int(sum(res['2024_legi_t1']['bv'][b]['i'] for b in m if b.startswith(c))) for c in COMMUNES},
                'vote': XV.loc[m].mean().round(1).tolist(),
                'socio': SOCIO.loc[m].mean().round(1).tolist(),
            }
        return out

    # Dendrogramme (ordre des feuilles et segments, pour le dessin)
    def dendro(Z):
        d = dendrogram(Z, no_plot=True, labels=BV)
        return {'feuilles': d['ivl'], 'icoord': d['icoord'], 'dcoord': d['dcoord']}

    def coupe(Z, k):
        h = sorted(Z[:, 2])
        return float((h[-k] + h[-k + 1]) / 2)

    # Correspondance avec la typologie fine de l'atlas de Noisy-le-Grand
    D = json.load(open(C / 'D.json'))
    noisy = {f'93051_{bv}': int(t) for bv, t in D['typo2'].items()}

    # Géométries : secteurs officiels pour Noisy-le-Grand ; ailleurs, secteurs
    # reconstruits à partir des adresses des électeurs (cf. secteurs.py)
    import geopandas as gpd
    from secteurs import secteurs, accord, L93
    geo = {}
    for bv, b in D['bureaux'].items():
        geo[f'93051_{bv}'] = shape({'type': 'MultiPolygon', 'coordinates': b['geo']})
    adr = pd.read_parquet(C / 'adresses_circo.parquet')
    adr['bv'] = adr.code_commune_ref + '_' + adr.id_brut_bv_reu.str.split('_').str[1].str.zfill(4)
    xy = gpd.GeoSeries(gpd.points_from_xy(adr.longitude, adr.latitude), crs=4326).to_crs(L93)
    adr['x'], adr['y'], adr['nb'] = xy.x.values, xy.y.values, adr.nb_adresses.astype(int)
    reu = gpd.read_file(C / 'circo_reu.geojson').to_crs(L93)
    qualite = {}
    for com in COMMUNES:
        if com == '93051':
            continue
        contour = unary_union(reu[reu.codeCommune == com].geometry).buffer(1).buffer(-1)
        a = adr[adr.code_commune_ref == com]
        sect = secteurs(a, contour)
        qualite[com] = round(accord(sect, a), 3)
        for bv, g in sect.simplify(12).to_crs(4326).items():
            geo[bv] = g
    print('électeurs dans le secteur de leur bureau :', qualite)

    def coords(g):
        g = g.simplify(0.00005, preserve_topology=True)
        m = mapping(g)
        c = m['coordinates'] if m['type'] == 'MultiPolygon' else [m['coordinates']]
        return [[[[round(x, 5), round(y, 5)] for x, y in ring] for ring in poly] for poly in c]

    # Lieux de vote
    lieux = {}
    reu_bv = pd.read_parquet(C / 'bvreu.parquet').set_index('id_brut_miom')
    for bv in BV:
        if bv.startswith('93051'):
            lieux[bv] = D['bureaux'][bv[6:]]['lieu']
        elif bv in reu_bv.index:
            r = reu_bv.loc[bv]
            lib = r.libelle_reu if not r.libelle_reu.lower().startswith('bureau') else r.voie_reu
            lib = str(lib).strip()
            if lib.isupper() or lib.islower():
                lib = lib.capitalize().replace('Gs ', 'Groupe scolaire ').replace('Group scol', 'Groupe scolaire').replace('Groupe scol ', 'Groupe scolaire ')
            lieux[bv] = lib
        else:
            lieux[bv] = ''

    out = {
        'communes': COMMUNES,
        'bv': BV,
        'lieux': lieux,
        'parent': PARENT,
        'geo': {bv: coords(g) for bv, g in geo.items()},
        'scrutins': res,
        'vote_noms': list(XV.columns),
        'vote': XV.round(2).values.tolist(),
        'socio_noms': list(SOCIO.columns),
        'socio': SOCIO.round(2).values.tolist(),
        'couv_rev': {bv: round(float(COUV_REV[bv]), 2) for bv in BV if COUV_REV[bv] < 0.9},
        'moy_vote': XV.mean().round(1).tolist(),
        'moy_socio': SOCIO.mean().round(1).tolist(),
        'qualite_secteurs': qualite,
        'contours': {c: coords(unary_union([geo[b].buffer(0.00008) for b in geo if b.startswith(c)]).buffer(-0.00008))
                     for c in COMMUNES},
        'fine': {'k': KF, 'lab': lab_f.astype(str).tolist(), 'familles': familles_f, 'diag': diag_f,
                 'profils': profils(lab_f), 'dendro': dendro(Zf), 'coupe': coupe(Zf, KF)},
        'vote_seul': {'k': KV, 'lab': lab_v.tolist(), 'familles': familles_v, 'diag': diag_v,
                      'profils': profils(lab_v)},
        'noisy': noisy,
    }
    txt = json.dumps(out, ensure_ascii=False, separators=(',', ':'))
    (HERE / 'data.json').write_text(txt)
    tpl = (HERE / 'typologie_template.html').read_text()
    (HERE / 'typologie.html').write_text(tpl.replace('__DATA__', txt))
    print('data.json et typologie.html écrits')
