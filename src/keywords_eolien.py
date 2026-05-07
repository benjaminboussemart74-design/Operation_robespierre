"""
Champ sémantique : éoliennes et énergie éolienne.
"""

import re

KEYWORD_GROUPS_EOLIEN = {
    "eolien_infrastructure": [
        r"\béoliennes?\b",
        r"\béolien(?:ne)?\b",
        r"\bparcs?\s+éolien(?:s|nes?)?\b",
        r"\baérogénérateurs?\b",
        r"\bturbines?\s+éoliennes?\b",
        r"\bmâts?\s+éoliens?\b",
        r"\bpales?\s+d'éoliennes?\b",
        r"\béolien\s+(?:offshore|onshore|terrestre|en\s+mer|marin)\b",
        r"\bchamps?\s+d'éoliennes?\b",
        r"\binstallations?\s+éoliennes?\b",
        r"\bproduction\s+éolienne\b",
        r"\bcapacités?\s+éoliennes?\b",
        r"\bpuissance\s+éolienne\b",
        r"\bgigawatts?\s+éoliens?\b",
    ],
    "eolien_administratif": [
        r"\bautorisation\s+(?:unique|environnementale)\b",
        r"\bpermis\s+de\s+construire\s+(?:éolien|d'éoliennes?)\b",
        r"\bICPE\b",
        r"\bZDE\b",
        r"\bzone\s+de\s+développement\s+(?:de\s+l'éolien|éolien)\b",
        r"\bprojets?\s+éoliens?\b",
        r"\bdéveloppeurs?\s+éoliens?\b",
        r"\bpromoteurs?\s+éoliens?\b",
        r"\bplanification\s+éolienne\b",
        r"\bmoratoire\s+(?:sur\s+les?\s+)?éoliennes?\b",
        r"\bpermis?\s+éolien\b",
        r"\brecours?\s+(?:contre\s+(?:les?\s+)?)?éoliennes?\b",
        r"\bdistance\s+(?:réglementaire\s+)?(?:aux?\s+habitations?)?\s*(?:éolien)?\b",
        r"\brefus\s+(?:de\s+)?(?:permis?\s+)?éolien\b",
        r"\bcontrats?\s+d'achat\s+(?:éolien|d'électricité\s+éolienne)\b",
        r"\bappels?\s+d'offres?\s+éoliens?\b",
        r"\bRTE\b.*\béolien\b|\béolien\b.*\bRTE\b",
    ],
    "eolien_impacts": [
        r"\bnuisances?\s+(?:sonores?|visuelles?|paysagères?)\s+(?:des?\s+)?éoliennes?\b",
        r"\bimpacts?\s+(?:paysager|visuel|sonore|environnemental|sur\s+la\s+santé)\s+(?:des?\s+)?éoliennes?\b",
        r"\bco-?visibilité\s+éolienne\b",
        r"\briverains?\s+(?:des?\s+)?éoliennes?\b",
        r"\bpaysage\s+(?:et\s+)?éoliennes?\b",
        r"\bhabitats?\s+(?:et\s+)?éoliennes?\b",
        r"\bsanté\s+(?:et\s+)?éoliennes?\b",
        r"\bbifluence\b",
        r"\beffet\s+stroboscopique\b",
        r"\binfra-?sons?\b",
        r"\brapport\s+de\s+l'ANSES\b",
        r"\bbiens?\s+immobiliers?\s+(?:et\s+)?éoliennes?\b",
        r"\bdévaluation\s+immobilière\s+éolienne\b",
        r"\btourisme\s+(?:et\s+)?éoliennes?\b",
        r"\bpêcheurs?\s+(?:et\s+)?éoliennes?\b",
    ],
    "eolien_politique": [
        r"\bobjectifs?\s+éoliens?\b",
        r"\bPPE\b",
        r"\bprogrammation\s+pluriannuelle\s+de\s+l'énergie\b",
        r"\btransition\s+(?:énergétique|écologique)\b.*\béolien\b|\béolien\b.*\btransition\s+(?:énergétique|écologique)\b",
        r"\bEnR\b.*\béolien\b|\béolien\b.*\bEnR\b",
        r"\bénergies?\s+renouvelables?\b.*\béolien\b|\béolien\b.*\bénergies?\s+renouvelables?\b",
        r"\bacceptabilité\s+(?:sociale\s+)?(?:des?\s+)?éoliennes?\b",
        r"\bopposition\s+(?:aux?|contre\s+les?)\s+éoliennes?\b",
        r"\bpolitique\s+éolienne\b",
        r"\bindustrie\s+éolienne\b",
        r"\bfilière\s+éolienne\b",
        r"\bemplois?\s+(?:dans\s+la\s+filière\s+)?éoliens?\b",
        r"\bvestas\b",
        r"\bsiemens\s+gamesa\b",
        r"\bnacelle\s+éolienne\b",
        r"\brepowering\b",
        r"\brenouvellement\s+(?:de\s+parcs?\s+éoliens?)\b",
    ],
}

COMPILED_EOLIEN = {
    group: [re.compile(p, re.IGNORECASE | re.UNICODE) for p in patterns]
    for group, patterns in KEYWORD_GROUPS_EOLIEN.items()
}


def find_matches_eolien(text: str) -> dict[str, list[str]]:
    results = {}
    for group, patterns in COMPILED_EOLIEN.items():
        hits = [pat.pattern for pat in patterns if pat.search(text)]
        if hits:
            results[group] = hits
    return results


def has_any_match_eolien(text: str) -> bool:
    return any(
        pat.search(text)
        for patterns in COMPILED_EOLIEN.values()
        for pat in patterns
    )
