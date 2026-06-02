"""
Extrait toutes les interventions, amendements et questions écrites
d'un député donné, sans filtre thématique.

Usage : python3 src/extract_depute.py --acteur PA793940 [--nom "Cazenave"]
"""

import csv
import glob
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
RESULTS_DIR = BASE_DIR / "results"

NS = "http://schemas.assemblee-nationale.fr/referentiel"


# ── HTML strip ────────────────────────────────────────────────────────────────
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
def extract_amendments(acteur_ref: str) -> list[dict]:
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
        ref = auteur.get("acteurRef", "")
        if not isinstance(ref, str):
            ref = ""

        cosign = signataires.get("cosignataires", {}).get("acteurRef", [])
        if isinstance(cosign, str):
            cosign = [cosign]

        refs = {ref} | set(cosign)
        if acteur_ref not in refs:
            continue

        corps = amend.get("corps", {}).get("contenuAuteur", {})
        dispositif = strip_html(corps.get("dispositif", ""))
        expose = strip_html(corps.get("exposeSommaire", ""))

        role = "Auteur" if ref == acteur_ref else "Cosignataire"
        uid = amend.get("uid", "")
        results.append({
            "source": "Amendement",
            "role": role,
            "uid": uid,
            "url": f"https://www.assemblee-nationale.fr/dyn/17/amendements/{uid}" if uid else "",
            "numero": (amend.get("identification", {}) or {}).get("numeroLong", ""),
            "texte_ref": amend.get("texteLegislatifRef", ""),
            "date": ((amend.get("cycleDeVie", {}) or {}).get("dateDepot", "")),
            "sort": (((amend.get("cycleDeVie", {}) or {})
                      .get("etatDesTraitements", {}) or {})
                     .get("etat", {}) or {}).get("libelle", ""),
            "dispositif": dispositif[:500],
            "expose": expose[:800],
        })
    return results


# ── Comptes rendus ────────────────────────────────────────────────────────────
def _xt(elem):
    return re.sub(r"\s+", " ", "".join(elem.itertext())).strip() if elem is not None else ""

def extract_seances(acteur_ref: str) -> list[dict]:
    results = []
    pattern = str(BASE_DIR / "Compte rendu" / "compteRendu" / "*.xml")
    for path in glob.glob(pattern):
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            continue

        uid = _xt(root.find(f"{{{NS}}}uid"))
        meta = root.find(f"{{{NS}}}metadonnees")
        date = _xt(meta.find(f"{{{NS}}}dateSeanceJour")) if meta is not None else ""

        for p in root.findall(f".//{{{NS}}}paragraphe"):
            o = p.find(f"{{{NS}}}orateurs")
            if o is None:
                continue
            raw = _xt(o)
            m = re.search(r"\b(\d{5,6})\b", raw)
            if not m or ("PA" + m.group(1)) != acteur_ref:
                continue

            name = re.sub(r"\s+", " ", raw[:m.start()]).strip()
            role = re.sub(r"\s+", " ", raw[m.end():]).strip()
            texte = _xt(p.find(f"{{{NS}}}texte"))
            if not texte:
                continue

            slug = uid[len("CRSANR5"):].lower() if uid.startswith("CRSANR5") else uid.lower()
            results.append({
                "source": "Séance plénière",
                "role": role or "Intervenant",
                "uid": uid,
                "url": f"https://www.assemblee-nationale.fr/dyn/17/comptes-rendus/seance/{slug}",
                "date": date,
                "orateur": name,
                "texte": texte[:1000],
            })
    return results


# ── Questions écrites ─────────────────────────────────────────────────────────
def extract_qe(acteur_ref: str) -> list[dict]:
    qe_dir = BASE_DIR / "Questions_ecrites"
    candidates = list(qe_dir.glob("**/*.json")) if qe_dir.exists() else []
    results = []
    for path in candidates:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        q = data.get("question", data) if isinstance(data, dict) else {}
        auteur = q.get("auteur", {})
        identite = auteur.get("identite", {}) if isinstance(auteur, dict) else {}
        ref = identite.get("acteurRef", "") if isinstance(identite, dict) else ""
        if ref != acteur_ref:
            continue

        tq = q.get("textesQuestion", {})
        tq_obj = tq.get("texteQuestion", {}) if isinstance(tq, dict) else {}
        texte_q = strip_html(tq_obj.get("texte", "") if isinstance(tq_obj, dict) else "")

        tr = q.get("textesReponse")
        tr_obj = tr.get("texteReponse", {}) if isinstance(tr, dict) else {}
        texte_r = strip_html(tr_obj.get("texte", "") if isinstance(tr_obj, dict) else "")

        uid = q.get("uid", "")
        ministere = (q.get("minInt", {}) or {}).get("developpe", "")

        date_jo = (tq_obj.get("infoJO", {}) or {}).get("dateJO", "") if isinstance(tq_obj, dict) else ""

        results.append({
            "source": "Question écrite",
            "role": "Auteur",
            "uid": uid,
            "url": f"https://www.assemblee-nationale.fr/dyn/17/questions/{uid}" if uid else "",
            "date": date_jo,
            "ministere": ministere,
            "question": texte_q[:800],
            "reponse": texte_r[:800] if texte_r else "(pas de réponse)",
        })
    return results


# ── Export ────────────────────────────────────────────────────────────────────
def save_results(all_results: list[dict], nom: str):
    RESULTS_DIR.mkdir(exist_ok=True)
    slug = re.sub(r"\s+", "_", nom.lower())
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # JSON
    json_path = RESULTS_DIR / f"{slug}_latest.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    # CSV (une feuille par source)
    for src in ("Amendement", "Séance plénière", "Question écrite"):
        rows = [r for r in all_results if r["source"] == src]
        if not rows:
            continue
        src_slug = src.lower().replace(" ", "_").replace("é", "e").replace("è", "e")
        csv_path = RESULTS_DIR / f"{slug}_{src_slug}_latest.csv"
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"  → {csv_path.name} ({len(rows)} lignes)")

    print(f"  → {json_path.name}")


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--acteur", required=True, help="ex: PA793940")
    parser.add_argument("--nom", default="", help="ex: Thomas Cazenave")
    args = parser.parse_args()

    acteur_ref = args.acteur
    nom = args.nom or acteur_ref

    print("═" * 60)
    print(f"EXTRACTION — {nom.upper()} ({acteur_ref})")
    print("═" * 60)

    print("\n[1/3] Amendements...")
    ams = extract_amendments(acteur_ref)
    print(f"      → {len(ams)} amendements")

    print("[2/3] Séances plénières...")
    crs = extract_seances(acteur_ref)
    print(f"      → {len(crs)} interventions")

    print("[3/3] Questions écrites...")
    qes = extract_qe(acteur_ref)
    print(f"      → {len(qes)} questions")

    all_results = ams + crs + qes
    print(f"\n{'─'*60}")
    print(f"TOTAL : {len(all_results)} entrées")
    print(f"{'─'*60}\n")

    save_results(all_results, nom)
    print("\nTerminé.")
