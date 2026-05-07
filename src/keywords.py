"""
Champ sémantique : cloud, data center, souveraineté numérique.
Chaque terme est une regex case-insensitive compilée.
Les groupes permettent de catégoriser les résultats.
"""

import re

# Patterns qui doivent rester sensibles à la casse (ex : IA, AI, GPU)
CASE_SENSITIVE = {
    "ia_calcul": {
        r"(?<![a-zA-Zéèàùâêîôûçœæ'])IA(?![a-zA-Zéèàùâêîôûçœæ])",
        r"(?<![a-zA-Zéèàùâêîôûçœæ'])AI(?![a-zA-Zéèàùâêîôûçœæ])",
        r"\bGPU\b",
        r"\bLLM\b",
        r"\bHPC\b",
    }
}

KEYWORD_GROUPS = {
    "cloud": [
        r"\bcloud\b",
        r"\binformatique\s+en\s+nuage\b",
        r"\bnuage\s+informatique\b",
        r"\bcloud\s+computing\b",
        r"\bcloud\s+souverain\b",
        r"\bcloud\s+de\s+confiance\b",
        r"\bcloud\s+hybride\b",
        r"\bcloud\s+priv[ée]\b",
        r"\bcloud\s+public\b",
        r"\bmulticloud\b",
        r"\bhyperscal(?:er|eur)s?\b",
        r"\bSaaS\b",
        r"\bPaaS\b",
        r"\bIaaS\b",
        r"\bservices?\s+en\s+ligne\b",
        r"\bopérateurs?\s+(?:de\s+)?cloud\b",
        r"\bfournisseurs?\s+(?:de\s+)?cloud\b",
        r"\bplatteforme\s+cloud\b",
        r"\bplateforme\s+numérique\b",
    ],
    "data_center": [
        r"\bdata[\s\-]?centers?\b",
        r"\bdatacenters?\b",
        r"\bcentres?\s+de\s+données\b",
        r"\bcentres?\s+informatiques?\b",
        r"\bsalles?\s+(?:de\s+)?serveurs?\b",
        r"\binfrastructures?\s+(?:d[e']?\s+)?hébergement\b",
        r"\bhébergeurs?\s+(?:de\s+)?données\b",
        r"\bhébergement\s+(?:de\s+)?données\b",
        r"\bhébergement\s+numérique\b",
        r"\bstockage\s+(?:de\s+)?données\b",
        r"\bstockage\s+(?:en\s+)?nuage\b",
        r"\bserveurs?\s+(?:informatiques?)?\b",
        r"\binfrastructures?\s+numériques?\b",
        r"\binfrastructures?\s+(?:de\s+)?données\b",
        r"\bcapacités?\s+(?:de\s+)?calcul\b",
        r"\bcalcul\s+intensif\b",
    ],
    "souverainete_numerique": [
        r"\bsouveraineté\s+numérique\b",
        r"\bsouveraineté\s+(?:des?\s+)?données\b",
        r"\bsouveraineté\s+technologique\b",
        r"\bsouveraineté\s+(?:du\s+)?numérique\b",
        r"\bindépendance\s+numérique\b",
        r"\bindépendance\s+technologique\b",
        r"\bautonomie\s+numérique\b",
        r"\bautonomie\s+stratégique\s+(?:numérique|technologique|des?\s+données)\b",
        r"\brésilience\s+numérique\b",
        r"\brésilience\s+(?:des?\s+)?données\b",
        r"\bespaces?\s+européen\s+(?:des?\s+)?données\b",
        r"\blocalisation\s+(?:des?\s+)?données\b",
        r"\bdomiciliation\s+(?:des?\s+)?données\b",
        r"\bSecNumCloud\b",
        r"\bvisas?\s+(?:de\s+)?sécurité\s+cloud\b",
        r"\bprotection\s+(?:des?\s+)?données\s+(?:personnelles?)?\b",
        r"\bGAFAM\b",
        r"\bGAFA\b",
        r"\bBig[\s\-]?Tech\b",
        r"\bgéants?\s+(?:du\s+)?numérique\b",
        r"\bplatformes?\s+américaines?\b",
        r"\bplatformes?\s+(?:extra|hors)[‑\-]?(?:européennes?|UE)\b",
        r"\bextraterritorialit[eé]\b",
        r"\bCloud\s+Act\b",
        r"\bRGPD\b",
        r"\bGDPR\b",
        r"\bdonnées\s+(?:personnelles?|sensibles?|critiques?|stratégiques?)\b",
        r"\bhébergement\s+(?:en\s+)?(?:Europe|France|national|territorial)\b",
        r"\bANSSI\b",
        r"\bnumérique\s+souverain\b",
        r"\béconomie\s+(?:de\s+la\s+)?(?:donnée|données)\b",
        r"\bespace\s+(?:de\s+)?données\b",
    ],
    "ia_calcul": [
        r"\bintelligence\s+artificielle\b",
        r"\bcalculateurs?\s+(?:quantiques?)?\b",
        r"\bmodèles?\s+(?:de\s+)?langage\b",
        r"\bgénération\s+(?:de\s+)?(?:texte|image|contenu)\b",
        r"\bpuissance\s+(?:de\s+)?calcul\b",
    ],
}

# Compile all patterns once
COMPILED: dict[str, list] = {}
for group, patterns in KEYWORD_GROUPS.items():
    COMPILED[group] = [re.compile(p, re.IGNORECASE | re.UNICODE) for p in patterns]

# Add case-sensitive patterns (no IGNORECASE)
for group, patterns in CASE_SENSITIVE.items():
    compiled_cs = [re.compile(p, re.UNICODE) for p in patterns]
    if group in COMPILED:
        COMPILED[group].extend(compiled_cs)
    else:
        COMPILED[group] = compiled_cs


def find_matches(text: str) -> dict[str, list[str]]:
    """Return dict of group -> list of matched patterns found in text."""
    results = {}
    for group, patterns in COMPILED.items():
        hits = []
        for pat in patterns:
            if pat.search(text):
                hits.append(pat.pattern)
        if hits:
            results[group] = hits
    return results


def has_any_match(text: str) -> bool:
    for patterns in COMPILED.values():
        for pat in patterns:
            if pat.search(text):
                return True
    return False
