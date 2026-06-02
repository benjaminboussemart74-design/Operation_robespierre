"""
Champ sémantique : taxis, VTC, plateformes de mobilité, travailleurs indépendants de plateforme.

Stratégie anti-faux-positifs :
- "plateforme" seul → écarté (trop générique en contexte parlementaire)
- "indépendant" seul → écarté (trop générique)
- "taxi" seul → conservé (très spécifique en contexte parlementaire)
- VTC, Uber, ubérisation → case-sensitive pour VTC/noms propres
"""

import re

KEYWORD_GROUPS_TAXI = {
    "taxi_vtc": [
        r"\btaxis?\b",
        r"\bchauffeurs?\s+de\s+taxi\b",
        r"\blicences?\s+de\s+taxi\b",
        r"\bplaque\s+de\s+taxi\b",
        r"\bcarte\s+(?:professionnelle\s+)?de\s+taxi\b",
        r"\bcentrale\s+de\s+réservation\b",
        r"\bchauffeurs?\s+(?:privés?|indépendants?)\s+(?:de\s+)?VTC\b",
        r"\bchauffeurs?\s+VTC\b",
        r"\bvoitures?\s+de\s+transport\s+avec\s+chauffeur\b",
        r"\bregistre\s+(?:national\s+)?(?:des?\s+)?VTC\b",
        r"\btransport\s+(?:artisanal|de\s+personnes)\s+à\s+la\s+demande\b",
        r"\bADTC\b",
        r"\bUNTC\b",
        r"\bFNTI\b",
        r"\bG7\s+(?:taxi|transport)\b",
    ],
    "plateformes_mobilite": [
        r"\bUber\b",
        r"\bLyft\b",
        r"\bBolt\b",
        r"\bHeetch\b",
        r"\bKapten\b",
        r"\bMarcel\b",
        r"\bDeliveroo\b",
        r"\bUber\s+Eats\b",
        r"\bubérisation\b",
        r"\béconomie\s+de\s+(?:la\s+)?plateforme\b",
        r"\bplatformes?\s+(?:numériques?\s+)?(?:de\s+)?(?:mobilité|transport|mise\s+en\s+relation)\b",
        r"\bplatformes?\s+(?:de\s+)?(?:travail|emploi|services?)\s+(?:à\s+la\s+demande|numériques?)\b",
        r"\btravailleurs?\s+(?:de\s+|des?\s+)plateformes?\b",
        r"\blivreurs?\s+(?:à\s+vélo|indépendants?|de\s+plateforme)\b",
        r"\bVTC\b",
    ],
    "statut_independants": [
        r"\bprésomption\s+de\s+salariat\b",
        r"\brequalification\s+(?:en\s+)?salari[eé]\b",
        r"\bauto-?entrepreneur(?:iat)?\b",
        r"\bstatut\s+(?:des?\s+)?(?:micro-entrepreneur|auto-entrepreneur)\b",
        r"\bdirective\s+(?:européenne\s+)?(?:sur\s+les?\s+)?travailleurs?\s+(?:de\s+)?plateformes?\b",
        r"\bindépendants?\s+(?:de\s+)?plateformes?\b",
        r"\bfaux\s+indépendants?\b",
        r"\bcharte\s+(?:de\s+)?plateformes?\b",
        r"\bprotection\s+sociale\s+(?:des?\s+)?(?:travailleurs?\s+)?(?:de\s+)?plateformes?\b",
        r"\bdroit\s+(?:du\s+)?travail\s+(?:et\s+)?plateformes?\b",
        r"\bCPAM\b.*\bplateforme\b|\bplateforme\b.*\bCPAM\b",
        r"\burssaf\b.*\bplateforme\b|\bplateforme\b.*\burssaf\b",
    ],
}

# VTC en majuscules → case-sensitive
CASE_SENSITIVE_TAXI = {
    "taxi_vtc": [r"\bVTC\b"],
    "plateformes_mobilite": [r"\bUber\b", r"\bLyft\b", r"\bBolt\b",
                              r"\bHeetch\b", r"\bKapten\b", r"\bMarcel\b",
                              r"\bDeliveroo\b"],
}

COMPILED_TAXI: dict[str, list] = {}
for group, patterns in KEYWORD_GROUPS_TAXI.items():
    COMPILED_TAXI[group] = [re.compile(p, re.IGNORECASE | re.UNICODE) for p in patterns]

for group, patterns in CASE_SENSITIVE_TAXI.items():
    cs = [re.compile(p, re.UNICODE) for p in patterns]
    if group in COMPILED_TAXI:
        COMPILED_TAXI[group].extend(cs)
    else:
        COMPILED_TAXI[group] = cs

# Dédoublonnage (VTC compilé deux fois sinon)
for group in COMPILED_TAXI:
    seen = set()
    deduped = []
    for pat in COMPILED_TAXI[group]:
        if pat.pattern not in seen:
            seen.add(pat.pattern)
            deduped.append(pat)
    COMPILED_TAXI[group] = deduped


def find_matches_taxi(text: str) -> dict[str, list[str]]:
    results = {}
    for group, patterns in COMPILED_TAXI.items():
        hits = [pat.pattern for pat in patterns if pat.search(text)]
        if hits:
            results[group] = hits
    return results


def has_any_match_taxi(text: str) -> bool:
    return any(
        pat.search(text)
        for patterns in COMPILED_TAXI.values()
        for pat in patterns
    )
