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
# Plan des bus du quartier
# ---------------------------------------------------------------------------
def fond_carte_bus(largeur=2400, hauteur=1350):
    """Fond de carte sans texte : photographie aérienne, secteur en couleur, lignes et arrêts.
    Renvoie (chemin de l'image, fonction lon/lat -> pixel, arrêts, lignes)."""
    import csv
    import json
    from PIL import ImageDraw, ImageEnhance, ImageFilter, ImageOps
    from shapely.geometry import shape
    from shapely.ops import unary_union
    import visuels_richardets as v

    quartiers = {f["properties"]["nom_quarti"]: shape(f["geometry"]) for f in v.geojson("quartiers-de-noisy-le-grand")}
    secteur = unary_union([quartiers[n] for n in v.SECTEUR_REUNION])
    (x0, y0), (x1, y1) = v.merc(*secteur.bounds[:2]), v.merc(*secteur.bounds[2:])
    w = max((x1 - x0) * 1.12, (y1 - y0) * 1.12 * largeur / hauteur)
    vue = v.Vue((x0 + x1) / 2, (y0 + y1) / 2, w, largeur, hauteur)
    photo = vue.photo(zoom_max=18)
    gris = ImageEnhance.Brightness(ImageOps.grayscale(photo).convert("RGB")).enhance(0.6)
    vif = ImageEnhance.Brightness(ImageEnhance.Color(photo).enhance(0.9)).enhance(0.85)
    img = Image.composite(vif, gris, v.masque(vue, secteur, flou=2)).convert("RGBA")
    d = ImageDraw.Draw(img)
    for a in vue.anneaux(secteur):
        v.pointilles(d, a, (255, 255, 255, 230), 5, 30, 20)

    traces = {t["route_short_name"]: t for t in json.load(open(os.path.join(ICI, ".cache", "traces_bus.json")))
              if t["route_short_name"] in LIGNES_PRINCIPALES}
    for nom in LIGNES_PRINCIPALES:
        geom = traces[nom]["shape"]["geometry"]
        brins = geom["coordinates"] if geom["type"] == "MultiLineString" else [geom["coordinates"]]
        couleur = tuple(int(traces[nom]["route_color"][i:i + 2], 16) for i in (0, 2, 4))
        for brin in brins:
            pts = [vue.px(*c) for c in brin]
            d.line(pts, fill=(255, 255, 255, 255), width=17, joint="curve")
        for brin in brins:
            d.line([vue.px(*c) for c in brin], fill=couleur + (255,), width=11, joint="curve")

    arrets = []
    for r in csv.DictReader(open(SIGNALEMENTS, encoding="utf-8")):
        x, y = vue.px(float(r["longitude"]), float(r["latitude"]))
        n = r["signalements"].strip()
        arrets.append({"nom": r["arret"], "lignes": r["lignes"], "x": x, "y": y, "n": int(n) if n else None})
        d.ellipse([x - 13, y - 13, x + 13, y + 13], fill=(255, 255, 255, 255), outline=(14, 31, 91, 255), width=6)
    chemin = os.path.join(ICI, ".cache", "fond_carte_bus.jpg")
    img.convert("RGB").save(chemin, quality=92)
    lignes = [(nom, traces[nom]["route_color"]) for nom in LIGNES_PRINCIPALES]
    return chemin, (largeur, hauteur), arrets, lignes


# police aux mêmes dimensions qu'Arial gras (Liberation Sans), pour mesurer les étiquettes à 12 pt
from PIL import ImageFont as _IF
MESURE = _IF.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 12)

# position des étiquettes (en pouces, par rapport au point) pour éviter les chevauchements
DECALAGES = {
    "Moulin à Vent": (0.15, -0.12), "Le Fort": (-0.2, -0.45), "Cité des Hêtres": (0.15, 0.0),
    "Rue de la Chapelle": (-1.85, -0.2), "Gabriel Péri": (-1.25, -0.15), "Place du Combat": (-1.55, 0.1),
    "Les Richardets - Centre": (-0.9, 0.15), "Ballon - Chapelle": (-0.75, -0.48), "Le Closeau": (-1.1, -0.2),
    "La Butte aux Cailles": (0.15, -0.45), "Rue du Ballon": (0.15, -0.38), "Chapelle": (0.12, -0.42),
    "Victor Hugo": (0.15, -0.12), "Les Graviers": (0.15, -0.05), "Rue des Aérostiers": (-1.85, -0.2),
    "Les Aérostiers": (0.15, -0.12), "Collège des Yvris": (0.15, -0.12),
    "Les Yvris - Noisy-le-Grand RER": (-3.1, 0.05),
}


def diapo_carte_bus(k):
    d = k.diapo(NUIT, "Services publics de proximité · les bus", "Les bus du quartier et vos signalements",
                "Plan des lignes 310, 312 et 320 qui traversent le quartier, avec leurs arrêts (données "
                "ouvertes d'Île-de-France Mobilités). Les arrêts Moulin à Vent (lignes 206, 207, 306, 310) "
                "et Les Aérostiers (ligne 212) sont en limite du quartier. Les cercles verts indiquent le "
                "nombre de signalements recueillis par le formulaire de la Ville pour chaque arrêt.")
    chemin, (lw, lh), arrets, lignes = fond_carte_bus()
    mx, my, mw = 1.04, 2.45, 12.3
    mh = mw * lh / lw
    d.shapes.add_picture(chemin, Inches(mx), Inches(my), Inches(mw), Inches(mh))
    texte(d, mx, my + mh + 0.08, mw, 0.3, "© IGN – BD ORTHO · Lignes et arrêts : Île-de-France Mobilités",
          11, "C9CCDA", gras=False, align=PP_ALIGN.RIGHT)
    vmax = max([a["n"] for a in arrets if a["n"]] or [0])
    for a in arrets:
        x, y = mx + a["x"] / lw * mw, my + a["y"] / lh * mh
        if a["n"]:
            diam = 0.38 + 0.52 * (a["n"] / vmax) ** 0.5   # surface proportionnelle au nombre
            c = rect(d, x - diam / 2, y - diam / 2, diam, diam, VERT, MSO_SHAPE.OVAL, contour=BLANC)
            tf = c.text_frame
            tf.text = str(a["n"])
            r = tf.paragraphs[0].runs[0]
            r.font.name, r.font.size, r.font.bold, r.font.color.rgb = POLICE, Pt(16), True, rgb(NUIT)
            tf.paragraphs[0].alignment = PP_ALIGN.CENTER
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE
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
    # légende des lignes
    texte(d, 13.8, 2.5, 5.2, 0.45, "LIGNES QUI TRAVERSENT LE QUARTIER", 18, VERT, espacement=120)
    for i, (nom, couleur) in enumerate(lignes):
        y = 3.2 + i * 0.75
        rect(d, 13.8, y + 0.12, 1.0, 0.22, couleur)
        texte(d, 15.0, y, 3.9, 0.5, f"Ligne {nom}", 24, BLANC)
    texte(d, 13.8, 5.55, 5.2, 0.45, "SIGNALEMENTS PAR ARRÊT", 18, VERT, espacement=120)
    if vmax:
        classement = sorted([a for a in arrets if a["n"]], key=lambda a: -a["n"])[:5]
        for i, a in enumerate(classement):
            y = 6.2 + i * 0.75
            texte(d, 13.8, y, 1.3, 0.6, str(a["n"]), 28, VERT)
            texte(d, 15.0, y + 0.05, 4.0, 0.6, a["nom"].replace(" - ", " – "), 20, BLANC)
    else:
        a_completer(d, 13.8, 6.15, 5.16, 3.5, "[Nombre de signalements par arrêt à compléter]", sombre=True)
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

    nv = k.nouvelles
    ordonner(prs, [G_QR_ACCUEIL, G_COUVERTURE, G_SOMMAIRE] + nv[0:4] + [G_PERI_MERCREDI, G_PERI_CANTINE]
             + nv[4:8] + [n_carte, G_KEOLIS] + nv[8:13] + [G_QUESTIONS, G_QR_SORTIE])
    prs.save(SORTIE)
    print("Écrit :", SORTIE, "-", len(prs.slides._sldIdLst), "diapositives")


if __name__ == "__main__":
    construire()
