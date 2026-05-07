"""
Extraction des données parlementaires liées à l'éolien pour les députés de la Somme.
Sources : amendements, comptes rendus de séance, questions écrites (si disponibles).
"""

import csv
import json
import glob
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))

from keywords_eolien import find_matches_eolien, has_any_match_eolien

# ── Députés de la Somme ───────────────────────────────────────────────────────
DEPUTES_SOMME = {
    "PA722142": {"prenom": "François",     "nom": "Ruffin",    "groupe": "ECOS",    "circo": "1re"},
    "PA841947": {"prenom": "Zahia",        "nom": "Hamdane",   "groupe": "LFI-NFP", "circo": "2e"},
    "PA841955": {"prenom": "Matthias",     "nom": "Renault",   "groupe": "RN",      "circo": "3e"},
    "PA795778": {"prenom": "Jean-Philippe","nom": "Tanguy",    "groupe": "RN",      "circo": "4e"},
    "PA795786": {"prenom": "Yaël",         "nom": "Ménaché",   "groupe": "RN",      "circo": "5e"},
}


# ── Utilitaires HTML ──────────────────────────────────────────────────────────
class _Stripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self._p = []
    def handle_data(self, d):
        self._p.append(d)
    def text(self):
        return re.sub(r"\s+", " ", "".join(self._p)).strip()


def strip_html(raw):
    if not raw or not isinstance(raw, str):
        return ""
    s = _Stripper()
    try:
        s.feed(raw)
        return s.text()
    except Exception:
        return re.sub(r"<[^>]+>", " ", raw).strip()


# ── Amendements ───────────────────────────────────────────────────────────────
def _get(obj, *keys, default=None):
    for k in keys:
        if not isinstance(obj, dict):
            return default
        obj = obj.get(k, default)
    return obj


def extract_amendments_eolien() -> list[dict]:
    results = []
    pattern = str(BASE_DIR / "Amendements" / "**" / "*.json")
    for path in glob.glob(pattern, recursive=True):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        amend = data.get("amendement", {})
        signataires = amend.get("signataires", {})
        auteur = signataires.get("auteur", {})
        acteur_ref = auteur.get("acteurRef", "")
        if not isinstance(acteur_ref, str):
            acteur_ref = ""

        cosign = signataires.get("cosignataires", {}).get("acteurRef", [])
        if isinstance(cosign, str):
            cosign = [cosign]

        # Filtre Somme : auteur OU cosignataire
        refs_presents = {acteur_ref} | set(cosign)
        somme_refs = refs_presents & set(DEPUTES_SOMME)
        if not somme_refs:
            continue

        corps = amend.get("corps", {}).get("contenuAuteur", {})
        dispositif = strip_html(corps.get("dispositif", ""))
        expose = strip_html(corps.get("exposeSommaire", ""))
        full = f"{dispositif} {expose}"

        if not has_any_match_eolien(full):
            continue

        matches = find_matches_eolien(full)

        for ref in somme_refs:
            dep = DEPUTES_SOMME[ref]
            role = "Auteur" if ref == acteur_ref else "Cosignataire"
            results.append({
                "source": "Amendement",
                "acteur_ref": ref,
                "prenom": dep["prenom"],
                "nom": dep["nom"],
                "groupe": dep["groupe"],
                "circo": dep["circo"],
                "role": role,
                "uid": amend.get("uid", ""),
                "numero": _get(amend, "identification", "numeroLong", default=""),
                "texte_ref": amend.get("texteLegislatifRef", ""),
                "date": _get(amend, "cycleDeVie", "dateDepot", default=""),
                "sort": _get(amend, "cycleDeVie", "etatDesTraitements", "etat", "libelle", default=""),
                "extrait": expose[:400] or dispositif[:400],
                "themes": sorted(matches.keys()),
                "keyword_matches": matches,
            })
    return results


# ── Comptes rendus de séance ──────────────────────────────────────────────────
NS = "http://schemas.assemblee-nationale.fr/referentiel"


def _xt(elem):
    return re.sub(r"\s+", " ", "".join(elem.itertext())).strip() if elem is not None else ""


def extract_cr_eolien() -> list[dict]:
    import xml.etree.ElementTree as ET
    results = []
    pattern = str(BASE_DIR / "Compte rendu" / "compteRendu" / "*.xml")

    for path in glob.glob(pattern):
        try:
            tree = ET.parse(path)
        except ET.ParseError:
            continue
        root = tree.getroot()

        uid = _xt(root.find(f"{{{NS}}}uid"))
        meta = root.find(f"{{{NS}}}metadonnees")
        date = _xt(meta.find(f"{{{NS}}}dateSeanceJour")) if meta is not None else ""

        for p in root.findall(f".//{{{NS}}}paragraphe"):
            orateurs = p.find(f"{{{NS}}}orateurs")
            if orateurs is None:
                continue
            raw = _xt(orateurs)
            id_match = re.search(r"\b(\d{5,6})\b", raw)
            acteur_id = ("PA" + id_match.group(1)) if id_match else ""
            name = re.sub(r"\s+", " ", raw[:id_match.start()]).strip() if id_match else raw.strip()

            if acteur_id not in DEPUTES_SOMME:
                continue

            texte = _xt(p.find(f"{{{NS}}}texte"))
            if not has_any_match_eolien(texte):
                continue

            matches = find_matches_eolien(texte)
            dep = DEPUTES_SOMME[acteur_id]
            results.append({
                "source": "Séance plénière",
                "acteur_ref": acteur_id,
                "prenom": dep["prenom"],
                "nom": dep["nom"],
                "groupe": dep["groupe"],
                "circo": dep["circo"],
                "role": "Intervenant",
                "uid": uid,
                "date": date,
                "extrait": texte[:400],
                "themes": sorted(matches.keys()),
                "keyword_matches": matches,
            })

    return results


# ── Questions écrites (si téléchargées) ──────────────────────────────────────
def extract_qe_eolien() -> list[dict]:
    """Parse les questions écrites JSON si le fichier est présent."""
    qe_dir = BASE_DIR / "Questions_ecrites"
    candidates = list(qe_dir.glob("**/*.json")) if qe_dir.exists() else []
    if not candidates:
        return []

    results = []
    for path in candidates:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        # Format individuel : {"question": {...}} ou liste ou dict direct
        if isinstance(data, dict) and "question" in data:
            questions = [data["question"]]
        elif isinstance(data, list):
            questions = data
        else:
            questions = data.get("questions", [data])
        if isinstance(questions, dict):
            questions = [questions]

        for q in questions:
            auteur = q.get("auteur", {})
            if isinstance(auteur, dict):
                auteur_ref = auteur.get("acteurRef", "")
            else:
                auteur_ref = q.get("auteurRef", "")
            if not isinstance(auteur_ref, str):
                auteur_ref = ""
            if auteur_ref not in DEPUTES_SOMME:
                continue

            texte_q = strip_html(q.get("texteQuestion", q.get("texte", q.get("corps", ""))))
            texte_r = strip_html(q.get("texteReponse", q.get("reponse", "")))
            full = f"{texte_q} {texte_r}"

            if not has_any_match_eolien(full):
                continue

            matches = find_matches_eolien(full)
            dep = DEPUTES_SOMME[auteur_ref]
            results.append({
                "source": "Question écrite",
                "acteur_ref": auteur_ref,
                "prenom": dep["prenom"],
                "nom": dep["nom"],
                "groupe": dep["groupe"],
                "circo": dep["circo"],
                "role": "Auteur",
                "uid": q.get("uid", q.get("numero", "")),
                "date": q.get("dateDepot", q.get("date", "")),
                "ministere": q.get("ministereInterroge", {}).get("libelle", "") if isinstance(q.get("ministereInterroge"), dict) else "",
                "extrait": texte_q[:400],
                "themes": sorted(matches.keys()),
                "keyword_matches": matches,
            })

    return results


# ── Rapport de présentation ───────────────────────────────────────────────────
THEME_LABELS = {
    "eolien_infrastructure": "Infrastructure éolienne",
    "eolien_administratif":  "Réglementation & projets",
    "eolien_impacts":        "Impacts & nuisances",
    "eolien_politique":      "Politique énergétique",
}

SOURCE_LABELS = {
    "Amendement":      "Amend.",
    "Séance plénière": "Séance",
    "Question écrite": "QE",
}


def build_presentation(all_results: list[dict]) -> dict:
    """Construit les structures pour l'export de présentation."""
    from collections import defaultdict

    # ── Tableau de synthèse par député ────────────────────────────────────────
    summary = {}
    for ref, dep in DEPUTES_SOMME.items():
        items = [r for r in all_results if r["acteur_ref"] == ref]
        by_source = defaultdict(list)
        for r in items:
            by_source[r["source"]].append(r)

        theme_counts = defaultdict(int)
        for r in items:
            for t in r.get("themes", []):
                theme_counts[t] += 1

        top_theme = max(theme_counts, key=theme_counts.get) if theme_counts else "—"

        summary[ref] = {
            "Député·e":      f"{dep['prenom']} {dep['nom']}",
            "Groupe":        dep["groupe"],
            "Circo Somme":   dep["circo"],
            "Amendements":   len(by_source["Amendement"]),
            "Séances":       len(by_source["Séance plénière"]),
            "QE":            len(by_source["Question écrite"]),
            "Total":         len(items),
            "Thème dominant":THEME_LABELS.get(top_theme, top_theme),
            "Position déduite": _infer_position(items),
        }

    # ── Détail par entrée ─────────────────────────────────────────────────────
    detail = []
    for r in sorted(all_results, key=lambda x: (x["nom"], x.get("date", ""))):
        detail.append({
            "Député·e":     f"{r['prenom']} {r['nom']}",
            "Groupe":       r["groupe"],
            "Circo":        r["circo"],
            "Source":       r["source"],
            "Rôle":         r.get("role", ""),
            "Date":         r.get("date", ""),
            "Référence":    r.get("uid", r.get("numero", "")),
            "Thèmes":       " | ".join(THEME_LABELS.get(t, t) for t in r.get("themes", [])),
            "Extrait":      r.get("extrait", "")[:300],
        })

    return {"synthese": list(summary.values()), "detail": detail}


def _infer_position(items: list[dict]) -> str:
    """Déduit grossièrement la position du député sur l'éolien."""
    if not items:
        return "—"
    text = " ".join(r.get("extrait", "") for r in items).lower()
    contre = sum(1 for w in ["opposition", "moratoire", "nuisance", "supprimer", "contre", "refus",
                              "stop", "impact négatif", "riverains", "dégradation", "artificialisation"] if w in text)
    pour = sum(1 for w in ["développer", "favoriser", "renouvelable", "transition", "objectif",
                            "atteindre", "déploiement", "filière"] if w in text)
    if contre > pour + 1:
        return "⚠ Critique / Opposé"
    if pour > contre + 1:
        return "✓ Favorable"
    return "~ Nuancé / Mixte"


# ── Export ────────────────────────────────────────────────────────────────────
def save_presentation(pres: dict, results_dir: Path):
    results_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Synthèse
    _write_csv(pres["synthese"], results_dir / "eolien_somme_synthese_latest.csv")
    _write_csv(pres["synthese"], results_dir / f"eolien_somme_synthese_{ts}.csv")

    # Détail
    _write_csv(pres["detail"], results_dir / "eolien_somme_detail_latest.csv")
    _write_csv(pres["detail"], results_dir / f"eolien_somme_detail_{ts}.csv")

    # JSON complet
    with open(results_dir / "eolien_somme_latest.json", "w", encoding="utf-8") as f:
        json.dump({"synthese": pres["synthese"], "detail": pres["detail"]}, f,
                  ensure_ascii=False, indent=2)


def _write_csv(rows: list[dict], path):
    if not rows:
        with open(path, "w", encoding="utf-8-sig") as f:
            f.write("(aucun résultat)\n")
        return
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("═" * 60)
    print("EXTRACTION ÉOLIEN — DÉPUTÉS DE LA SOMME")
    print("═" * 60)

    print("\n[1/3] Amendements...")
    ams = extract_amendments_eolien()
    print(f"      → {len(ams)} entrées")

    print("[2/3] Comptes rendus de séance...")
    crs = extract_cr_eolien()
    print(f"      → {len(crs)} entrées")

    print("[3/3] Questions écrites...")
    qes = extract_qe_eolien()
    print(f"      → {len(qes)} entrées")
    if not qes:
        print("      (fichier absent — lancer download_all.sh pour les télécharger)")

    all_results = ams + crs + qes

    print(f"\n{'─'*60}")
    print(f"TOTAL : {len(all_results)} occurrences éolien")
    print(f"{'─'*60}")

    pres = build_presentation(all_results)

    # Affichage console
    print("\n📊 TABLEAU DE SYNTHÈSE\n")
    header = ["Député·e", "Groupe", "Circo", "Amend.", "Séances", "QE", "Total", "Thème dominant", "Position"]
    widths  = [25, 10, 6, 7, 7, 4, 6, 30, 22]
    row_fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    sep = "  ".join("─" * w for w in widths)
    print(row_fmt.format(*header))
    print(sep)
    for s in sorted(pres["synthese"], key=lambda x: -x["Total"]):
        print(row_fmt.format(
            s["Député·e"], s["Groupe"], s["Circo Somme"],
            s["Amendements"], s["Séances"], s["QE"], s["Total"],
            s["Thème dominant"][:30], s["Position déduite"]
        ))

    save_presentation(pres, BASE_DIR / "results")
    print(f"\n✓ Exports : results/eolien_somme_synthese_latest.csv")
    print(f"            results/eolien_somme_detail_latest.csv")
