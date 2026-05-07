"""
Extraction des prises de parole en séance liées au cloud / data center / souveraineté numérique.
Parcourt tous les fichiers XML sous Compte rendu/compteRendu/.
"""

import xml.etree.ElementTree as ET
import glob
import os
import re
from pathlib import Path
from typing import Optional

from keywords import find_matches, has_any_match

NS = "http://schemas.assemblee-nationale.fr/referentiel"


def _tag(name: str) -> str:
    return f"{{{NS}}}{name}"


def _text_of(elem) -> str:
    if elem is None:
        return ""
    return re.sub(r"\s+", " ", "".join(elem.itertext())).strip()


def parse_orateur(orateurs_elem) -> tuple[str, str, str]:
    """Return (name, acteur_id, role) from <orateurs> element."""
    if orateurs_elem is None:
        return "", "", ""

    orateur = orateurs_elem.find(_tag("orateur"))
    raw = _text_of(orateur if orateur is not None else orateurs_elem)

    # Extrait l'ID numérique (5-6 chiffres) où qu'il soit dans la chaîne
    # Formats rencontrés :
    #   "M. le président 330008"
    #   "Mme Cyrielle Chatelain\n  794008\n  rapporteur..."
    id_match = re.search(r"\b(\d{5,6})\b", raw)
    acteur_id = ("PA" + id_match.group(1)) if id_match else ""

    # Nom = tout ce qui précède le premier chiffre (ou toute la chaîne)
    name_part = raw[:id_match.start()].strip() if id_match else raw.strip()
    name = re.sub(r"\s+", " ", name_part).strip()

    # Rôle = tout ce qui suit l'ID
    role = re.sub(r"\s+", " ", raw[id_match.end():]).strip() if id_match else ""

    return name, acteur_id, role


def parse_compte_rendu(path: str, depute_filter: Optional[set] = None) -> list[dict]:
    try:
        tree = ET.parse(path)
    except ET.ParseError:
        return []

    root = tree.getroot()

    uid = _text_of(root.find(_tag("uid")))
    meta = root.find(_tag("metadonnees"))
    date_seance = _text_of(meta.find(_tag("dateSeanceJour"))) if meta is not None else ""
    session = _text_of(meta.find(_tag("session"))) if meta is not None else ""
    legislature = _text_of(meta.find(_tag("legislature"))) if meta is not None else ""

    paragraphes = root.findall(f".//{_tag('paragraphe')}")

    results = []
    for p in paragraphes:
        orateurs_elem = p.find(_tag("orateurs"))
        texte_elem = p.find(_tag("texte"))

        name, acteur_id, role = parse_orateur(orateurs_elem)
        text = _text_of(texte_elem)

        if not text or not has_any_match(text):
            continue

        if depute_filter is not None and acteur_id not in depute_filter:
            continue

        matches = find_matches(text)

        results.append({
            "source": "compte_rendu",
            "cr_uid": uid,
            "date_seance": date_seance,
            "session": session,
            "legislature": legislature,
            "orateur_nom": name,
            "acteur_ref": acteur_id,
            "role": role,
            "texte": text[:1500],
            "keyword_matches": matches,
            "keyword_groups": list(matches.keys()),
            "file": path,
        })

    return results


def extract_all(base_dir: str, depute_filter: Optional[set] = None) -> list[dict]:
    pattern = os.path.join(base_dir, "Compte rendu", "compteRendu", "*.xml")
    files = glob.glob(pattern)

    results = []
    for path in files:
        results.extend(parse_compte_rendu(path, depute_filter=depute_filter))

    return results
