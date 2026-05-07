"""
Parse le fichier Agenda.json (réunions 17e législature) extrait de Agenda.json.zip.
Filtre les réunions liées au cloud / data center / souveraineté numérique,
et repère spécifiquement la commission cenum.

Produit :
  results/reunions_cloud_latest.json
  results/reunions_cloud_latest.csv
"""

import glob
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from keywords import find_matches, has_any_match

BASE_DIR = Path(__file__).parent.parent
REUNIONS_DIR = BASE_DIR / "Réunions"
RESULTS_DIR = BASE_DIR / "results"

# Identifiant organe de la commission cenum (à vérifier dans les données)
CENUM_KEYWORDS = {"cenum", "vulnerabilites", "vulnérabilités", "numerique", "numérique",
                  "dependances", "dépendances", "structurelles", "independance", "indépendance"}


def find_agenda_file() -> str | None:
    candidates = list(REUNIONS_DIR.glob("*.json")) + list(REUNIONS_DIR.glob("**/*.json"))
    if not candidates:
        return None
    # Prefer the largest file (full dataset)
    return str(max(candidates, key=lambda p: p.stat().st_size))


def is_cenum(reunion: dict) -> bool:
    """Détecte si une réunion appartient à la commission cenum."""
    def _all_text(obj) -> str:
        if isinstance(obj, str):
            return obj.lower()
        if isinstance(obj, dict):
            return " ".join(_all_text(v) for v in obj.values())
        if isinstance(obj, list):
            return " ".join(_all_text(v) for v in obj)
        return ""

    text = _all_text(reunion)
    # Check organe ref or uid
    uid = str(reunion.get("uid", "")).lower()
    organe = str(reunion.get("organeRef", "")).lower()

    if "cenum" in uid or "cenum" in organe:
        return True
    # Check title/agenda
    return sum(1 for k in CENUM_KEYWORDS if k in text) >= 2


def parse_agenda(path: str) -> tuple[list[dict], list[dict]]:
    """
    Returns (cenum_reunions, cloud_reunions) where cloud_reunions matched keywords.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # Handle both list and wrapped formats
    if isinstance(data, list):
        reunions = data
    elif isinstance(data, dict):
        # Try common wrapper keys
        for key in ("reunions", "Reunions", "agenda", "Agenda", "export"):
            if key in data:
                reunions = data[key]
                if isinstance(reunions, dict):
                    # Nested: {"reunion": [...]}
                    for k2 in ("reunion", "Reunion"):
                        if k2 in reunions:
                            reunions = reunions[k2]
                            break
                break
        else:
            # Try first list value
            for v in data.values():
                if isinstance(v, list):
                    reunions = v
                    break
            else:
                reunions = [data]

    if not isinstance(reunions, list):
        reunions = [reunions]

    print(f"[INFO] {len(reunions)} réunions chargées")

    cenum = []
    cloud = []

    for r in reunions:
        if not isinstance(r, dict):
            continue

        # Extract flat text for keyword matching
        def flatten(obj) -> str:
            if isinstance(obj, str):
                return obj
            if isinstance(obj, dict):
                return " ".join(flatten(v) for v in obj.values())
            if isinstance(obj, list):
                return " ".join(flatten(v) for v in obj)
            return str(obj) if obj else ""

        full_text = flatten(r)

        # cenum detection
        if is_cenum(r):
            cenum.append({
                "source": "reunion_cenum",
                "uid": r.get("uid", ""),
                "date": r.get("dateReunion", r.get("dateSeance", r.get("timestampDebut", ""))),
                "libelle": r.get("libelle", r.get("titre", "")),
                "organe": r.get("organeRef", r.get("idOrgane", "")),
                "ordre_du_jour": str(r.get("odj", r.get("ordre_du_jour", r.get("pointsOdj", "")))),
                "lieu": r.get("lieu", ""),
                "raw": r,
            })

        # keyword matching on agenda/title
        if has_any_match(full_text):
            matches = find_matches(full_text)
            cloud.append({
                "source": "reunion",
                "uid": r.get("uid", ""),
                "date": r.get("dateReunion", r.get("dateSeance", r.get("timestampDebut", ""))),
                "libelle": r.get("libelle", r.get("titre", "")),
                "organe": r.get("organeRef", r.get("idOrgane", "")),
                "ordre_du_jour": str(r.get("odj", r.get("ordre_du_jour", r.get("pointsOdj", ""))))[:500],
                "keyword_matches": matches,
                "keyword_groups": list(matches.keys()),
                "raw": r,
            })

    return cenum, cloud


def save_json(data, path):
    # Remove "raw" field for cleaner output
    clean = [{k: v for k, v in r.items() if k != "raw"} for r in data]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)


def save_csv(data, path):
    import csv
    if not data:
        return
    flat = []
    for r in data:
        row = {k: v for k, v in r.items() if k not in ("raw", "keyword_matches")}
        if "keyword_groups" in row:
            row["keyword_groups"] = "|".join(row["keyword_groups"])
        flat.append(row)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(flat[0].keys()))
        writer.writeheader()
        writer.writerows(flat)


def inspect_structure(path: str):
    """Affiche la structure du JSON pour debug."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        print(f"Format : liste de {len(data)} éléments")
        if data:
            print("Premier élément (clés) :", list(data[0].keys()) if isinstance(data[0], dict) else type(data[0]))
    elif isinstance(data, dict):
        print("Format : dict avec clés :", list(data.keys())[:10])


if __name__ == "__main__":
    agenda_path = find_agenda_file()
    if not agenda_path:
        print(f"[ERROR] Aucun fichier JSON trouvé dans {REUNIONS_DIR}")
        print("        Lance d'abord : bash src/download_all.sh")
        sys.exit(1)

    print(f"[INFO] Parsing {agenda_path}")
    inspect_structure(agenda_path)

    cenum, cloud = parse_agenda(agenda_path)

    print(f"[INFO] {len(cenum)} réunions cenum identifiées")
    print(f"[INFO] {len(cloud)} réunions avec keywords cloud/souveraineté")

    RESULTS_DIR.mkdir(exist_ok=True)
    save_json(cenum, str(RESULTS_DIR / "reunions_cenum_latest.json"))
    save_json(cloud, str(RESULTS_DIR / "reunions_cloud_latest.json"))
    save_csv(cenum, str(RESULTS_DIR / "reunions_cenum_latest.csv"))
    save_csv(cloud, str(RESULTS_DIR / "reunions_cloud_latest.csv"))

    print(f"[OK] Sauvegardé dans results/")

    if cenum:
        print("\n[CENUM] Premières réunions :")
        for r in cenum[:5]:
            print(f"  {r['date']} | {r['libelle'][:80]}")
