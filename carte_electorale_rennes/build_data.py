"""
Prépare les données de la carte électorale de Rennes Métropole par bureau de vote.

Sources
-------
- Résultats par bureau de vote (1999-2026) : « Données des élections agrégées »,
  data.gouv.fr, construites à partir des fichiers du ministère de l'Intérieur.
- Contours des bureaux de vote : « Proposition de contours des bureaux de vote »
  (Etalab / Insee, répertoire électoral unique, situation 2022).
- Périmètres actuels des bureaux de la ville de Rennes : Rennes Métropole
  (fichier sources/perimetres-bureaux-de-vote-rennes.csv).

Usage
-----
    python3 build_data.py            # télécharge les sources manquantes dans ./cache
Sortie : data.json (lu par la page carte.html).
"""

import csv
import json
import os
import re
import sys
import urllib.request
from collections import defaultdict

import duckdb
import ijson
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

ICI = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(ICI, "cache")
SOURCES = {
    "general_results.parquet": "https://data-pipeline-open.s3.sbg.io.cloud.ovh.net/elections/general_results.parquet",
    "candidats_results.parquet": "https://data-pipeline-open.s3.sbg.io.cloud.ovh.net/elections/candidats_results.parquet",
    "contours.geojson": "https://data-pipeline-open.s3.sbg.io.cloud.ovh.net/reu/contours-france-entiere-latest-v2.geojson",
}
PERIM_RENNES = os.path.join(ICI, "sources", "perimetres-bureaux-de-vote-rennes.csv")

# Les 43 communes de Rennes Métropole
COMMUNES = ["Acigné", "Bécherel", "Betton", "Bourgbarré", "Brécé", "Bruz", "Cesson-Sévigné",
            "Chantepie", "La Chapelle-Chaussée", "La Chapelle-des-Fougeretz", "La Chapelle-Thouarault",
            "Chartres-de-Bretagne", "Chavagne", "Chevaigné", "Cintré", "Clayes", "Corps-Nuds", "Gévezé",
            "L'Hermitage", "Laillé", "Langan", "Le Rheu", "Le Verger", "Miniac-sous-Bécherel",
            "Montgermont", "Mordelles", "Noyal-Châtillon-sur-Seiche", "Nouvoitou", "Orgères", "Pacé",
            "Parthenay-de-Bretagne", "Pont-Péan", "Rennes", "Romillé", "Saint-Armel", "Saint-Erblon",
            "Saint-Gilles", "Saint-Grégoire", "Saint-Jacques-de-la-Lande", "Saint-Sulpice-la-Forêt",
            "Thorigné-Fouillard", "Vern-sur-Seiche", "Vezin-le-Coquet"]

# Seuil d'appariement : en deçà, le résultat est affiché à l'échelle de la commune
SEUIL = 0.9

# ── Blocs politiques ──────────────────────────────────────────────────────────
BLOCS = ["GR", "GAU", "ECO", "CEN", "DRO", "ED", "REG", "DIV"]
NUANCE_BLOC = {
    # Gauche radicale et extrême gauche
    **{k: "GR" for k in ["EXG", "COM", "FG", "FI", "PG", "LCR", "LO", "DXG", "XG", "PC", "COP", "EXTG", "POI"]},
    # Gauche socialiste, divers gauche, unions de la gauche
    **{k: "GAU" for k in ["SOC", "PS", "DVG", "RDG", "PRG", "UG", "NUP", "GAU", "GA", "DG", "GC", "PREP"]},
    # Écologistes
    **{k: "ECO" for k in ["VEC", "ECO", "VE", "UGE"]},
    # Centre et majorité présidentielle (depuis 2017)
    **{k: "CEN" for k in ["UDF", "UDFD", "MODM", "MDM", "M", "M-NC", "REM", "ENS", "UC", "CMD", "UDI",
                          "NCE", "ALLI", "CEN", "DVC", "PRV", "MC"]},
    # Droite
    **{k: "DRO" for k in ["RPR", "UMP", "LR", "DVD", "UD", "UCD", "DR", "DD", "DTE", "MPF", "DLF", "DSV",
                          "RPF", "CPNT", "CP", "DL"]},
    # Extrême droite
    **{k: "ED" for k in ["FN", "RN", "MNR", "MNA", "FRN", "EXD", "XD", "REC", "EXTD"]},
    # Régionalistes
    "REG": "REG",
}
# Candidats à l'élection présidentielle (code de nuance avant 2017, nom ensuite)
PRESIDENTIELLE = {
    "GR": ["LAGU", "BESA", "HUE", "GLUC", "BUFF", "BOVE", "SCHI", "MELE", "POUT", "ARTH",
           "MÉLENCHON", "POUTOU", "ARTHAUD", "ROUSSEL"],
    "GAU": ["JOSP", "CHEV", "TAUB", "ROYA", "HOLL", "HAMON", "HIDALGO"],
    "ECO": ["MAME", "LEPA", "VOYN", "JOLY", "JADOT"],
    "CEN": ["BAYR", "MACRON"],
    "DRO": ["CHIR", "MADE", "BOUT", "SAIN", "VILL", "NIHO", "SARK", "DUPO", "FILLON",
            "DUPONT-AIGNAN", "PÉCRESSE"],
    "ED": ["LEPE", "MEGR", "LE PEN", "ZEMMOUR"],
    "DIV": ["CHEM", "ASSELINEAU", "LASSALLE", "CHEMINADE"],
}
PRES_BLOC = {k: b for b, ks in PRESIDENTIELLE.items() for k in ks}
# Européennes 2019 : aucune nuance dans la source, classement par tête de liste
EURO_2019 = {
    "LOISEAU": "CEN", "JADOT": "ECO", "GLUCKSMANN": "GAU", "BARDELLA": "ED", "BELLAMY": "DRO",
    "HAMON": "GAU", "AUBRY": "GR", "LAGARDE": "CEN", "BROSSAT": "GR", "BOURG": "ECO",
    "DUPONT-AIGNAN": "DRO", "ARTHAUD": "GR", "PHILIPPOT": "ED", "VAUCLIN": "ED", "CAMUS": "ED",
    "SANCHEZ": "GR",
}
TYPES = {"pres": "Présidentielle", "legi": "Législatives", "euro": "Européennes",
         "regi": "Régionales", "dpmt": "Départementales", "cant": "Cantonales", "muni": "Municipales"}


def bloc_de(election, nuance, nom, tete):
    annee, typ = int(election[:4]), election[5:9]
    if typ == "pres":
        return PRES_BLOC.get(nuance) or PRES_BLOC.get((nom or "").upper(), "DIV")
    if election == "2019_euro_t1":
        return EURO_2019.get((tete or "").split(" ")[0].upper(), "DIV")
    if not nuance:
        return "DIV"
    n = nuance
    if n.startswith("BC-"):
        n = n[3:]
    elif typ in ("euro", "regi", "muni") and n.startswith("L") and len(n) > 2:
        n = n[1:]
    if n == "MAJ":  # « majorité présidentielle » : UMP avant 2012, macronie ensuite
        return "DRO" if annee <= 2012 else "CEN"
    return NUANCE_BLOC.get(n, "DIV")


def libelle_candidat(typ, nom, prenom, liste, tete, nuance):
    if typ == "pres":
        return " ".join(x for x in [(prenom or "").title(), (nom or "").title()] if x).strip()
    if liste:
        return liste.strip().capitalize() if liste.isupper() else liste.strip()
    if tete:
        return tete
    base = (nom or "").title()
    return f"{base} ({nuance})" if nuance else base


# ── Téléchargement ────────────────────────────────────────────────────────────
def telecharger():
    os.makedirs(CACHE, exist_ok=True)
    for nom, url in SOURCES.items():
        chemin = os.path.join(CACHE, nom)
        if not os.path.exists(chemin):
            print("Téléchargement", url, file=sys.stderr)
            urllib.request.urlretrieve(url, chemin)


# ── Géométries ────────────────────────────────────────────────────────────────
def arrondir(geom, tol=0.00004):
    g = geom.simplify(tol, preserve_topology=True)
    d = mapping(g)

    def r(c):
        return [round(c[0], 5), round(c[1], 5)]

    if d["type"] == "Polygon":
        polys = [d["coordinates"]]
    else:
        polys = d["coordinates"]
    return [[[r(c) for c in anneau] for anneau in poly] for poly in polys]


def charger_geometries():
    reu = []
    with open(os.path.join(CACHE, "contours.geojson"), "rb") as f:
        for ft in ijson.items(f, "features.item", use_float=True):
            p = ft["properties"]
            if p["codeDepartement"] == "35" and p["nomCommune"] in COMMUNES:
                reu.append((p["codeCommune"], p["nomCommune"], p["numeroBureauVote"], shape(ft["geometry"])))
    rennes = []
    csv.field_size_limit(10 ** 9)
    with open(PERIM_RENNES, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f, delimiter=";"):
            geom = shape(json.loads(row["Geo Shape"]))
            rennes.append(("35238", "Rennes", row["num_bureau"].zfill(4), geom))
    noms = {cc: nom for cc, nom, _, _ in reu}
    grilles = {"reu2022": reu, "rennes2026": rennes}
    communes = {}
    par_commune = defaultdict(list)
    for cc, _, _, g in reu:
        par_commune[cc].append(g)
    for cc, gs in par_commune.items():
        communes[cc] = unary_union([g.buffer(0) for g in gs]).buffer(0.00001).buffer(-0.00001)
    return grilles, communes, noms


# ── Résultats ─────────────────────────────────────────────────────────────────
def main():
    telecharger()
    grilles, communes, noms = charger_geometries()
    codes = tuple(sorted(communes))
    db = duckdb.connect()
    gen = db.sql(f"""select id_election, code_commune, code_bv, inscrits, votants, exprimes
                     from '{CACHE}/general_results.parquet' where code_commune in {codes}""").fetchall()
    cand = db.sql(f"""select id_election, code_commune, code_bv, nuance, nom, prenom,
                      coalesce(libelle_abrege_liste, liste), nom_tete_liste, voix
                      from '{CACHE}/candidats_results.parquet' where code_commune in {codes}""").fetchall()

    # Index des polygones par grille : {grille: {commune: {code}}}
    index = {g: defaultdict(set) for g in grilles}
    for g, feats in grilles.items():
        for cc, _, code, _ in feats:
            index[g][cc].add(code)

    elections = defaultdict(lambda: {"bv": {}, "cands": {}, "liste": []})
    for e, cc, bv, ins, vot, exp in gen:
        elections[e]["bv"][(cc, bv)] = [ins or 0, vot or 0, exp or 0, []]
    for e, cc, bv, nu, nom, prenom, liste, tete, voix in cand:
        el = elections[e]
        if (cc, bv) not in el["bv"]:
            continue
        typ = e[5:9]
        cle = (nu, nom if typ in ("pres",) else (liste or tete or nom), cc if typ in ("muni", "legi", "cant", "dpmt") else "")
        if cle not in el["cands"]:
            el["cands"][cle] = len(el["liste"])
            el["liste"].append({
                "n": libelle_candidat(typ, nom, prenom, liste, tete, nu),
                "b": BLOCS.index(bloc_de(e, nu, nom, tete)),
                "nu": nu or "",
            })
        el["bv"][(cc, bv)][3] += [el["cands"][cle], voix or 0]

    sortie = {"blocs": BLOCS, "types": TYPES, "elections": [], "grilles": {}, "communes": {}}
    for g, feats in grilles.items():
        sortie["grilles"][g] = [{"c": cc, "b": code, "g": arrondir(geom)} for cc, _, code, geom in feats]
    for cc, geom in communes.items():
        sortie["communes"][cc] = {"n": noms[cc], "g": arrondir(geom, 0.00008)}

    def bureaux(e, cc):
        return {bv: v for (c, bv), v in elections[e]["bv"].items() if c == cc}

    def appariement(bvs, cc, grille):
        """Part des inscrits rattachés à un polygone et part des polygones pourvus."""
        polys = index[grille].get(cc)
        if not polys or not bvs:
            return 0, 0
        total = sum(v[0] for v in bvs.values()) or 1
        part_ins = sum(v[0] for b, v in bvs.items() if b in polys) / total
        part_poly = len(polys & set(bvs)) / len(polys)
        return part_ins, part_poly

    # Scrutins couvrant tout le territoire : ils servent de référence aux scrutins
    # partiels (cantonales, seconds tours), où seule une partie des bureaux vote.
    complets = [e for e in sorted(elections) if e[5:9] in ("pres", "euro", "regi") and e.endswith("t1")]

    def reference(e):
        return min(complets, key=lambda r: (abs(int(r[:4]) - int(e[:4])), r[:4] < e[:4]))

    cache_bv = {}
    for e in sorted(elections):
        el = elections[e]
        par_commune = defaultdict(dict)
        for (cc, bv), v in el["bv"].items():
            par_commune[cc][bv] = v
        ref = e if e in complets else reference(e)
        modes, resultats = {}, {}
        for cc, bvs in par_commune.items():
            if (ref, cc) not in cache_bv:
                cache_bv[(ref, cc)] = bureaux(ref, cc)
            bvs_ref = cache_bv[(ref, cc)]
            meilleur = None
            for g in grilles:
                ins_ref, poly_ref = appariement(bvs_ref, cc, g)
                ins, _ = appariement(bvs, cc, g)
                score = min(ins_ref, poly_ref, ins)
                if meilleur is None or score > meilleur[1]:
                    meilleur = (g, score)
            # Agrégat communal (toujours fourni, utilisé en repli et pour les totaux)
            agg = [0, 0, 0, defaultdict(int)]
            for v in bvs.values():
                for i in range(3):
                    agg[i] += v[i]
                vx = v[3]
                for i in range(0, len(vx), 2):
                    agg[3][vx[i]] += vx[i + 1]
            resultats[cc] = {"_": [agg[0], agg[1], agg[2], [x for k, n in sorted(agg[3].items()) for x in (k, n)]]}
            if meilleur and meilleur[1] >= SEUIL:
                modes[cc] = [meilleur[0], round(meilleur[1], 3)]
                for b, v in bvs.items():
                    resultats[cc][b] = v
            else:
                modes[cc] = ["commune", round(meilleur[1], 3) if meilleur else 0]
        sortie["elections"].append({
            "id": e, "type": e[5:9], "annee": int(e[:4]), "tour": int(e[-1]),
            "cands": el["liste"], "modes": modes, "res": resultats,
        })

    with open(os.path.join(ICI, "data.json"), "w", encoding="utf-8") as f:
        json.dump(sortie, f, ensure_ascii=False, separators=(",", ":"))
    # Page autonome : les données sont injectées dans le gabarit
    with open(os.path.join(ICI, "carte_template.html"), encoding="utf-8") as f:
        gabarit = f.read()
    donnees = json.dumps(sortie, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    with open(os.path.join(ICI, "carte.html"), "w", encoding="utf-8") as f:
        f.write(gabarit.replace("/*__DATA__*/", "const D = " + donnees + ";"))
    print("data.json :", os.path.getsize(os.path.join(ICI, "data.json")) // 1024, "Ko", file=sys.stderr)
    # Bilan de l'appariement
    for el in sortie["elections"]:
        n_bv = sum(1 for m in el["modes"].values() if m[0] != "commune")
        print(el["id"], f"{n_bv}/{len(el['modes'])} communes au bureau",
              "Rennes:", el["modes"].get("35238"), file=sys.stderr)


if __name__ == "__main__":
    main()
