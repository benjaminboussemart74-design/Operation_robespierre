"""
Extraction des amendements liés au cloud / data center / souveraineté numérique.
Parcourt tous les fichiers JSON sous Amendements/ et extrait les occurrences pertinentes.
"""

import json
import re
import glob
import os
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

from keywords import find_matches, has_any_match


class HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self._parts = []

    def handle_data(self, data):
        self._parts.append(data)

    def get_text(self) -> str:
        return " ".join(self._parts)


def strip_html(raw: str) -> str:
    if not raw or not isinstance(raw, str):
        return ""
    s = HTMLStripper()
    try:
        s.feed(raw)
        return re.sub(r"\s+", " ", s.get_text()).strip()
    except Exception:
        return re.sub(r"<[^>]+>", " ", raw).strip()


def _get(obj, *keys, default=None):
    for key in keys:
        if not isinstance(obj, dict):
            return default
        obj = obj.get(key, default)
    return obj


def parse_amendment(path: str) -> Optional[dict]:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None

    amend = data.get("amendement", {})

    uid = amend.get("uid", "")
    legislature = amend.get("legislature", "")
    texte_ref = amend.get("texteLegislatifRef", "")

    # Identification
    ident = amend.get("identification", {})
    numero = ident.get("numeroLong", "")
    organe = ident.get("prefixeOrganeExamen", "")

    # Signataires
    signataires = amend.get("signataires", {})
    auteur = signataires.get("auteur", {})
    acteur_ref = auteur.get("acteurRef", "")
    if not isinstance(acteur_ref, str):
        acteur_ref = ""
    groupe_ref = auteur.get("groupePolitiqueRef", "")
    if not isinstance(groupe_ref, str):
        groupe_ref = ""
    signataires_libelle = signataires.get("libelle", "")

    cosignataires = signataires.get("cosignataires", {})
    cosign_refs = cosignataires.get("acteurRef", [])
    if isinstance(cosign_refs, str):
        cosign_refs = [cosign_refs]

    # Corps
    corps = amend.get("corps", {})
    contenu = corps.get("contenuAuteur", {})
    dispositif_html = contenu.get("dispositif", "")
    expose_html = contenu.get("exposeSommaire", "")

    dispositif = strip_html(dispositif_html)
    expose = strip_html(expose_html)

    full_text = f"{dispositif} {expose}".strip()

    if not has_any_match(full_text):
        return None

    matches = find_matches(full_text)

    # Sort info
    sort_info = amend.get("cycleDeVie", {})
    sort_libelle = _get(amend, "cycleDeVie", "sort", "libelle") or ""
    date_depot = _get(amend, "cycleDeVie", "dateDepot") or ""

    return {
        "source": "amendement",
        "uid": uid,
        "numero": numero,
        "legislature": legislature,
        "organe": organe,
        "texte_ref": texte_ref,
        "acteur_ref": acteur_ref,
        "groupe_ref": groupe_ref,
        "cosignataires_refs": cosign_refs,
        "signataires_libelle": signataires_libelle,
        "dispositif": dispositif[:500],
        "expose_sommaire": expose[:1000],
        "full_text_len": len(full_text),
        "date_depot": date_depot,
        "sort": sort_libelle,
        "keyword_matches": matches,
        "keyword_groups": list(matches.keys()),
        "file": path,
    }


def extract_all(base_dir: str, depute_filter: Optional[set] = None) -> list[dict]:
    """
    Parcourt tous les amendements JSON.
    depute_filter: ensemble d'acteurRef (ex: {"PA793672"}) pour filtrer, ou None pour tout garder.
    """
    pattern = os.path.join(base_dir, "Amendements", "**", "*.json")
    files = glob.glob(pattern, recursive=True)

    results = []
    for path in files:
        r = parse_amendment(path)
        if r is None:
            continue
        if depute_filter is not None:
            # Keep if auteur or any cosignataire matches filter
            refs = {r["acteur_ref"]} | set(r["cosignataires_refs"])
            if not refs.intersection(depute_filter):
                continue
        results.append(r)

    return results
