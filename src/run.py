"""
Script principal d'extraction.

Usage:
    python run.py                          # tout le corpus
    python run.py --deputes PA793672 PA840119  # filtrage par acteurRef
    python run.py --deputes-csv ../deputes-active.csv --noms "Dupont,Martin"
"""

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent

sys.path.insert(0, str(Path(__file__).parent))

import extract_amendments
import extract_comptes_rendus


def load_deputes_csv(csv_path: str) -> dict[str, dict]:
    """Return dict acteurRef -> row."""
    deputes = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            deputes[row["id"]] = row
    return deputes


def enrich_with_depute_info(results: list[dict], deputes_by_id: dict) -> list[dict]:
    for r in results:
        ref = r.get("acteur_ref", "")
        info = deputes_by_id.get(ref, {})
        r["depute_nom"] = info.get("nom", "")
        r["depute_prenom"] = info.get("prenom", "")
        r["depute_groupe"] = info.get("groupe", "")
        r["depute_groupe_abrev"] = info.get("groupeAbrev", "")
        r["depute_departement"] = info.get("departementNom", "")
    return results


def save_json(data: list[dict], path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_csv(data: list[dict], path: str):
    if not data:
        return
    # Flatten keyword_groups to string, drop complex fields for CSV
    flat = []
    for r in data:
        row = {k: v for k, v in r.items() if k not in ("keyword_matches",)}
        row["keyword_groups"] = "|".join(row.get("keyword_groups", []))
        if "cosignataires_refs" in row:
            row["cosignataires_refs"] = "|".join(row["cosignataires_refs"])
        flat.append(row)
    fieldnames = list(flat[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(flat)


def build_depute_summary(results: list[dict], deputes_by_id: dict) -> list[dict]:
    """Aggregate results by deputy."""
    from collections import defaultdict
    summary: dict[str, dict] = {}

    for r in results:
        ref = r.get("acteur_ref", "") or "inconnu"
        if ref not in summary:
            info = deputes_by_id.get(ref, {})
            summary[ref] = {
                "acteur_ref": ref,
                "nom": info.get("nom", r.get("depute_nom", "")),
                "prenom": info.get("prenom", r.get("depute_prenom", "")),
                "groupe": info.get("groupe", r.get("depute_groupe", "")),
                "groupe_abrev": info.get("groupeAbrev", ""),
                "departement": info.get("departementNom", ""),
                "nb_amendements": 0,
                "nb_prises_de_parole": 0,
                "groupes_thematiques": set(),
                "extraits": [],
            }
        entry = summary[ref]
        if r["source"] == "amendement":
            entry["nb_amendements"] += 1
        else:
            entry["nb_prises_de_parole"] += 1
        entry["groupes_thematiques"].update(r.get("keyword_groups", []))
        # Keep short excerpt
        text = r.get("expose_sommaire") or r.get("texte", "")
        if text:
            entry["extraits"].append({
                "source": r["source"],
                "date": r.get("date_depot") or r.get("date_seance", ""),
                "extrait": text[:300],
                "themes": r.get("keyword_groups", []),
            })

    # Serialize sets
    for entry in summary.values():
        entry["groupes_thematiques"] = sorted(entry["groupes_thematiques"])
        entry["nb_total"] = entry["nb_amendements"] + entry["nb_prises_de_parole"]

    identified = [e for e in summary.values() if e["acteur_ref"] not in ("", "inconnu")]
    unidentified = [e for e in summary.values() if e["acteur_ref"] in ("", "inconnu")]
    return sorted(identified, key=lambda x: -x["nb_total"]) + unidentified


def main():
    parser = argparse.ArgumentParser(description="Extraction données parlementaires cloud/souveraineté")
    parser.add_argument("--deputes", nargs="*", help="Liste d'acteurRef (ex: PA793672 PA840119)")
    parser.add_argument("--deputes-csv", default=str(BASE_DIR / "deputes-active.csv"),
                        help="Chemin vers deputes-active.csv")
    parser.add_argument("--noms", help="Noms de famille séparés par virgule pour filtrage")
    parser.add_argument("--output-dir", default=str(BASE_DIR / "results"),
                        help="Répertoire de sortie")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load deputés reference
    deputes_by_id = {}
    if os.path.exists(args.deputes_csv):
        deputes_by_id = load_deputes_csv(args.deputes_csv)
        print(f"[INFO] {len(deputes_by_id)} députés chargés depuis {args.deputes_csv}")

    # Build filter set
    depute_filter = None
    if args.deputes:
        depute_filter = set(args.deputes)
    elif args.noms:
        noms = {n.strip().lower() for n in args.noms.split(",")}
        depute_filter = {
            ref for ref, info in deputes_by_id.items()
            if info.get("nom", "").lower() in noms
        }
        print(f"[INFO] Filtre par nom : {depute_filter}")

    if depute_filter is not None:
        print(f"[INFO] Filtre actif : {len(depute_filter)} député(s)")
    else:
        print("[INFO] Extraction globale (tous les députés)")

    # Extract amendments
    print("[INFO] Extraction des amendements...")
    amendments = extract_amendments.extract_all(str(BASE_DIR), depute_filter=depute_filter)
    amendments = enrich_with_depute_info(amendments, deputes_by_id)
    print(f"[INFO] {len(amendments)} amendements pertinents trouvés")

    # Extract comptes rendus
    print("[INFO] Extraction des comptes rendus de séance...")
    prises = extract_comptes_rendus.extract_all(str(BASE_DIR), depute_filter=depute_filter)
    prises = enrich_with_depute_info(prises, deputes_by_id)
    print(f"[INFO] {len(prises)} prises de parole pertinentes trouvées")

    all_results = amendments + prises

    # Summary by deputy
    summary = build_depute_summary(all_results, deputes_by_id)

    # Save outputs
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_json(amendments, str(output_dir / f"amendements_cloud_{ts}.json"))
    save_json(prises, str(output_dir / f"prises_de_parole_cloud_{ts}.json"))
    save_json(summary, str(output_dir / f"synthese_deputes_{ts}.json"))
    save_csv(amendments, str(output_dir / f"amendements_cloud_{ts}.csv"))
    save_csv(prises, str(output_dir / f"prises_de_parole_cloud_{ts}.csv"))

    # Also save stable filenames for easy access
    save_json(amendments, str(output_dir / "amendements_cloud_latest.json"))
    save_json(prises, str(output_dir / "prises_de_parole_cloud_latest.json"))
    save_json(summary, str(output_dir / "synthese_deputes_latest.json"))
    save_csv(amendments, str(output_dir / "amendements_cloud_latest.csv"))
    save_csv(prises, str(output_dir / "prises_de_parole_cloud_latest.csv"))

    print(f"\n[OK] Résultats sauvegardés dans {output_dir}/")
    print(f"  - {len(amendments)} amendements")
    print(f"  - {len(prises)} prises de parole")
    print(f"  - {len(summary)} députés impliqués")

    # Quick stats
    from collections import Counter
    groups_counter: Counter = Counter()
    for r in all_results:
        for g in r.get("keyword_groups", []):
            groups_counter[g] += 1
    print("\n[STATS] Répartition par thématique :")
    for theme, count in groups_counter.most_common():
        print(f"  {theme}: {count}")

    return all_results, summary


if __name__ == "__main__":
    main()
