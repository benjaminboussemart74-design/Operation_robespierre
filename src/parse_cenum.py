"""
Parse les HTML des comptes rendus de la commission cenum (vulnérabilités numériques)
téléchargés par download_cenum.sh, et les intègre au pipeline d'extraction.

Produit :
  results/cenum_cloud_latest.json
  results/cenum_cloud_latest.csv
"""

import glob
import json
import os
import re
import sys
from pathlib import Path
from html.parser import HTMLParser

sys.path.insert(0, str(Path(__file__).parent))
from keywords import find_matches, has_any_match

BASE_DIR = Path(__file__).parent.parent
CENUM_DIR = BASE_DIR / "Compte rendu" / "cenum"
RESULTS_DIR = BASE_DIR / "results"


class ANHTMLParser(HTMLParser):
    """Extrait le texte des balises de contenu principal d'une page AN."""

    def __init__(self):
        super().__init__()
        self._in_content = False
        self._depth = 0
        self._parts = []
        self._current_speaker = ""
        self._paragraphs = []  # list of (speaker, text)
        self._current_text = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        classes = attrs_dict.get("class", "")
        if "orateur" in classes or "intervenant" in classes:
            self._flush_paragraph()
            self._in_speaker = True
        if tag in ("p", "div") and any(
            k in classes for k in ("texte", "paragraphe", "contenu", "body-text")
        ):
            self._in_content = True

    def handle_endtag(self, tag):
        pass

    def handle_data(self, data):
        self._parts.append(data)

    def get_text(self) -> str:
        return re.sub(r"\s+", " ", "".join(self._parts)).strip()

    def _flush_paragraph(self):
        pass


def strip_html_simple(html: str) -> str:
    """Strip toutes les balises HTML et retourne le texte brut."""
    s = HTMLParser()
    parts = []

    class Collector(HTMLParser):
        def handle_data(self, data):
            parts.append(data)

    c = Collector()
    try:
        c.feed(html)
    except Exception:
        pass
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def parse_cenum_html(path: str) -> list[dict]:
    """
    Extrait les prises de parole d'un CR cenum HTML.
    Retourne une liste de dict {cr_num, speaker, text, keyword_matches, ...}
    """
    with open(path, encoding="utf-8", errors="replace") as f:
        html = f.read()

    # Numéro du CR depuis le nom de fichier
    fname = os.path.basename(path)
    m = re.search(r"l17cenum2526(\d+)", fname)
    cr_num = int(m.group(1)) if m else 0

    # Extraction de la date
    date_m = re.search(
        r"(\d{1,2}\s+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+\d{4})",
        html, re.IGNORECASE
    )
    date_seance = date_m.group(1) if date_m else ""

    # Extraire le texte brut complet
    full_text = strip_html_simple(html)

    # Segmenter par orateur : pattern "M./Mme PRENOM NOM" suivi de texte
    # Les CRs AN ont généralement "M. Prénom Nom. – Texte..."
    speaker_pattern = re.compile(
        r'((?:M\.|Mme|M)\s+[A-ZÉÈÀÙÂÊÎÔÛÇ][a-zéèàùâêîôûçœæ\-]+'
        r'(?:\s+[A-ZÉÈÀÙÂÊÎÔÛÇ][a-zéèàùâêîôûçœæ\-]+)*'
        r'(?:\s+\([^)]+\))?)\s*[\.–—-]\s*',
        re.UNICODE
    )

    segments = []
    last_end = 0
    current_speaker = "Inconnu"

    for match in speaker_pattern.finditer(full_text):
        if last_end > 0:
            text_segment = full_text[last_end:match.start()].strip()
            if len(text_segment) > 50:
                segments.append((current_speaker, text_segment))
        current_speaker = match.group(1).strip()
        last_end = match.end()

    # Dernier segment
    if last_end > 0:
        remaining = full_text[last_end:].strip()
        if remaining:
            segments.append((current_speaker, remaining))

    # Si aucune segmentation, traiter comme un bloc
    if not segments:
        segments = [("N/A", full_text)]

    results = []
    for speaker, text in segments:
        if not has_any_match(text):
            continue
        matches = find_matches(text)
        results.append({
            "source": "cenum",
            "cr_num": cr_num,
            "date_seance": date_seance,
            "session": "Session 2025-2026",
            "legislature": "17",
            "orateur_nom": speaker,
            "acteur_ref": "",  # non disponible directement depuis HTML
            "texte": text[:2000],
            "keyword_matches": matches,
            "keyword_groups": list(matches.keys()),
            "file": path,
        })

    return results


def extract_all_cenum() -> list[dict]:
    files = sorted(glob.glob(str(CENUM_DIR / "*.html")))
    if not files:
        print(f"[WARN] Aucun fichier HTML trouvé dans {CENUM_DIR}")
        print("       Lance d'abord : bash src/download_cenum.sh")
        return []

    results = []
    for path in files:
        parsed = parse_cenum_html(path)
        results.extend(parsed)
        print(f"  {os.path.basename(path)} → {len(parsed)} passages pertinents")

    return results


def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_csv(data, path):
    import csv
    if not data:
        return
    flat = []
    for r in data:
        row = {k: v for k, v in r.items() if k != "keyword_matches"}
        row["keyword_groups"] = "|".join(row.get("keyword_groups", []))
        flat.append(row)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(flat[0].keys()))
        writer.writeheader()
        writer.writerows(flat)


if __name__ == "__main__":
    print("[INFO] Extraction des CR cenum...")
    results = extract_all_cenum()
    print(f"[INFO] {len(results)} passages pertinents extraits")

    if results:
        RESULTS_DIR.mkdir(exist_ok=True)
        save_json(results, str(RESULTS_DIR / "cenum_cloud_latest.json"))
        save_csv(results, str(RESULTS_DIR / "cenum_cloud_latest.csv"))
        print(f"[OK] Sauvegardé dans results/cenum_cloud_latest.*")

        from collections import Counter
        groups = Counter(g for r in results for g in r["keyword_groups"])
        print("\n[STATS] Thématiques :")
        for g, c in groups.most_common():
            print(f"  {g}: {c}")
