"""Support projeté de la réunion publique des Richardets (mercredi 14 octobre 2026, 19 h, Victoria Park).

La charte est celle des réunions précédentes : le fichier du Mont d'Est (modele/) fournit
le gabarit (dimensions, logo, couverture, sommaire, « Vos questions ») ; les autres
diapositives sont construites ici avec les mêmes couleurs, la même police (Arial) et les
mêmes tailles. Tous les textes sont des zones de texte modifiables.

Contenu : brief du cabinet du 13 octobre 2026. Les emplacements entre crochets du brief ont
été complétés uniquement lorsque les réponses des services (courriels des 9 et 13 octobre)
y répondent directement ; les autres restent visibles, en cadre pointillé.

Usage : python3 presentation_richardets.py
"""
import copy
import io
import os

from lxml import etree
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

from build_richardets import forme, notes, ordonner, remplacer_image, remplacer_texte, vue_aerienne

ICI = os.path.dirname(os.path.abspath(__file__))
MODELE = os.path.join(ICI, "modele", "PPT_Mont_dEst_V3.pptx")
VISUELS = os.path.join(ICI, "Visuels_Richardets")
SORTIE = os.environ.get("SORTIE_PPT", os.path.join(ICI, "PPT_Richardets_V1.pptx"))

# Charte (relevée dans le fichier du Mont d'Est)
NUIT, VERT, CREME, BLANC = "0E1F5B", "72C493", "FAF5EC", "FFFFFF"
CARTE, GRIS = "132568", "8A90B0"     # fond des cartes sur bleu nuit, texte secondaire
JAUNE = "F2D43A"                     # jaune des caméras en cours d'installation (carte fournie)
POLICE = "Arial"
G_COUVERTURE, G_SOMMAIRE, G_QUESTIONS = 2, 3, 28   # gabarits repris du Mont d'Est
G_QR_ACCUEIL, G_QR_SORTIE = 1, 29                    # QR code et fiche de renseignement
G_PERI_MERCREDI, G_PERI_CANTINE, G_KEOLIS = 6, 7, 27  # diapositives habituelles, chiffres de toute la ville
SIGNALEMENTS = os.path.join(ICI, "signalements_par_arret.csv")
SYNTHESE_BUS = os.path.join(ICI, "signalements_synthese.csv")
LIGNES_PRINCIPALES = ("310", "312", "320")            # lignes qui traversent le quartier


def rgb(h):
    return RGBColor.from_string(h)


# ---------------------------------------------------------------------------
# Briques de mise en page
# ---------------------------------------------------------------------------
def fond(diapo, couleur):
    bg = diapo.background.fill
    bg.solid()
    bg.fore_color.rgb = rgb(couleur)


def texte(diapo, x, y, w, h, contenu, taille, couleur, gras=True, align=PP_ALIGN.LEFT,
          ancre=MSO_ANCHOR.TOP, espacement=None, interligne=None):
    """Zone de texte modifiable. `contenu` : chaîne ou liste de paragraphes."""
    zone = diapo.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = zone.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = ancre
    for m in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, m, 0)
    for i, ligne in enumerate([contenu] if isinstance(contenu, str) else contenu):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if interligne:
            p.line_spacing = interligne
        r = p.add_run()
        r.text = ligne
        f = r.font
        f.name, f.size, f.bold = POLICE, Pt(taille), gras
        f.color.rgb = rgb(couleur)
        if espacement:
            r._r.get_or_add_rPr().set("spc", str(espacement))
    return zone


def ombre_verte(zone):
    """Ombre verte des titres de la charte (reprise du Mont d'Est)."""
    spPr = zone._element.spPr
    eff = etree.SubElement(spPr, qn("a:effectLst"))
    sh = etree.SubElement(eff, qn("a:outerShdw"), blurRad="101600", dist="80822", dir="2700000",
                          algn="bl", rotWithShape="0")
    c = etree.SubElement(sh, qn("a:srgbClr"), val=VERT)
    etree.SubElement(c, qn("a:alpha"), val="100000")


def rect(diapo, x, y, w, h, couleur, forme_=MSO_SHAPE.RECTANGLE, contour=None):
    s = diapo.shapes.add_shape(forme_, Inches(x), Inches(y), Inches(w), Inches(h))
    if couleur:
        s.fill.solid()
        s.fill.fore_color.rgb = rgb(couleur)
    else:
        s.fill.background()
    if contour:
        s.line.color.rgb = rgb(contour)
    else:
        s.line.fill.background()
    s.shadow.inherit = False
    return s


def ligne(diapo, x1, y1, x2, y2, couleur, epaisseur=3):
    c = diapo.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = rgb(couleur)
    c.line.width = Pt(epaisseur)
    return c


def a_completer(diapo, x, y, w, h, mention, sombre=False):
    """Emplacement visible pour un élément manquant, en cadre pointillé."""
    s = rect(diapo, x, y, w, h, None)
    s.line.color.rgb = rgb(GRIS)
    s.line.width = Pt(2.5)
    s.line.dash_style = MSO_LINE_DASH_STYLE.DASH
    texte(diapo, x + 0.3, y, w - 0.6, h, mention, 22, "C9CCDA" if sombre else GRIS, gras=True,
          align=PP_ALIGN.CENTER, ancre=MSO_ANCHOR.MIDDLE)


def image(diapo, chemin, x, y, w, h, align="centre"):
    """Insère une image entière dans le cadre (x, y, w, h), sans déformation ni recadrage."""
    with Image.open(chemin) as im:
        iw, ih = im.size
    k = min(w / iw, h / ih)
    rw, rh = iw * k, ih * k
    dx = {"centre": (w - rw) / 2, "gauche": 0, "droite": w - rw}[align]
    return diapo.shapes.add_picture(chemin, Inches(x + dx), Inches(y + (h - rh) / 2), Inches(rw), Inches(rh))


class Deck:
    def __init__(self):
        self.prs = Presentation(MODELE)
        self.layout = self.prs.slides[G_SOMMAIRE - 1].slide_layout
        logo = self.prs.slides[G_SOMMAIRE - 1].shapes[0]       # logo « Les réunions publiques »
        self.logo = io.BytesIO(logo.image.blob)
        self.nouvelles = []

    def diapo(self, couleur, surtitre, titre, notes_orateur):
        d = self.prs.slides.add_slide(self.layout)
        for ph in list(d.placeholders):
            ph._element.getparent().remove(ph._element)
        fond(d, couleur)
        self.logo.seek(0)
        d.shapes.add_picture(self.logo, Inches(17.50), Inches(0.25), Inches(2.08), Inches(2.12))
        sur = texte(d, 1.04, 0.80, 15.8, 0.45, surtitre.upper(), 21, VERT, espacement=150)
        sur.name = "Surtitre"
        t = texte(d, 1.04, 1.30, 15.8, 0.85, titre, 44, BLANC if couleur == NUIT else NUIT)
        t.name = "Titre"
        ombre_verte(t)
        notes(d, notes_orateur, modele=self.prs.slides[G_SOMMAIRE - 1])
        self.nouvelles.append(len(self.prs.slides))
        return d


# ---------------------------------------------------------------------------
# Composants « à construire »
# ---------------------------------------------------------------------------
def carte_chiffre(d, x, y, w, h, chiffre, legende, sur_nuit=False, taille=54):
    rect(d, x, y, w, h, CARTE if sur_nuit else NUIT)
    texte(d, x + 0.35, y + 0.28, w - 0.6, 1.0, chiffre, taille, VERT)
    texte(d, x + 0.35, y + 0.28 + taille / 72 * 1.25, w - 0.6, h - 1.4, legende, 24, CREME)


def frise(d, x, y, largeur, etapes, sur_nuit, compacte=False):
    """Frise horizontale : ligne verte, pastilles numérotées, date en gras, texte dessous."""
    dy_date, dy_texte = (0.82, 1.42) if compacte else (1.0, 1.75)
    n = len(etapes)
    pas = largeur / n
    ligne(d, x + pas / 2, y + 0.35, x + largeur - pas / 2, y + 0.35, VERT, 5)
    for i, (date, libelle) in enumerate(etapes):
        cx = x + pas * i + pas / 2
        p = rect(d, cx - 0.35, y, 0.7, 0.7, VERT, MSO_SHAPE.OVAL)
        tf = p.text_frame
        tf.text = str(i + 1)
        r = tf.paragraphs[0].runs[0]
        r.font.name, r.font.size, r.font.bold, r.font.color.rgb = POLICE, Pt(24), True, rgb(NUIT)
        tf.paragraphs[0].alignment = PP_ALIGN.CENTER
        texte(d, cx - pas / 2 + 0.25, y + dy_date, pas - 0.5, 0.6, date, 28 if compacte else 30, VERT if sur_nuit else NUIT,
              align=PP_ALIGN.CENTER)
        texte(d, cx - pas / 2 + 0.25, y + dy_texte, pas - 0.5, 2.0, libelle, 24,
              CREME if sur_nuit else NUIT, gras=False, align=PP_ALIGN.CENTER)


def puces_numerotees(d, x, y, w, items, couleur_texte, pas=1.25, taille=26):
    """Liste numérotée du Mont d'Est : carré vert numéroté, texte en gras."""
    for i, item in enumerate(items):
        yy = y + i * pas
        c = rect(d, x, yy + 0.02, 0.62, 0.62, VERT)
        tf = c.text_frame
        tf.text = f"{i + 1:02d}"
        r = tf.paragraphs[0].runs[0]
        r.font.name, r.font.size, r.font.bold, r.font.color.rgb = POLICE, Pt(19.5), True, rgb(NUIT)
        tf.paragraphs[0].alignment = PP_ALIGN.CENTER
        texte(d, x + 0.9, yy, w - 0.9, pas, item, taille, couleur_texte)


# Pictogrammes simples, dessinés en formes modifiables (blanc sur pastille bleu nuit)
def picto_parking(d, cx, cy):
    s = rect(d, cx - 0.42, cy - 0.42, 0.84, 0.84, BLANC, MSO_SHAPE.ROUNDED_RECTANGLE)
    tf = s.text_frame
    tf.text = "P"
    r = tf.paragraphs[0].runs[0]
    r.font.name, r.font.size, r.font.bold, r.font.color.rgb = POLICE, Pt(40), True, rgb(NUIT)
    tf.paragraphs[0].alignment = PP_ALIGN.CENTER
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE


def picto_maison(d, cx, cy):
    rect(d, cx - 0.5, cy - 0.55, 1.0, 0.5, BLANC, MSO_SHAPE.ISOSCELES_TRIANGLE)
    rect(d, cx - 0.38, cy - 0.06, 0.76, 0.56, BLANC)
    rect(d, cx - 0.11, cy + 0.16, 0.22, 0.34, NUIT)


def picto_camion(d, cx, cy):
    rect(d, cx - 0.62, cy - 0.38, 0.78, 0.58, BLANC)
    rect(d, cx + 0.2, cy - 0.16, 0.42, 0.36, BLANC, MSO_SHAPE.ROUND_1_RECTANGLE)
    for ox in (-0.38, 0.38):
        rect(d, cx + ox - 0.15, cy + 0.14, 0.3, 0.3, BLANC, MSO_SHAPE.OVAL, contour=NUIT).line.width = Pt(4)


def picto_vitesse(d, cx, cy):
    arc = rect(d, cx - 0.55, cy - 0.5, 1.1, 1.1, BLANC, MSO_SHAPE.BLOCK_ARC)
    arc.adjustments[0], arc.adjustments[1], arc.adjustments[2] = 180, 0, 0.16
    ligne(d, cx, cy + 0.05, cx + 0.33, cy - 0.3, BLANC, 6)
    rect(d, cx - 0.09, cy - 0.04, 0.18, 0.18, BLANC, MSO_SHAPE.OVAL)


def triangle(d, x, y, couleur, cote=0.36):
    t = rect(d, x, y, cote, cote * 0.88, couleur, MSO_SHAPE.ISOSCELES_TRIANGLE, contour=NUIT)
    t.line.width = Pt(1.25)



# ---------------------------------------------------------------------------
# Travaux dans les écoles du quartier
# ---------------------------------------------------------------------------
# Sources : réponse de la Direction des Bâtiments et de l'Énergie au cabinet (courriel de
# L. Vignel, 14 octobre 2026) pour les Gobelins et les montants des Charmilles ; tableau de suivi
# des travaux en régie 2026 (onglet « Travaux en régie ») ; comptes rendus des conseils d'école
# (printemps 2026). On n'affiche que le réalisé et le programmé ; le reste va dans les notes.
# Les deux écoles principales (cartes du haut) : (nom, montant, légende, [(état, [travaux])]).
ECOLES_PRINCIPALES = [
    ("École des Gobelins", "1,3 M€", "pour accueillir l'école des Richardets", [
        ("RÉALISÉ CETTE ANNÉE", ["Création de sanitaires",
                                 "Réfection des sols et des peintures",
                                 "Travaux électriques",
                                 "Clôtures et portails",
                                 "Rénovation de la cour et pose de pare-ballons"]),
    ]),
    ("Les Charmilles", "23 000 €", "pour l'assainissement et le hall du groupe scolaire", [
        ("FAIT", ["Mise en conformité du réseau d'assainissement (19 000 €)",
                  "Remise en état du hall : plâtrerie et peinture (4 000 €)",
                  "Faux plafonds remplacés, étais du réfectoire déposés",
                  "Portes réglées, poignée remplacée",
                  "Ventilateurs, films anti-UV et bancs dans la cour"]),
        ("PROGRAMMÉ", ["Infiltration et peinture, classe de CM1-CM2",
                       "Peinture de l'office du réfectoire"]),
    ]),
]

# Les autres écoles (cartes du bas) : (nom, [(fait ?, travaux)]).
AUTRES_ECOLES = [
    ("Les Yvris", [(True, "Drapeau de l'entrée remis en état"),
                   (False, "Peinture du hall élémentaire et du bureau de la direction")]),
    ("Maternelle des Richardets", [(True, "Un rafraîchisseur d'air"),
                                   (True, "Des films de protection solaire sur les vitrages")]),
    ("Paul-Serelle", [(False, "Sécurisation du carrefour, à l'étude"),
                      (False, "Réparation des fuites de la salle polyvalente")]),
]

NOTES_ECOLES_QUARTIER = (
    "Sources : Direction des Bâtiments et de l'Énergie, service Patrimoine Bâti (courriel du "
    "14 octobre 2026) ; tableau de suivi des travaux en régie 2026 ; comptes rendus des conseils "
    "d'école du printemps 2026.\n\n"
    "École des Gobelins : 1,3 million d'euros investis cette année au sein du groupe scolaire des "
    "Gobelins pour permettre l'installation et le déménagement de l'école des Richardets : création "
    "de sanitaires, réfection des revêtements de sols et peinture, travaux électriques, installation "
    "de clôtures et de portails, rénovation de la cour et mise en place de pare-ballons.\n\n"
    "Les Charmilles : 19 000 € pour la mise en conformité du réseau d'assainissement et 4 000 € "
    "d'aménagement et de remise en état du hall (pose de plaques de plâtre et mise en peinture). "
    "Les travaux « programmés » (classe de CM1-CM2, office du réfectoire) étaient prévus pour l'été "
    "2026 : leur réalisation reste à confirmer auprès de la Direction des Bâtiments. Même réserve "
    "pour la peinture du hall élémentaire des Yvris. Paul-Serelle : un réverbère devant le portail "
    "reste à programmer.\n\n"
    "Demandes en attente, à connaître (non projetées). Charmilles maternelle : fissures, toiture à "
    "refaire (travaux reportés pour analyser une fissure), chaudière en panne chaque année, "
    "brise-vues posés à l'envers ; les parents et la direction demandent le rapport d'expertise et "
    "la participation à la commission travaux. Charmilles élémentaire : allée de secours inachevée "
    "(environ 6 mètres, enjeu pour un élève en fauteuil), 13 chaises manquantes, écrans numériques, "
    "rapport d'expertise. Richardets élémentaire : barrière côté rue cassée, rideaux thermiques. "
    "Yvris maternelle : bouton d'ouverture du portail à rehausser, placards à sécuriser, barre pour "
    "le parc à vélos, chaleur au réfectoire. Paul-Serelle (synthèse des parents du 29 mai) : portes "
    "coupe-feu trop lourdes, détecteurs de fumée, extincteurs non fixés, alarme PPMS, interphone et "
    "grille de la maternelle hors service, fenêtres et stores défectueux, fuites, revêtement de cour.")


def diapo_ecoles_quartier(k):
    d = k.diapo(NUIT, "Les écoles du quartier", "Les travaux dans les écoles du quartier",
                NOTES_ECOLES_QUARTIER)
    # Cartes du haut : les Gobelins et les Charmilles, avec le montant investi
    largeur, y0, h = 8.8, 2.45, 5.4
    for i, (ecole, montant, legende, blocs) in enumerate(ECOLES_PRINCIPALES):
        x = 1.04 + i * (largeur + 0.3)
        rect(d, x, y0, largeur, h, CARTE)
        rect(d, x, y0, largeur, 0.12, VERT)
        texte(d, x + 0.35, y0 + 0.35, 4.6, 0.6, ecole, 28, BLANC)
        texte(d, x + 0.35, y0 + 0.95, 4.9, 0.7, legende, 16, GRIS, gras=False)
        texte(d, x + 4.6, y0 + 0.28, largeur - 4.95, 0.9, montant, 48, VERT, align=PP_ALIGN.RIGHT)
        texte(d, x + 4.6, y0 + 1.15, largeur - 4.95, 0.35, "INVESTIS CETTE ANNÉE", 13, VERT,
              align=PP_ALIGN.RIGHT, espacement=150)
        y = y0 + 1.65
        for etat, items in blocs:
            texte(d, x + 0.35, y, largeur - 0.7, 0.35, etat, 15, VERT, espacement=150)
            y += 0.4
            for item in items:
                rect(d, x + 0.37, y + 0.09, 0.17, 0.17, VERT if etat != "PROGRAMMÉ" else GRIS,
                     MSO_SHAPE.OVAL)
                texte(d, x + 0.7, y, largeur - 1.05, 0.38, item, 17, CREME)
                y += 0.38
            y += 0.05

    # Cartes du bas : les autres écoles du quartier
    largeur, y0, h = 5.77, 8.1, 2.2
    for i, (ecole, items) in enumerate(AUTRES_ECOLES):
        x = 1.04 + i * (largeur + 0.29)
        rect(d, x, y0, largeur, h, CARTE)
        rect(d, x, y0, 0.1, h, VERT)
        texte(d, x + 0.35, y0 + 0.22, largeur - 0.6, 0.5, ecole, 22, BLANC)
        y = y0 + 0.82
        for fait, item in items:
            rect(d, x + 0.37, y + 0.08, 0.16, 0.16, VERT if fait else GRIS, MSO_SHAPE.OVAL)
            texte(d, x + 0.68, y, largeur - 0.95, 0.7, item, 16, CREME)
            y += 0.3 * -(-len(item) // 44) + 0.12     # environ 44 caractères par ligne à 16 pt

    # Légende des pastilles
    for j, (couleur, libelle) in enumerate(((VERT, "réalisé"), (GRIS, "programmé ou à l'étude"))):
        x = 14.0 + j * 1.45
        rect(d, x, 10.53, 0.15, 0.15, couleur, MSO_SHAPE.OVAL)
        texte(d, x + 0.25, 10.46, 3.5, 0.3, libelle, 13, GRIS, gras=False)
    return d


# ---------------------------------------------------------------------------
# Périscolaire : mercredis et pause méridienne réunis sur une diapositive
# (chiffres de toute la ville, repris à l'identique des deux diapositives du Mont d'Est)
# ---------------------------------------------------------------------------
PERISCOLAIRE = [
    ("LE MERCREDI", [
        ("Places en accueil de loisirs", "Sept. 2025", "1 616", "Oct. 2026", "1 784", "+168 places, soit +10 %"),
        ("Animateurs recrutés", "Sept. 2025", "145", "Oct. 2026", "162", "+17 animateurs"),
    ]),
    ("À LA CANTINE", [
        ("Enfants accueillis", "2025", "5 543", "2026", "5 727", "+3,3 %"),
        ("Animateurs en maternelle", "2025", "199", "2026", "248", "+49 animateurs"),
        ("Animateurs en élémentaire", "2025", "123", "2026", "130", "+5 %"),
    ]),
]


def diapo_periscolaire(k, notes_mercredi, notes_cantine):
    d = k.diapo(NUIT, "Les écoles · le périscolaire", "Plus de places et plus d'animateurs",
                "À dire (non projeté) : chaque recrutement ouvre 8 places en maternelle et 12 en "
                "élémentaire ; les places libérées sont réattribuées chaque semaine à partir des listes "
                "d'attente ; les recrutements continuent, surtout pour les postes du mercredi.\n\n"
                "Mercredis — " + notes_mercredi + "\n\nPause méridienne — " + notes_cantine)
    texte(d, 1.04, 2.2, 15.8, 0.5, "Dans toute la ville, rentrée 2026 comparée à la rentrée 2025", 21, BLANC,
          gras=False)
    for c, (titre, lignes) in enumerate(PERISCOLAIRE):
        x, w = 1.04 + c * 9.22, 8.7
        ligne(d, x, 3.0, x + w, 3.0, VERT, 2)
        texte(d, x, 3.15, w, 0.45, titre, 21, VERT, espacement=150)
        for i, (libelle, an1, v1, an2, v2, evolution) in enumerate(lignes):
            y = 3.8 + i * 1.55
            texte(d, x, y, w, 0.4, libelle, 20, BLANC)
            texte(d, x, y + 0.55, 1.3, 0.35, an1, 15, GRIS)
            texte(d, x, y + 0.82, 2.0, 0.6, v1, 32, GRIS)
            texte(d, x + 2.05, y + 0.72, 0.6, 0.6, "→", 30, VERT, gras=False)
            texte(d, x + 2.75, y + 0.4, 1.4, 0.35, an2, 15, VERT)
            texte(d, x + 2.75, y + 0.62, 2.7, 0.85, v2, 48, BLANC)
            b = rect(d, x + 5.55, y + 0.8, w - 5.55, 0.5, VERT)
            tf = b.text_frame
            tf.text = evolution
            r = tf.paragraphs[0].runs[0]
            r.font.name, r.font.size, r.font.bold, r.font.color.rgb = POLICE, Pt(17), True, rgb(NUIT)
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf.margin_left = Inches(0.15)
    for c, (titre, phrase) in enumerate((
            ("CANTINES DE MATERNELLE", "96 % des cantines à 1 animateur pour 10 enfants ou mieux, contre 44 % en 2025"),
            ("CANTINES D'ÉLÉMENTAIRE", "14 cantines sur 26 à 1 pour 25, 19 d'ici mi-octobre. Objectif : toutes d'ici la fin "
                            "de l'année"))):
        x = 1.04 + c * 9.22
        rect(d, x, 8.65, 8.7, 1.75, CARTE)
        texte(d, x + 0.35, 8.85, 8.0, 0.4, titre, 17, VERT, espacement=150)
        texte(d, x + 0.35, 9.3, 8.0, 1.0, phrase, 21, BLANC)
    return d


# ---------------------------------------------------------------------------
# Zones bleues : parking du secteur du gymnase des Yvris
# (point fourni par le cabinet : 48°49'35.57" N, 2°35'00.63" E ; vues aériennes IGN)
# ---------------------------------------------------------------------------
def diapo_zones_bleues(k):
    d = k.diapo(NUIT, "Circulation et sécurité", "Les zones bleues de stationnement",
                "Parking situé dans le secteur du gymnase des Yvris, chemin de la Noisette, près de "
                "l'école élémentaire des Yvris et du collège Saint-Exupéry (point fourni : 48°49'35.57\" N, "
                "2°35'00.63\" E). Vues : orthophotographies IGN. Règles de la zone bleue à compléter : "
                "périmètre, durée de stationnement autorisée, date de mise en place, contrôle.")
    img = image(d, os.path.join(VISUELS, "Securite", "Securite_03_zone_bleue_parking.jpg"),
                1.04, 2.45, 11.2, 7.5, align="gauche")
    bas = (img.top + img.height) / 914400
    texte(d, 1.04, bas + 0.08, 11.2, 0.3, "© IGN – BD ORTHO", 11, "C9CCDA", gras=False, align=PP_ALIGN.RIGHT)
    image(d, os.path.join(VISUELS, "Securite", "Securite_04_zone_bleue_situation.jpg"),
          12.65, 2.45, 6.3, 4.2)
    texte(d, 12.65, 6.75, 6.3, 0.8, "Secteur du gymnase des Yvris, chemin de la Noisette", 20, BLANC)
    a_completer(d, 12.65, 7.65, 6.3, 2.3,
                "[Périmètre, durée de stationnement autorisée et date de mise en place à compléter]", sombre=True)
    return d


# ---------------------------------------------------------------------------
# Plan des bus du quartier
# ---------------------------------------------------------------------------
def fond_carte_bus(largeur=2400, hauteur=1350):
    """Fond de carte schématique, sans texte : fond bleu nuit, rues (IGN), quartier éclairci et
    cerné de pointillés, lignes de bus épaisses et décalées côte à côte, arrêts en points blancs.
    Renvoie (chemin de l'image, taille, arrêts, lignes, pastilles de numéro de ligne)."""
    import csv
    import json
    from PIL import ImageDraw
    from shapely.geometry import LineString, box, shape
    from shapely.ops import linemerge, unary_union
    import visuels_richardets as v

    quartiers = {f["properties"]["nom_quarti"]: shape(f["geometry"]) for f in v.geojson("quartiers-de-noisy-le-grand")}
    secteur = unary_union([quartiers[n] for n in v.SECTEUR_REUNION])
    (x0, y0), (x1, y1) = v.merc(*secteur.bounds[:2]), v.merc(*secteur.bounds[2:])
    w = max((x1 - x0) * 1.12, (y1 - y0) * 1.12 * largeur / hauteur)
    vue = v.Vue((x0 + x1) / 2, (y0 + y1) / 2, w, largeur, hauteur)

    img = Image.new("RGB", (largeur, hauteur), (11, 24, 74))
    d = ImageDraw.Draw(img)
    for a in vue.anneaux(secteur):
        d.polygon(a, fill=(22, 40, 104))
    # rues : plus l'importance IGN est forte (1), plus le trait est épais et clair
    style = {"1": (8, (70, 88, 150)), "2": (7, (66, 84, 146)), "3": (5, (56, 74, 136)),
             "4": (4, (50, 68, 130)), "5": (2, (42, 60, 120)), "6": (2, (36, 54, 112))}
    routes = json.load(open(os.path.join(ICI, ".cache", "routes_secteur.json")))["features"]
    for imp in ("6", "5", "4", "3", "2", "1"):
        ep, coul = style[imp]
        for f in routes:
            if f["properties"].get("importance") != imp or not f["geometry"]:
                continue
            g = f["geometry"]
            for brin in (g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]):
                d.line([vue.px(c[0], c[1]) for c in brin], fill=coul, width=ep, joint="curve")
    for a in vue.anneaux(secteur):
        v.pointilles(d, a, (235, 238, 245), 5, 30, 20)

    # lignes : tracé découpé au cadre, simplifié, puis décalé pour que les lignes qui partagent
    # une rue apparaissent côte à côte (comme sur les plans de réseau)
    traces = {t["route_short_name"]: t for t in json.load(open(os.path.join(ICI, ".cache", "traces_bus.json")))
              if t["route_short_name"] in LIGNES_PRINCIPALES}
    cadre = box(-40, -40, largeur + 40, hauteur + 40)
    decalage = {"310": -12, "312": 0, "320": 12}
    pastilles, lignes = [], []
    for nom in LIGNES_PRINCIPALES:
        geom = traces[nom]["shape"]["geometry"]
        brins = geom["coordinates"] if geom["type"] == "MultiLineString" else [geom["coordinates"]]
        # un seul sens de circulation par ligne : le brin le plus long dans le cadre, décalé d'un
        # seul tenant (fusionner les deux sens découperait le tracé en fragments)
        morceaux = [LineString([vue.px(*c) for c in b]).intersection(cadre) for b in brins if len(b) > 1]
        morceaux = [linemerge(m) if m.geom_type == "MultiLineString" else m for m in morceaux if not m.is_empty]
        principal = max(morceaux, key=lambda m: m.length)
        parties = list(principal.geoms) if hasattr(principal, "geoms") else [principal]
        parties = [p.simplify(2.5).offset_curve(decalage[nom], join_style=1) for p in parties if p.length > 30]
        parties = [p for p in parties if not p.is_empty and p.length > 30]

        def segments(p):
            return [q for q in (list(p.geoms) if hasattr(p, "geoms") else [p]) if len(q.coords) > 1]
        couleur = tuple(int(traces[nom]["route_color"][i:i + 2], 16) for i in (0, 2, 4))
        for p in parties:
            for q in segments(p):
                d.line(list(q.coords), fill=(11, 24, 74), width=24, joint="curve")
        for p in parties:
            for q in segments(p):
                d.line(list(q.coords), fill=couleur, width=15, joint="curve")
        longue = max(parties, key=lambda p: p.length)
        for t in {"310": (0.3, 0.72), "312": (0.3, 0.72), "320": (0.3,)}[nom]:
            pt = longue.interpolate(t, normalized=True)
            if 60 < pt.x < largeur - 60 and 40 < pt.y < hauteur - 40:
                pastilles.append((nom, traces[nom]["route_color"], pt.x, pt.y))
        lignes.append((nom, traces[nom]["route_color"]))

    arrets = []
    for r in csv.DictReader(open(SIGNALEMENTS, encoding="utf-8")):
        x, y = vue.px(float(r["longitude"]), float(r["latitude"]))
        n = r["signalements"].strip()
        arrets.append({"nom": r["arret"], "lignes": r["lignes"], "x": x, "y": y, "n": int(n) if n else None})
        d.ellipse([x - 12, y - 12, x + 12, y + 12], fill=(255, 255, 255), outline=(11, 24, 74), width=5)
    chemin = os.path.join(ICI, ".cache", "fond_carte_bus.png")
    img.save(chemin)
    return chemin, (largeur, hauteur), arrets, lignes, pastilles


# police aux mêmes dimensions qu'Arial gras (Liberation Sans), pour mesurer les étiquettes à 12 pt
from PIL import ImageFont as _IF
MESURE = _IF.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 12)

# position des étiquettes (en pouces, par rapport au point) pour éviter les chevauchements
DECALAGES = {
    "Moulin à Vent": (0.15, -0.12), "Le Fort": (-1.05, -0.45), "Cité des Hêtres": (-2.05, -0.12),
    "Rue de la Chapelle": (-1.85, -0.2), "Gabriel Péri": (-1.25, -0.15), "Place du Combat": (-1.15, 0.2),
    "Les Richardets - Centre": (0.05, 0.22), "Ballon - Chapelle": (-0.75, -0.48), "Le Closeau": (-1.1, -0.2),
    "La Butte aux Cailles": (0.15, -0.45), "Rue du Ballon": (0.15, -0.38), "Chapelle": (0.12, -0.42),
    "Victor Hugo": (-1.75, -0.15), "Les Graviers": (0.15, -0.05), "Rue des Aérostiers": (-1.85, -0.2),
    "Les Aérostiers": (0.15, -0.12), "Collège des Yvris": (-2.25, -0.47),
    "Les Yvris - Noisy-le-Grand RER": (-3.1, 0.05),
}


def diapo_carte_bus(k):
    import csv
    d = k.diapo(NUIT, "Services publics de proximité · les bus", "Les bus du quartier et vos signalements",
                "Plan des lignes 310, 312 et 320 qui traversent le quartier, avec leurs arrêts (données "
                "ouvertes d'Île-de-France Mobilités). Les arrêts Moulin à Vent (lignes 206, 207, 306, 310) "
                "et Les Aérostiers (ligne 212) sont en limite du quartier. Les pastilles vertes indiquent le "
                "nombre de signalements recueillis par le formulaire de la Ville pour chaque arrêt "
                "(472 signalements au total ; 156 rattachés avec certitude à un arrêt du quartier, les "
                "saisies ambiguës ne sont pas comptées). Les problèmes sont comptés en mentions : un "
                "signalement peut en citer plusieurs. Dans toute la ville : ligne 310, 312 signalements ; "
                "ligne 320, 76 ; ligne 312, 13 ; ligne 220, 51.")
    chemin, (lw, lh), arrets, lignes, pastilles = fond_carte_bus()
    mx, my, mw = 1.04, 2.45, 12.3
    mh = mw * lh / lw
    d.shapes.add_picture(chemin, Inches(mx), Inches(my), Inches(mw), Inches(mh))
    texte(d, mx, my + mh + 0.08, mw, 0.3, "Rues : IGN – BD TOPO · Lignes et arrêts : Île-de-France Mobilités",
          11, "C9CCDA", gras=False, align=PP_ALIGN.RIGHT)
    vmax = max([a["n"] for a in arrets if a["n"]] or [0])
    # pastilles de numéro posées sur les lignes
    for nom, couleur, px, py in pastilles:
        x, y = mx + px / lw * mw, my + py / lh * mh
        p = rect(d, x - 0.33, y - 0.19, 0.66, 0.38, couleur, MSO_SHAPE.ROUNDED_RECTANGLE, contour=NUIT)
        p.line.width = Pt(2)
        tf = p.text_frame
        tf.text = nom
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        r = tf.paragraphs[0].runs[0]
        r.font.name, r.font.size, r.font.bold, r.font.color.rgb = POLICE, Pt(14), True, rgb(NUIT)
        tf.paragraphs[0].alignment = PP_ALIGN.CENTER
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    # étiquettes : nom de l'arrêt, suivi du nombre de signalements dans une pastille verte
    for a in arrets:
        x, y = mx + a["x"] / lw * mw, my + a["y"] / lh * mh
        dx, dy = DECALAGES.get(a["nom"], (0.15, -0.1))
        nom = a["nom"].replace(" - ", " – ")
        largeur = MESURE.getlength(nom) / 72 + 0.12      # largeur réelle du nom, en pouces
        e = texte(d, x + dx, y + dy, largeur, 0.3, nom, 12, BLANC)
        e.text_frame.word_wrap = False
        e.fill.solid()
        e.fill.fore_color.rgb = rgb(NUIT)
        tf = e.text_frame
        tf.margin_left = tf.margin_right = Inches(0.05)
        tf.auto_size = None
        if a["n"]:
            c = rect(d, x + dx + largeur, y + dy, 0.42, 0.3, VERT)
            tf = c.text_frame
            tf.text = str(a["n"])
            tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
            r = tf.paragraphs[0].runs[0]
            r.font.name, r.font.size, r.font.bold, r.font.color.rgb = POLICE, Pt(13), True, rgb(NUIT)
            tf.paragraphs[0].alignment = PP_ALIGN.CENTER
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    # légende des lignes, sous la carte
    for i, (nom, couleur) in enumerate(lignes):
        x = mx + i * 2.6
        rect(d, x, my + mh + 0.55, 0.8, 0.2, couleur)
        texte(d, x + 0.95, my + mh + 0.42, 1.6, 0.45, f"Ligne {nom}", 20, BLANC)
    if not vmax:
        a_completer(d, 13.8, 2.5, 5.16, 7.0, "[Nombre de signalements par arrêt à compléter]", sombre=True)
        return d
    synthese = {}
    for r in csv.DictReader(open(SYNTHESE_BUS, encoding="utf-8")):
        synthese.setdefault(r["indicateur"], []).append((r["libelle"], int(r["valeur"])))
    total_quartier = synthese["total_quartier"][0][1]
    total_ville = synthese["total_ville"][0][1]
    texte(d, 13.8, 2.35, 5.2, 1.2, str(total_quartier), 72, VERT)
    texte(d, 13.8, 3.55, 5.2, 0.8, "signalements aux arrêts du quartier", 22, BLANC)
    texte(d, 13.8, 4.3, 5.2, 0.45, f"sur {total_ville} dans toute la ville", 17, GRIS, gras=False)
    texte(d, 13.8, 5.0, 5.2, 0.4, "ARRÊTS LES PLUS SIGNALÉS", 16, VERT, espacement=120)
    classement = sorted([a for a in arrets if a["n"]], key=lambda a: -a["n"])[:4]
    for i, a in enumerate(classement):
        y = 5.5 + i * 0.5
        texte(d, 13.8, y, 0.8, 0.45, str(a["n"]), 22, VERT)
        texte(d, 14.6, y + 0.04, 4.4, 0.45, a["nom"].replace(" - ", " – "), 18, BLANC)
    texte(d, 13.8, 7.65, 5.2, 0.4, "PROBLÈMES LES PLUS CITÉS", 16, VERT, espacement=120)
    problemes = sorted(synthese["probleme_quartier"], key=lambda p: -p[1])[:3]
    pmax = problemes[0][1]
    for i, (libelle, n) in enumerate(problemes):
        y = 8.15 + i * 0.72
        libelle = libelle.replace("Horaires erronés sur l'affichage en temps réel", "Affichage en temps réel erroné")
        texte(d, 13.8, y, 5.2, 0.35, libelle, 15, BLANC, gras=False)
        rect(d, 13.8, y + 0.36, 4.3 * n / pmax, 0.22, VERT)
        texte(d, 13.8 + 4.3 * n / pmax + 0.1, y + 0.28, 0.8, 0.35, str(n), 15, VERT)
    return d

# ---------------------------------------------------------------------------
# Piste cyclable vers le centre-ville (plan d'aménagement fourni par le cabinet)
# ---------------------------------------------------------------------------
PISTE = "E8473F"   # rouge de la piste cyclable sur le plan fourni


def diapo_piste_cyclable(k):
    d = k.diapo(CREME, "Circulation et sécurité", "Une nouvelle piste cyclable pour joindre le centre",
                "Plan d'aménagement du carrefour et de la piste cyclable (en rouge), avec la coupe de la "
                "voie en encart.")
    rect(d, 1.04, 2.55, 17.9, 6.95, BLANC)
    image(d, os.path.join(VISUELS, "Mobilites", "Mobilites_01_piste_cyclable_plan.png"),
          1.19, 2.7, 17.6, 6.65)
    yl = 9.85
    rect(d, 1.04, yl, 0.9, 0.36, PISTE)
    texte(d, 2.15, yl - 0.05, 8.0, 0.45, "Piste cyclable", 22, NUIT)
    return d


# ---------------------------------------------------------------------------
# Les commerces de l'avenue Médéric
# (commerces_mederic.csv, tiré de la base Sirene par commerces_mederic.py)
# ---------------------------------------------------------------------------
COMMERCES = os.path.join(ICI, "commerces_mederic.csv")
# couleur de chaque catégorie sur le plan, reprise en pastille dans les cartes du bas
COULEURS_COMMERCES = {"Alimentation": VERT, "Restaurants et cafés": JAUNE, "Coiffure et beauté": "C49BE0",
                      "Santé": "6FB7E9", "Autres commerces": "F28C6B"}
EXEMPLES_COMMERCES = {"Alimentation": "boulangeries, boucherie, supérettes, surgelés",
                      "Restaurants et cafés": "restaurants, restauration rapide, cafés",
                      "Coiffure et beauté": "salons de coiffure, institut de beauté",
                      "Santé": "pharmacie, opticiens, vétérinaire",
                      "Autres commerces": "garage, station-service, fleuriste, électroménager, mercerie"}

def fond_plan_mederic(commerces, largeur=2600, hauteur=640):
    """Plan schématique sans texte : rues IGN sur fond bleu nuit, avenue Médéric en clair.
    Renvoie (chemin de l'image, vue, tracé de l'avenue en pixels)."""
    import json
    from PIL import ImageDraw
    from shapely.geometry import LineString
    from shapely.ops import linemerge, unary_union
    import visuels_richardets as v

    lons = [c["lon"] for c in commerces]
    lats = [c["lat"] for c in commerces]
    (x0, y0), (x1, y1) = v.merc(min(lons), min(lats)), v.merc(max(lons), max(lats))
    vue = v.Vue((x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) * 1.12, largeur, hauteur)
    routes = json.load(open(os.path.join(ICI, ".cache", "routes_mederic.json")))["features"]

    img = Image.new("RGB", (largeur, hauteur), (11, 24, 74))
    d = ImageDraw.Draw(img)
    style = {"1": (9, (70, 88, 150)), "2": (8, (66, 84, 146)), "3": (7, (60, 78, 140)),
             "4": (6, (56, 74, 136)), "5": (4, (46, 64, 124)), "6": (3, (38, 56, 114))}
    avenue = []
    for imp in ("6", "5", "4", "3", "2", "1"):
        ep, coul = style[imp]
        for f in routes:
            p = f["properties"]
            if p.get("importance") != imp or not f["geometry"]:
                continue
            brin = [vue.px(*c[:2]) for c in f["geometry"]["coordinates"]]
            if p.get("nom_collaboratif_gauche") == "AV MEDERIC":
                avenue.append(LineString(brin))
            d.line(brin, fill=coul, width=ep, joint="curve")
    axe = linemerge(unary_union(avenue))
    parties = sorted(axe.geoms if hasattr(axe, "geoms") else [axe], key=lambda l: l.length, reverse=True)
    # tracé principal continu d'ouest en est (les bretelles courtes sont écartées)
    coords = []
    for brin in sorted([p for p in parties if p.length > 60], key=lambda l: min(c[0] for c in l.coords)):
        cs = list(brin.coords)
        coords += cs if cs[0][0] < cs[-1][0] else cs[::-1]
    axe = LineString(coords)
    d.line(coords, fill=(11, 24, 74), width=30, joint="curve")
    d.line(coords, fill=(214, 220, 236), width=20, joint="curve")
    chemin = os.path.join(ICI, ".cache", "fond_plan_mederic.png")
    img.save(chemin)
    return chemin, vue, axe


def diapo_commerces_mederic(k):
    import csv
    from shapely.geometry import Point
    commerces = [{"nom": r["nom"], "numero": r["numero"], "categorie": r["categorie"],
                  "lon": float(r["longitude"]), "lat": float(r["latitude"])}
                 for r in csv.DictReader(open(COMMERCES, encoding="utf-8"))]
    par_categorie = {c: [m for m in commerces if m["categorie"] == c] for c in COULEURS_COMMERCES}
    d = k.diapo(NUIT, "Équipements et cadre de vie", "Les commerces de l'avenue Médéric",
                "Source : base Sirene des entreprises (données ouvertes de la Ville, mise à jour du "
                "15 août 2026), établissements actifs de l'avenue Médéric qui tiennent une boutique ou "
                "une salle ouverte au public ; chaque point est placé à l'adresse déclarée (Base "
                "Adresse Nationale). Ne sont pas comptés : la vente à distance ou à domicile, les "
                "meublés de tourisme, les sièges domiciliés et les cabinets de santé libéraux de "
                "l'avenue (deux médecins généralistes au 50, des infirmiers aux 92 et 114, des "
                "kinésithérapeutes et ostéopathes). Sirene peut garder actif un commerce fermé "
                "sans radiation : liste à confirmer par le service du commerce.\n\n"
                + "\n".join(f"{c} ({len(ms)}) : " + ", ".join(f"{m['nom'].title()} ({m['numero']})" for m in ms)
                            for c, ms in par_categorie.items()))

    # Plan schématique de l'avenue
    chemin, vue, axe = fond_plan_mederic(commerces)
    mx, my, mw = 1.04, 2.45, 17.9
    mh = mw * vue.hauteur / vue.largeur
    d.shapes.add_picture(chemin, Inches(mx), Inches(my), Inches(mw), Inches(mh))
    texte(d, mx, my + mh + 0.06, mw, 0.3, "Rues : IGN – BD TOPO · Commerces : base Sirene (Insee), "
          "établissements actifs en août 2026", 11, "C9CCDA", gras=False, align=PP_ALIGN.RIGHT)
    pouce = mw / vue.largeur

    # points des commerces : rangés en chapelet de part et d'autre de l'avenue, chacun du côté de
    # son adresse et dans l'ordre de sa position réelle, écartés juste assez pour ne pas se toucher
    pas, ecart = 0.3 / pouce, 0.3 / pouce                # en pixels du plan
    cotes = {1: [], -1: []}
    for m in commerces:
        pt = Point(vue.px(m["lon"], m["lat"]))
        s = axe.project(pt)
        a, b = axe.interpolate(max(s - 5, 0)), axe.interpolate(min(s + 5, axe.length))
        sens = 1 if (b.x - a.x) * (pt.y - a.y) - (b.y - a.y) * (pt.x - a.x) > 0 else -1
        cotes[sens].append([s, m])
    for sens, liste in cotes.items():
        liste.sort(key=lambda e: e[0])
        blocs = [[e] for e in liste]                     # blocs de points contigus, centrés sur leur position
        while True:
            debuts = [sum(e[0] for e in bl) / len(bl) - (len(bl) - 1) * pas / 2 for bl in blocs]
            i = next((i for i in range(1, len(blocs)) if debuts[i] < debuts[i - 1] + len(blocs[i - 1]) * pas), None)
            if i is None:
                break
            blocs[i - 1:i + 1] = [blocs[i - 1] + blocs[i]]
        for debut, bl in zip(debuts, blocs):
            for j, (_, m) in enumerate(bl):
                s = min(max(debut + j * pas, 0), axe.length)
                a, b = axe.interpolate(max(s - 5, 0)), axe.interpolate(min(s + 5, axe.length))
                n = ((b.y - a.y), -(b.x - a.x))
                ln = (n[0] ** 2 + n[1] ** 2) ** 0.5
                c = axe.interpolate(s)
                x = mx + (c.x - sens * n[0] / ln * ecart) * pouce
                y = my + (c.y - sens * n[1] / ln * ecart) * pouce
                p = rect(d, x - 0.12, y - 0.12, 0.24, 0.24, COULEURS_COMMERCES[m["categorie"]], MSO_SHAPE.OVAL,
                         contour=NUIT)
                p.line.width = Pt(1.5)
                p.name = f"{m['nom'].title()} ({m['numero']})"

    nom_av = texte(d, mx + 0.25, my + 0.18, 3.6, 0.4, "Avenue Médéric", 18, BLANC)
    nom_av.name = "Nom de l'avenue"

    # Synthèse : total, puis une carte par catégorie (qui sert de légende au plan)
    yb = my + mh + 0.55
    texte(d, 1.04, yb - 0.1, 3.3, 1.3, str(len(commerces)), 88, VERT)
    texte(d, 1.04, yb + 1.35, 3.3, 1.3, "commerces et services ouverts au public", 20, BLANC)
    largeur = (17.9 - 3.6 - 4 * 0.22) / 5
    for i, (cat, ms) in enumerate(par_categorie.items()):
        x = 4.64 + i * (largeur + 0.22)
        h = 10.55 - yb
        rect(d, x, yb, largeur, h, CARTE)
        rect(d, x + 0.3, yb + 0.33, 0.3, 0.3, COULEURS_COMMERCES[cat], MSO_SHAPE.OVAL)
        texte(d, x + 0.75, yb + 0.1, largeur - 0.95, 0.75, str(len(ms)), 40, BLANC)
        texte(d, x + 0.3, yb + 0.95, largeur - 0.55, 0.75, cat, 19, VERT)
        texte(d, x + 0.3, yb + 1.75, largeur - 0.55, h - 1.9, EXEMPLES_COMMERCES[cat], 15, CREME, gras=False)
    return d


# ---------------------------------------------------------------------------
# Les diapositives
# ---------------------------------------------------------------------------
def construire():
    k = Deck()
    prs = k.prs
    gabarit = {n: prs.slides[n - 1] for n in (G_COUVERTURE, G_SOMMAIRE, G_QUESTIONS)}

    # 1. Couverture -------------------------------------------------------------
    c = gabarit[G_COUVERTURE]
    remplacer_texte(c, "Text 3", "RÉUNION PUBLIQUE —")
    remplacer_texte(c, "Text 4", "QUARTIER DES", "RICHARDETS")
    remplacer_texte(c, "Text 5", "Mercredi 14 octobre 2026 — 19 h — Victoria Park")
    remplacer_image(c, "Image 0", vue_aerienne(2.5700, 48.8300, 3200, (1920, 1080)))
    texte(c, 15.6, 10.75, 4.1, 0.3, "© IGN – BD ORTHO", 12, "C9CCDA", gras=False, align=PP_ALIGN.RIGHT)
    notes(c, "Accueil des habitants par Vincent Monnier, Maire de Noisy-le-Grand. Réunion du cycle "
             "des réunions publiques organisées dans tous les quartiers.")

    # 2. Sommaire ----------------------------------------------------------------
    parties = ["L'école des Richardets et le périscolaire", "Circulation et sécurité", "Services publics de proximité",
               "Équipements et cadre de vie", "Santé et accueil des seniors"]
    s = gabarit[G_SOMMAIRE]
    for i in range(1, 9):
        if i <= len(parties):
            remplacer_texte(s, f"Partie {i}", parties[i - 1])
        else:
            for nom in (f"Numero {i}", f"Partie {i}", f"Separateur {i - 1}"):
                el = forme(s, nom)._element
                el.getparent().remove(el)
    notes(s, "Présenter les cinq parties de la soirée.")

    # 3. Un déménagement organisé par la Ville -----------------------------------
    d = k.diapo(NUIT, "L'école des Richardets", "Un déménagement organisé par la Ville",
                "Le déménagement a été organisé par la Ville, après la fin de l'année scolaire pour le "
                "matériel scolaire. Le matériel de restauration a été déménagé dès le 1er juillet pour "
                "permettre l'installation aux Gobelins le 20 juillet.")
    frise(d, 1.04, 3.75, 17.9, [
        ("1er juillet 2026", "Déménagement du matériel de restauration"),
        ("6 juillet 2026", "Déménagement du matériel scolaire, après la fin de l'année"),
        ("20 juillet 2026", "Installation à l'école des Gobelins"),
    ], sur_nuit=True)
    rect(d, 1.04, 8.45, 17.9, 1.55, VERT)
    texte(d, 1.5, 8.45, 17.0, 1.55, "Un déménagement entièrement pris en charge par un prestataire de "
          "la Ville : mise en carton, transport et réinstallation", 26, NUIT, ancre=MSO_ANCHOR.MIDDLE)

    # 4. Le chantier de l'école ----------------------------------------------------
    d = k.diapo(CREME, "L'école des Richardets", "Le chantier de l'école",
                "Source : Direction des Bâtiments et de l'Énergie (9 octobre 2026). Les travaux ont "
                "démarré en septembre, après la notification des marchés de travaux, pour une durée "
                "prévue de 20 mois. La réouverture de l'école agrandie et rénovée est prévue pour la "
                "rentrée de septembre 2028.")
    rect(d, 1.04, 2.55, 10.6, 4.1, NUIT)
    texte(d, 1.5, 2.85, 9.8, 0.5, "RÉOUVERTURE PRÉVUE EN", 22, VERT, espacement=150)
    texte(d, 1.5, 3.35, 9.8, 1.6, "septembre 2028", 80, BLANC)
    texte(d, 1.5, 5.0, 9.8, 1.4, "Les élèves sont accueillis à l'école des Gobelins pendant toute "
          "la durée du chantier", 24, CREME)
    carte_chiffre(d, 1.04, 6.95, 5.15, 3.3, "Sept. 2026", "démarrage des travaux", taille=48)
    carte_chiffre(d, 6.49, 6.95, 5.15, 3.3, "20 mois", "de travaux prévus, pour une école agrandie "
                  "et rénovée", taille=48)
    a_completer(d, 12.2, 2.55, 6.76, 7.7, "[Photo du chantier à fournir]")

    # 5. Le coût d'une annulation -------------------------------------------------
    d = k.diapo(NUIT, "L'école des Richardets", "Le coût d'une annulation",
                "Source : Direction des Bâtiments et de l'Énergie (9 octobre 2026). Le coût de "
                "l'annulation des marchés de travaux est difficile à estimer : il pourrait représenter "
                "entre plusieurs centaines de milliers d'euros et quelques millions d'euros. Dépenses "
                "déjà réalisées : études préalables et diagnostics (environ 150 000 €), études de "
                "conception et autorisations dont le permis de construire (environ 400 000 €), "
                "déménagement de l'école aux Gobelins (environ 1 300 000 €). Non compté : l'acquisition "
                "du bâtiment des Gobelins, pour un peu plus de 5 000 000 €.")
    texte(d, 1.04, 2.55, 17.9, 2.4, ["De plusieurs centaines de milliers d'euros", "à quelques millions d'euros"],
          50, VERT, interligne=1.05)
    texte(d, 1.04, 4.85, 17.9, 0.6, "Le coût qu'aurait représenté l'annulation de la construction de l'école",
          28, BLANC)
    texte(d, 1.04, 6.0, 17.9, 0.5, "DÉJÀ ENGAGÉ", 21, VERT, espacement=150)
    for i, (montant, objet) in enumerate((
            ("Environ 150 000 €", "études préalables et diagnostics"),
            ("Environ 400 000 €", "études de conception et autorisations, dont le permis de construire"),
            ("Environ 1 300 000 €", "déménagement de l'école aux Gobelins"))):
        carte_chiffre(d, 1.04 + i * 6.09, 6.6, 5.72, 3.3, montant, objet, sur_nuit=True, taille=34)

    # 6. Des travaux dans toutes les écoles ----------------------------------------
    d = k.diapo(CREME, "L'école des Richardets · et les autres écoles", "Le plan Petits travaux dans les écoles",
                "Plan Petits travaux mené cet été dans les écoles ; plan fraîcheur pour mieux protéger "
                "les élèves.")
    texte(d, 1.04, 2.5, 4.0, 2.0, "35", 120, NUIT)
    ombre_verte(texte(d, 4.2, 2.95, 14.7, 1.4, "opérations sur 19 sites cet été", 48, NUIT))
    texte(d, 1.04, 4.75, 17.9, 0.5, "PLAN FRAÎCHEUR", 21, VERT, espacement=150)
    for i, (chiffre, legende) in enumerate((("3 600 m", "de film solaire"), ("67", "climatiseurs"),
                                            ("400", "brumisateurs"), ("618", "ventilateurs"))):
        carte_chiffre(d, 1.04 + i * 4.5, 5.3, 4.18, 2.6, chiffre, legende)
    a_completer(d, 1.04, 8.25, 17.9, 1.95,
                "[Travaux réalisés à l'école des Gobelins et à la maternelle des Yvris à compléter]")

    # 7. Circulation aux abords des écoles -------------------------------------------
    d = k.diapo(NUIT, "Circulation et sécurité", "Circulation aux abords des écoles",
                "Éléments de la Direction de l'Environnement et de l'Espace Public (à l'oral, non "
                "projetés) : autour de l'école des Gobelins, un dépose-minute d'environ 15 places pour "
                "les parents, ainsi que les abords du CTM ; pas d'autre réserve de stationnement. "
                "Circulation : attente du retrait du transformateur situé sur la chaussée pour que la "
                "Société des grands projets termine ses travaux, soit encore environ 12 mois (8 mois "
                "d'attente puis les travaux). Sujet également évoqué : le dernier ouvrage de la SGP, "
                "l'ouvrage Médéric.")
    sujets = [(picto_parking, "Circulation et stationnement aux abords de l'école des Gobelins"),
              (picto_maison, "Stationnement gênant dans les rues pavillonnaires"),
              (picto_camion, "Véhicules de livraison"),
              (picto_vitesse, "Vitesse excessive avenue Médéric")]
    for i, (picto, libelle) in enumerate(sujets):
        x = 1.04 + i * 4.5
        rect(d, x, 2.55, 4.18, 4.6, CARTE)
        rect(d, x + 1.29, 2.9, 1.6, 1.6, VERT, MSO_SHAPE.OVAL)
        rect(d, x + 1.39, 3.0, 1.4, 1.4, NUIT, MSO_SHAPE.OVAL)
        picto(d, x + 2.09, 3.7)
        texte(d, x + 0.3, 4.8, 3.58, 2.2, libelle, 24, BLANC, align=PP_ALIGN.CENTER)
    a_completer(d, 1.04, 7.55, 17.9, 2.65, "[Mesures prises à compléter]", sombre=True)

    # 8. La vidéoprotection dans le quartier -------------------------------------------
    d = k.diapo(CREME, "Circulation et sécurité", "La vidéoprotection dans le quartier",
                "Carte des caméras du quartier : en vert les caméras en service, en jaune les caméras "
                "en cours d'installation.")
    img = image(d, os.path.join(VISUELS, "Securite", "Securite_01_cameras_quartier.png"),
                1.04, 2.45, 11.9, 6.9, align="gauche")
    yl = img.top / 914400 + img.height / 914400 + 0.3
    triangle(d, 1.04, yl, VERT)
    texte(d, 1.55, yl - 0.04, 4.2, 0.45, "Caméra en service", 22, NUIT)
    triangle(d, 5.6, yl, JAUNE)
    texte(d, 6.11, yl - 0.04, 6.5, 0.45, "Caméra en cours d'installation", 22, NUIT)
    carte_chiffre(d, 13.4, 2.45, 5.56, 2.55, "29", "caméras en service", taille=66)
    carte_chiffre(d, 13.4, 5.2, 5.56, 2.55, "2", "caméras en cours d'installation", taille=66)
    image(d, os.path.join(VISUELS, "Securite", "Securite_02_cameras_allee_du_Closeau.png"),
          13.4, 7.95, 5.56, 1.6)

    # 9. Non à la fermeture du bureau de poste -------------------------------------------
    d = k.diapo(NUIT, "Services publics de proximité", "Non à la fermeture du bureau de poste des Richardets",
                "La fermeture avait été décidée par La Poste sans information des habitants. Le Maire "
                "s'y est opposé et a demandé un délai ainsi que la sauvegarde d'activités postales.")
    texte(d, 1.04, 2.45, 10.9, 1.2, "Un service de proximité essentiel, auquel les habitants sont attachés",
          30, VERT)
    frise(d, 1.04, 4.1, 10.9, [
        ("15 juin 2026", "Courrier du Maire à La Poste"),
        ("Juin 2026", "Le Maire reçoit le délégué de La Poste et s'oppose à la fermeture"),
        ("10 juillet 2026", "Nouvel échange entre le Maire et La Poste"),
    ], sur_nuit=True)
    image(d, os.path.join(VISUELS, "Services", "Services_01_bureau_de_poste.jpg"), 12.45, 2.45, 6.5, 5.0)
    a_completer(d, 12.45, 7.75, 6.5, 2.45, "[Situation actuelle du bureau à compléter]", sombre=True)

    # 10. Le réseau de bus ---------------------------------------------------------------
    d = k.diapo(CREME, "Services publics de proximité", "Le réseau de bus",
                "Formulaire de signalement de la Ville : 400 signalements. Le Maire a obtenu la "
                "suspension de la modification non concertée du trajet de la ligne 220.")
    rect(d, 1.04, 2.5, 6.6, 6.4, NUIT)
    texte(d, 1.5, 2.95, 5.8, 2.0, "400", 120, VERT)
    texte(d, 1.5, 5.0, 5.8, 1.6, "signalements recueillis par la Ville", 30, BLANC)
    puces_numerotees(d, 8.3, 2.6, 10.6, [
        "Le Maire a rencontré deux fois Île-de-France Mobilités",
        "La modification non concertée du trajet de la ligne 220 a été suspendue",
        "Un courrier aux exploitants pour exiger un retour au niveau de service prévu et "
        "l'application des pénalités",
    ], NUIT, pas=2.05)
    ligne(d, 1.04, 9.35, 18.96, 9.35, VERT, 2)
    texte(d, 1.04, 9.55, 17.9, 0.6, "Le réseau est organisé par Île-de-France Mobilités et exploité "
          "par Keolis et RATP Cap", 22, NUIT, gras=False)

    # 11. La tribune du stade Alain-Mimoun ----------------------------------------------
    d = k.diapo(NUIT, "Équipements et cadre de vie", "La tribune du stade Alain-Mimoun",
                "Arbitrages validés lors du dernier comité de suivi. Points à connaître (non projetés) : "
                "glissement du calendrier prévisionnel en raison de nouvelles études ; actualisation du "
                "dossier pour le prochain comité de pilotage ; révision de la programmation pluriannuelle "
                "des investissements et nouvelles demandes de subventions ; vigilance du service des "
                "sports sur l'emprise du chantier sur la piste d'athlétisme.")
    colonnes = [("Le bâtiment", ["Des toitures solarisées", "Une façade végétalisée", "L'installation des sièges"]),
                ("Les espaces verts", ["Les arbres replantés avant tout abattage",
                                       "Une compensation végétale doublée",
                                       "Une haie contre les nuisances sonores"])]
    for i, (tete, items) in enumerate(colonnes):
        x = 1.04 + i * 5.85
        rect(d, x, 2.5, 5.55, 5.45, CARTE)
        rect(d, x, 2.5, 5.55, 0.12, VERT)
        texte(d, x + 0.4, 2.9, 4.8, 0.5, tete.upper(), 22, VERT, espacement=150)
        for j, item in enumerate(items):
            yy = 3.7 + j * 1.38
            rect(d, x + 0.4, yy + 0.12, 0.26, 0.26, VERT, MSO_SHAPE.OVAL)
            texte(d, x + 0.9, yy, 4.35, 1.3, item, 24, BLANC)
    a_completer(d, 1.04, 8.3, 11.4, 1.9, "[Montant et calendrier à compléter]", sombre=True)
    image(d, os.path.join(VISUELS, "Equipements", "Equipements_01_stade_Alain_Mimoun.jpg"),
          12.95, 2.5, 6.0, 5.45)
    a_completer(d, 12.95, 8.3, 6.0, 1.9, "[Perspective de la tribune à fournir]", sombre=True)

    # 12. Une nouvelle aire de jeux rue de la Chapelle --------------------------------------
    d = k.diapo(CREME, "Équipements et cadre de vie", "Une nouvelle aire de jeux rue de la Chapelle",
                "Source : Direction de l'Environnement et de l'Espace Public. Square du boulevard des "
                "Astronautes, entre la rue de la Chapelle et la rue des Pléiades : concertation avec les "
                "riverains cet hiver sur les aires de jeux et les équipements, travaux à la fin du "
                "printemps, plantations à l'automne. Les crédits sont prévus pour 2027.")
    image(d, os.path.join(VISUELS, "Equipements", "Equipements_02_square_Astronautes_plan.png"),
          1.04, 2.4, 11.2, 6.3, align="gauche")
    texte(d, 12.75, 2.45, 6.2, 0.45, "LE SQUARE", 21, VERT, espacement=150)
    puces = ["Square du boulevard des Astronautes, rue de la Chapelle",
             "Des jeux pour les enfants de 1 an à 10-12 ans",
             "Sol souple, bancs, chaises longues et tables de jeux en plastique recyclé",
             "Le séquoia géant et les arbres existants conservés"]
    for j, item in enumerate(puces):
        yy = 3.05 + j * 1.42
        rect(d, 12.75, yy + 0.13, 0.24, 0.24, VERT, MSO_SHAPE.OVAL)
        texte(d, 13.2, yy, 5.75, 1.35, item, 22, NUIT)
    frise(d, 1.04, 8.75, 17.9, [("Cet hiver", "Concertation avec les riverains"),
                                ("Fin du printemps", "Travaux"), ("À l'automne", "Plantations")],
          sur_nuit=False, compacte=True)

    # 13. Le Fort de Villiers ------------------------------------------------------------
    d = k.diapo(NUIT, "Équipements et cadre de vie", "Le Fort de Villiers", "")
    image(d, os.path.join(VISUELS, "Equipements", "Equipements_03_fort_de_Villiers.jpg"), 1.04, 2.5, 10.6, 7.7,
          align="gauche")
    a_completer(d, 12.2, 2.5, 6.76, 7.7, "[Contenu à compléter]", sombre=True)

    # 14. Une maison médicale ---------------------------------------------------------------
    d = k.diapo(CREME, "Santé et accueil des seniors", "Une maison médicale", "")
    a_completer(d, 1.04, 2.6, 17.9, 7.6, "[Contenu à compléter : localisation, praticiens attendus, calendrier]")

    # 15. Un projet de maison de retraite ----------------------------------------------------
    d = k.diapo(NUIT, "Santé et accueil des seniors", "Un projet de maison de retraite", "")
    a_completer(d, 1.04, 2.6, 17.9, 7.6,
                "[Contenu à compléter : type d'établissement, nombre de places, état d'avancement]", sombre=True)

    # 16. Vos questions -------------------------------------------------------------------
    notes(gabarit[G_QUESTIONS], "Temps d'échange avec la salle.")

    # Diapositives habituelles du cycle -----------------------------------------------------
    habituelles = {n: prs.slides[n - 1] for n in (G_QR_ACCUEIL, G_QR_SORTIE, G_PERI_MERCREDI,
                                                    G_PERI_CANTINE, G_KEOLIS)}
    for n in (G_QR_ACCUEIL, G_QR_SORTIE):
        remplacer_texte(habituelles[n], "Text 0", "RÉUNION PUBLIQUE · QUARTIER DES RICHARDETS")
    remplacer_texte(habituelles[G_PERI_MERCREDI], "Text 0", "LES ÉCOLES · LE PÉRISCOLAIRE · MERCREDIS")
    remplacer_texte(habituelles[G_PERI_CANTINE], "Text 0", "LES ÉCOLES · LE PÉRISCOLAIRE · PAUSE MÉRIDIENNE")
    remplacer_texte(habituelles[G_KEOLIS], "Text 0", "SERVICES PUBLICS DE PROXIMITÉ · LES BUS")
    notes(habituelles[G_KEOLIS], "Courrier du Maire du 20 septembre 2026 à la direction générale de Keolis sur "
          "les dysfonctionnements des lignes : retards, suppressions, fréquences non respectées, information "
          "voyageurs défaillante. Demandes : sanctions contractuelles, réunion en mairie avec Keolis et "
          "Île-de-France Mobilités, plan d'actions immédiat.")
    n_carte = len(prs.slides._sldIdLst) + 1
    diapo_carte_bus(k)

    diapo_ecoles_quartier(k)
    diapo_periscolaire(k, habituelles[G_PERI_MERCREDI].notes_slide.notes_text_frame.text,
                       habituelles[G_PERI_CANTINE].notes_slide.notes_text_frame.text)
    diapo_piste_cyclable(k)
    diapo_zones_bleues(k)
    diapo_commerces_mederic(k)
    nv = k.nouvelles
    ordonner(prs, [G_QR_ACCUEIL, G_COUVERTURE, G_SOMMAIRE] + nv[0:4] + [nv[14], nv[15]]
             + [nv[4], nv[16], nv[5], nv[17]] + nv[6:8] + [n_carte, G_KEOLIS] + nv[8:10] + [nv[18]]
             + nv[10:13] + [G_QUESTIONS, G_QR_SORTIE])
    prs.save(SORTIE)
    print("Écrit :", SORTIE, "-", len(prs.slides._sldIdLst), "diapositives")


if __name__ == "__main__":
    construire()
