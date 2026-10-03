"""Génère les diapositives « L'électeur type de la 3e circonscription » (type Slides).

Chiffres lus dans ../data.json (typologie socio-électorale en 8 familles).
Sortie : <racine>/project/deck.json et <racine>/project/slides/*.html
Usage : python gen_slides.py <racine>
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ICI = Path(__file__).parent
D = json.loads((ICI.parent / 'data.json').read_text())
RACINE = Path(sys.argv[1])
(RACINE / 'project' / 'slides').mkdir(parents=True, exist_ok=True)

F = D['fine']
VN = ['pPres', 'pEur', 'pLeg', 'LFI', 'RN', 'Gau', 'Ren', 'LR', 'Portes', 'CG', 'Ctr', 'Dte', 'Mel', 'Mac', 'LPZ', 'Pec', 'GMod']
MV = dict(zip(VN, D['moy_vote']))
MS = dict(zip(D['socio_noms'], D['moy_socio']))
TOT = sum(p['inscrits'] for p in F['profils'].values())
COM = {'93051': 'Noisy-le-Grand', '93050': 'Neuilly-sur-Marne', '93049': 'Neuilly-Plaisance', '93033': 'Gournay-sur-Marne'}

# ── Charte (infographie politique) ──
BG, BG2, CARD = '#FAFAF8', '#F2F2EE', '#FFFFFF'
TXT, TXT2, MUTED, BORD = '#1A1A1A', '#4A4A45', '#76766E', '#DDDDD6'
RED, ACC = '#B01E28', '#1B3F7B'
SERIF = "'Playfair Display', Georgia, serif"
SANS = "'DM Sans', Arial, sans-serif"
MONO = "'JetBrains Mono', 'Courier New', monospace"
GRIS = '#E2E1DA'
# Couleur de la famille (carte) et version foncée pour les pictogrammes et les textes
ENCRE = {'1': '#1f5fae', '2': '#3a77b5', '3': '#c9501f', '4': '#b8692e', '5': '#a36f00',
         '6': '#b8487a', '7': '#007a00', '8': '#4a3aa7'}
COURT = {'1': 'Grands ensembles précaires', '2': "Cités d'habitat social", '3': 'Quartiers populaires cosmopolites',
         '4': 'Quartiers mixtes modestes', '5': 'Petits collectifs locatifs', '6': 'Classes moyennes diplômées',
         '7': 'Quartiers aisés de propriétaires', '8': 'Pavillonnaire aisé'}
PARTI = {'Mel': '#E8333A', 'Mac': '#3366CC', 'LPZ': '#0A1833', 'Portes': '#C2272D'}


def nb(x, d=1):
    s = f'{x:,.{d}f}'.replace(',', ' ').replace('.', ',')
    return s.replace(' ', ' ')


def pct(x):
    return nb(x) + ' %'


def eur(x):
    return nb(x, 0) + ' €'


# ── Pictogrammes (SVG, 10 icônes, la dernière remplie en partie) ──
def icone(kind, x, fill):
    if kind == 'personne':
        return (f'<circle cx="{x + 16}" cy="9" r="8" fill="{fill}"/>'
                f'<path d="M{x + 3} 46 V27 a13 10 0 0 1 26 0 V46 Z" fill="{fill}"/>')
    if kind == 'immeuble':
        fen = ''.join(f'<rect x="{x + 8 + c * 10}" y="{8 + r * 10}" width="5" height="5" fill="{BG}"/>'
                      for r in range(3) for c in range(2))
        return f'<rect x="{x + 4}" y="2" width="26" height="44" fill="{fill}"/>' + fen
    if kind == 'maison':
        return (f'<path d="M{x + 1} 22 L{x + 17} 6 L{x + 33} 22 V46 H{x + 1} Z" fill="{fill}"/>'
                f'<rect x="{x + 13}" y="32" width="8" height="14" fill="{BG}"/>')
    raise ValueError(kind)


def picto(kind, part, couleur, uid):
    """part en % : nombre d'icônes sur 10 colorées, la dernière au prorata."""
    n = part / 10
    pas, w = 46, 46 * 10
    fond = ''.join(icone(kind, i * pas, GRIS) for i in range(10))
    plein = ''.join(icone(kind, i * pas, couleur) for i in range(10))
    largeur = int(n) * pas + (n - int(n)) * 34
    return (f'<svg aria-label="{nb(n)} sur 10" width="{w}" height="48" viewBox="0 0 {w} 48">'
            f'<defs><clipPath id="c{uid}"><rect x="0" y="0" width="{largeur:.1f}" height="48"/></clipPath></defs>'
            f'{fond}<g clip-path="url(#c{uid})">{plein}</g></svg>')


def footer(n, total=12):
    return (f'<div style="position:absolute;left:128px;right:128px;bottom:56px;height:40px;display:flex;'
            f'justify-content:space-between;align-items:center;border-top:1px solid {BORD}">'
            f'<p style="font-size:24px;color:{MUTED}">Source : ministère de l\'Intérieur, INSEE (recensement 2022, revenus 2021) · moyennes des bureaux de vote</p>'
            f'<p style="font-family:{MONO};font-size:24px;color:{MUTED}">{n}/{total}</p></div>')


def section(sid, style, corps, notes, extra=''):
    return (f'<section id="{sid}" data-transition="fade" style="background:{BG};color:{TXT};font-family:{SANS};{style}">'
            f'<div style="position:absolute;left:0;top:0;width:1920px;height:8px;background:{RED}"></div>'
            f'{extra}{corps}<aside>{notes}</aside></section>')


# ── Portraits ──
PORTRAITS = {
    '1': "Il habite un appartement dans un grand ensemble de Noisy-le-Grand, en HLM pour près d'un ménage sur deux. "
         "Son quartier est le plus pauvre de la circonscription : {cho} de chômage et près de 4 habitants sur 10 immigrés. "
         "Il vote peu ({pPres} à la présidentielle), mais quand il vote, c'est à gauche : "
         "{Mel} pour Jean-Luc Mélenchon en 2022, {Portes} pour Thomas Portes en 2024.",
    '2': "Il vit dans une cité d'habitat social, le plus souvent à Neuilly-sur-Marne : 7 logements sur 10 sont des HLM, "
         "plus d'une famille sur trois est monoparentale et près d'un adulte sur trois n'a aucun diplôme. "
         "Le vote insoumis domine ({Mel} pour Mélenchon en 2022), mais le Rassemblement national y pèse davantage "
         "que dans les grands ensembles noiséens ({RN} aux européennes).",
    '3': "Il habite un immeuble, en copropriété ou en HLM, jamais une maison. Son quartier est familial "
         "(une famille sur deux est un couple avec enfants) et cosmopolite : près de 4 habitants sur 10 sont immigrés. "
         "La gauche y reste en tête, mais moins massivement : {Mel} pour Mélenchon et {Mac} pour Macron en 2022.",
    '4': "C'est l'électeur le plus répandu : un inscrit sur quatre, surtout à Neuilly-sur-Marne. "
         "Il vit dans un quartier qui mêle immeubles, HLM et pavillons, aux revenus un peu inférieurs à la moyenne. "
         "Son vote suit de près celui de la circonscription, avec un Rassemblement national légèrement plus fort : "
         "{RN} aux européennes 2024.",
    '5': "Il est jeune, vit souvent seul et loue son logement à un bailleur privé, dans deux bureaux de Neuilly-Plaisance : "
         "plus de la moitié des ménages sont des personnes seules et un sur deux n'a pas de voiture. "
         "Il vote à gauche modérée et au centre : {Gau} pour les listes PS, écologistes et PCF aux européennes, "
         "{Mac} pour Macron en 2022.",
    '6': "Il habite un appartement, presque toujours à Noisy-le-Grand (13 bureaux sur 14). Diplômé du supérieur "
         "une fois sur deux, cadre ou profession intermédiaire, il vit souvent seul. C'est l'électeur qui vote le plus : "
         "{pPres} à la présidentielle. Il partage ses voix entre Macron ({Mac}), Mélenchon ({Mel}) et la gauche modérée.",
    '7': "Il est propriétaire deux fois sur trois, souvent d'une maison, dans les quartiers aisés de Noisy-le-Grand "
         "et de Neuilly-Plaisance. Plus âgé que la moyenne, il vote beaucoup et au centre : {Mac} pour Macron en 2022, "
         "{Gau} pour la gauche modérée aux européennes. Le vote insoumis y est faible ({LFI}).",
    '8': "Il vit dans une maison dont il est propriétaire (3 ménages sur 4), à Gournay-sur-Marne, à Neuilly-Plaisance "
         "ou dans le pavillonnaire noiséen. Ses revenus sont les plus élevés de la circonscription, et 86 % des ménages "
         "ont une voiture. C'est là que la droite et le RN font leurs meilleurs scores : {RN} pour le RN et Reconquête "
         "aux européennes, {LPZ} pour Le Pen et Zemmour en 2022.",
}


def portrait(k, num):
    P = F['profils'][k]
    F_ = F['familles'][k]
    V = dict(zip(VN, P['vote']))
    S = dict(zip(D['socio_noms'], P['socio']))
    ink = ENCRE[k]
    vals = {**{c: pct(v) for c, v in V.items()}, **{c: pct(v) for c, v in S.items()}}
    texte = PORTRAITS[k].format(**vals)
    coms = ' · '.join(f'{COM[c]} {n}' for c, n in P['communes'].items() if n)
    part = 100 * P['inscrits'] / TOT

    lignes_picto = [
        ('immeuble', 'logements HLM', 'sur 10 logements', S['hlm'], MS['hlm']),
        ('maison', 'propriétaires', 'sur 10 logements', S['pro'], MS['pro']),
        ('personne', 'diplômés du supérieur', 'sur 10 adultes', S['dip'], MS['dip']),
        ('personne', 'immigrés', 'sur 10 habitants', S['imm'], MS['imm']),
    ]
    pictos = ''.join(
        f'<div style="display:flex;flex-direction:row;align-items:center;gap:24px">'
        f'<div style="width:300px;display:flex;flex-direction:column"><p style="font-size:26px;font-weight:600;line-height:1.15">{lab}</p>'
        f'<p style="font-size:24px;color:{MUTED};line-height:1.15">{sur}</p></div>'
        f'{picto(kind, v, ink, f"{k}{i}")}'
        f'<div style="display:flex;flex-direction:column"><p style="font-family:{MONO};font-size:30px;font-weight:700;line-height:1.1">{pct(v)}</p>'
        f'<p style="font-family:{MONO};font-size:24px;color:{MUTED};line-height:1.1">moy. {pct(m)}</p></div></div>'
        for i, (kind, lab, sur, v, m) in enumerate(lignes_picto))

    barres_def = [('Mélenchon · 2022', 'Mel'), ('Macron · 2022', 'Mac'), ('Le Pen et Zemmour · 2022', 'LPZ'), ('Portes · 2024', 'Portes')]
    ECH = 460 / 70  # 70 % = toute la piste
    barres = ''.join(
        f'<div style="display:flex;flex-direction:row;align-items:center;gap:24px">'
        f'<p style="width:300px;font-size:26px;font-weight:500">{lab}</p>'
        f'<div style="position:relative;width:460px;height:36px;background:{BG2}">'
        f'<div style="position:absolute;left:0;top:0;width:{V[c] * ECH:.0f}px;height:36px;background:{PARTI[c]}"></div>'
        f'<div style="position:absolute;left:{MV[c] * ECH - 3:.0f}px;top:0;width:6px;height:36px;background:{TXT};border:1px solid #FFFFFF"></div></div>'
        f'<p style="font-family:{MONO};font-size:30px;font-weight:700">{pct(V[c])}</p></div>'
        for lab, c in barres_def)

    corps = (
        f'<div style="display:flex;flex-direction:row;align-items:center;gap:32px">'
        f'<div style="width:96px;height:96px;background:{F_["col"]};display:flex;align-items:center;justify-content:center;flex:none">'
        f'<p style="font-family:{MONO};font-size:52px;font-weight:700;color:{"#FFFFFF" if k in ("1", "7", "8") else TXT}">{k}</p></div>'
        f'<div style="display:flex;flex-direction:column;gap:6px">'
        f'<p style="font-size:24px;font-weight:600;letter-spacing:3px;text-transform:uppercase;color:{ink}">'
        f'Famille {k} sur 8 · {len(P["bv"])} bureaux · {nb(part)} % des inscrits</p>'
        f'<h2 style="font-family:{SERIF};font-size:54px;font-weight:700;letter-spacing:-1px;line-height:1.1">{F_["nom"]}</h2></div></div>'
        f'<div style="display:grid;grid-template-columns:640px 1fr;gap:88px;align-items:start">'
        # gauche : portrait
        f'<div style="display:flex;flex-direction:column;gap:32px">'
        f'<p style="font-size:30px;line-height:1.45;color:{TXT2}">{texte}</p>'
        f'<div style="display:flex;flex-direction:column;gap:2px;border-left:6px solid {ink};padding:4px 0 4px 24px">'
        f'<p style="font-size:24px;font-weight:600;letter-spacing:2px;text-transform:uppercase;color:{MUTED}">Revenu médian</p>'
        f'<p style="font-family:{MONO};font-size:56px;font-weight:700;letter-spacing:-1px">{eur(S["rev"])}</p>'
        f'<p style="font-size:24px;color:{MUTED}">par an et par unité de consommation · moyenne {eur(MS["rev"])}</p></div>'
        f'<p style="font-size:24px;color:{MUTED}">{coms}</p></div>'
        # droite : pictogrammes et vote
        f'<div style="display:flex;flex-direction:column;gap:18px">'
        f'<p style="font-size:24px;font-weight:600;letter-spacing:3px;text-transform:uppercase;color:{MUTED}">Où il vit, qui il est</p>'
        f'{pictos}'
        f'<p style="font-size:24px;font-weight:600;letter-spacing:3px;text-transform:uppercase;color:{MUTED};padding:22px 0 0 0">'
        f'Comment il vote · premier tour, trait noir = moyenne</p>'
        f'{barres}</div></div>')
    notes = (f'Famille {k} : {F_["nom"]}. {len(P["bv"])} bureaux, {nb(P["inscrits"], 0)} inscrits ({nb(part)} %). '
             f'Le vote est secret : ce portrait décrit le quartier type de ces bureaux, moyenne simple des bureaux. '
             f'Participation à la présidentielle 2022 : {pct(V["pPres"])} (moyenne {pct(MV["pPres"])}).')
    return section(f'famille{k}', 'padding:96px 128px 160px;display:flex;flex-direction:column;gap:56px', corps, notes, footer(num))


# ── Couverture ──
ordre = [str(i) for i in range(1, 9)]
bande = ''.join(
    f'<div style="flex:{F["profils"][k]["inscrits"]};height:120px;background:{F["familles"][k]["col"]};display:flex;align-items:center;justify-content:center">'
    f'<p style="font-family:{MONO};font-size:36px;font-weight:700;color:{"#FFFFFF" if k in ("1", "7", "8") else TXT}">{k}</p></div>'
    for k in ordre)
couverture = section(
    'cover', 'padding:128px;display:flex;flex-direction:column;justify-content:space-between',
    f'<div style="display:flex;flex-direction:column;gap:32px">'
    f'<p style="font-size:28px;font-weight:600;letter-spacing:4px;text-transform:uppercase;color:{RED}">Seine-Saint-Denis · 3e circonscription</p>'
    f'<h1 style="font-family:{SERIF};font-size:112px;font-weight:900;letter-spacing:-2px;line-height:1.05">L\'électeur type,<br>famille par famille</h1>'
    f'<p style="font-size:36px;line-height:1.4;color:{TXT2};width:1300px">Huit familles de quartiers, huit portraits : qui vit où, et comment on y vote, '
    f'à Noisy-le-Grand, Neuilly-sur-Marne, Neuilly-Plaisance et Gournay-sur-Marne.</p></div>'
    f'<div style="display:flex;flex-direction:column;gap:16px">'
    f'<div style="display:flex;flex-direction:row;gap:4px">{bande}</div>'
    f'<p style="font-size:24px;color:{MUTED}">Les huit familles, à proportion de leurs inscrits · 82 bureaux de vote · {nb(TOT, 0)} inscrits (législatives 2024)</p></div>',
    "Présentation des huit familles de la typologie socio-électorale de la circonscription. "
    "La bande colorée montre le poids de chaque famille dans les inscrits.")

# ── Comment lire ──
def carte(titre, texte):
    return (f'<div style="flex:1;display:flex;flex-direction:column;gap:20px;background:{CARD};border:1px solid {BORD};padding:48px">'
            f'<h3 style="font-family:{SERIF};font-size:44px;font-weight:700;letter-spacing:-1px;line-height:1.15">{titre}</h3>'
            f'<p style="font-size:28px;line-height:1.45;color:{TXT2}">{texte}</p></div>')


legende = (f'<div style="display:flex;flex-direction:row;align-items:center;gap:20px">'
           f'{picto("immeuble", 45, ENCRE["1"], "L1")}</div>')
lire = section(
    'lire', 'padding:128px 128px 160px;display:flex;flex-direction:column;gap:56px',
    f'<h2 style="font-family:{SERIF};font-size:72px;font-weight:700;letter-spacing:-1px">Comment lire ces portraits</h2>'
    f'<div style="display:flex;flex-direction:row;gap:32px">'
    + carte('82 bureaux, 8 familles', "Chaque bureau est décrit par son vote (présidentielle 2022, européennes et législatives 2024) "
            "et par 21 indicateurs sociaux de l'INSEE. Les bureaux qui se ressemblent le plus sont regroupés en familles.")
    + carte('Un quartier type', "Le vote est secret : on ne connaît pas chaque électeur, mais le quartier où il vote. "
            "L'électeur type est la moyenne des bureaux de sa famille. Les municipales ne servent pas au calcul.")
    + carte('Les pictogrammes', "Dix icônes représentent dix logements, dix adultes ou dix habitants. Les icônes colorées "
            "donnent la part concernée. Sur les barres de vote, le trait noir marque la moyenne de la circonscription.")
    + '</div>'
    f'<div style="display:flex;flex-direction:row;align-items:center;gap:32px">{legende}'
    f'<p style="font-size:28px;color:{TXT2}">Exemple : 4,5 logements sur 10 sont des HLM.</p></div>',
    "Méthode : classification ascendante hiérarchique (Ward), votes et sociologie à poids égal. "
    "Les chiffres sont des moyennes de bureaux : ils atténuent les écarts réels entre électeurs.", footer(2))

# ── Vue d'ensemble ──
lignes = ''.join(
    f'<tr><td style="color:{ENCRE[k]};font-weight:700">{k} · {COURT[k]}</td>'
    f'<td>{len(F["profils"][k]["bv"])}</td><td>{pct(100 * F["profils"][k]["inscrits"] / TOT)}</td>'
    f'<td>{eur(dict(zip(D["socio_noms"], F["profils"][k]["socio"]))["rev"])}</td>'
    + ''.join(f'<td>{pct(dict(zip(VN, F["profils"][k]["vote"]))[c])}</td>' for c in ('Mel', 'Mac', 'LPZ'))
    + '</tr>' for k in ordre)
ensemble = section(
    'ensemble', 'padding:128px 128px 160px;display:flex;flex-direction:column;gap:48px',
    f'<h2 style="font-family:{SERIF};font-size:72px;font-weight:700;letter-spacing:-1px">Huit électeurs types, du plus modeste au plus aisé</h2>'
    f'<table style="font-family:{SANS};font-size:28px;color:{TXT}">'
    f'<tr><th style="width:34%;text-align:left">Famille</th><th style="width:9%;text-align:right">Bureaux</th>'
    f'<th style="width:11%;text-align:right">Inscrits</th><th style="width:13%;text-align:right">Revenu médian</th>'
    f'<th style="width:11%;text-align:right">Mélenchon 2022</th><th style="width:11%;text-align:right">Macron 2022</th>'
    f'<th style="width:11%;text-align:right">Le Pen et Zemmour</th></tr>{lignes}'
    f'<tr style="background:{BG2}"><td style="font-weight:700">Moyenne des bureaux</td><td>82</td><td>100 %</td><td>{eur(MS["rev"])}</td>'
    f'<td>{pct(MV["Mel"])}</td><td>{pct(MV["Mac"])}</td><td>{pct(MV["LPZ"])}</td></tr></table>',
    "Lecture : le revenu médian ordonne presque parfaitement le vote Mélenchon, qui passe de 55 % à 23 %. "
    "Les familles 4 et 6, les plus nombreuses, votent comme la circonscription.", footer(3))

# ── Synthèse ──
def stat(chiffre, titre, texte):
    return (f'<div style="flex:1;display:flex;flex-direction:column;gap:16px;border-top:6px solid {RED};padding:32px 0 0 0">'
            f'<p style="font-family:{MONO};font-size:88px;font-weight:700;letter-spacing:-2px;line-height:1">{chiffre}</p>'
            f'<h3 style="font-family:{SERIF};font-size:40px;font-weight:700;line-height:1.15">{titre}</h3>'
            f'<p style="font-size:28px;line-height:1.45;color:{TXT2}">{texte}</p></div>')


m = {k: dict(zip(VN, F['profils'][k]['vote'])) for k in ordre}
p46 = 100 * (F['profils']['4']['inscrits'] + F['profils']['6']['inscrits']) / TOT
nsm4 = 100 * F['profils']['4']['ins_communes']['93050'] / sum(F['profils'][k]['ins_communes']['93050'] for k in ordre)
synthese = section(
    'synthese', 'padding:128px 128px 160px;display:flex;flex-direction:column;gap:64px',
    f'<h2 style="font-family:{SERIF};font-size:72px;font-weight:700;letter-spacing:-1px">Ce qu\'il faut retenir</h2>'
    f'<div style="display:flex;flex-direction:row;gap:64px">'
    + stat(f'{nb(m["1"]["Mel"], 0)} → {nb(m["8"]["Mel"], 0)} %', 'Le revenu ordonne le vote',
           f'Le vote Mélenchon de 2022 passe de {pct(m["1"]["Mel"])} dans les grands ensembles à {pct(m["8"]["Mel"])} dans le pavillonnaire aisé. '
           f'Le Pen et Zemmour suivent le chemin inverse, de {pct(m["1"]["LPZ"])} à {pct(m["8"]["LPZ"])}.')
    + stat(f'{nb(p46, 0)} %', 'Un centre de gravité', 'Deux familles, les quartiers mixtes modestes (4) et les classes moyennes diplômées (6), '
           'réunissent ces inscrits. Leur vote est le plus proche de celui de la circonscription.')
    + stat(f'{nb(nsm4, 0)} %', 'Chaque commune a sa signature', 'des inscrits de Neuilly-sur-Marne vivent dans un quartier mixte modeste. '
           'Gournay-sur-Marne est tout entière pavillonnaire aisée ; Noisy-le-Grand et Neuilly-Plaisance mêlent tous les profils.')
    + '</div>',
    "Synthèse. Rappel : ces portraits décrivent des quartiers, pas des individus.", footer(12))

slides = {'cover': couverture, 'lire': lire, 'ensemble': ensemble}
for i, k in enumerate(ordre):
    slides[f'famille{k}'] = portrait(k, i + 4)
slides['synthese'] = synthese
for sid, html in slides.items():
    (RACINE / 'project' / 'slides' / f'{sid}.html').write_text(html)

deck = {
    'v': 4, 'createdOnFiles': {'v': 1, 'at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')},
    'lists': 'css', 'title': "L'électeur type de la 3e circonscription",
    'order': list(slides), 'cover': 'cover',
    'sections': {
        's1': {'description': 'Introduction et méthode', 'start': 'cover'},
        's2': {'description': 'Les huit portraits', 'start': 'famille1'},
        's3': {'description': 'Synthèse', 'start': 'synthese'},
    },
    'faces': {
        'playfair-display': {'family': 'Playfair Display', 'href': 'https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&display=swap'},
        'dm-sans': {'family': 'DM Sans', 'href': 'https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap'},
        'jetbrains-mono': {'family': 'JetBrains Mono', 'href': 'https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;700&display=swap'},
    },
    'designSystems': [],
}
(RACINE / 'project' / 'deck.json').write_text(json.dumps(deck, ensure_ascii=False, indent=1))
print(list(slides))
