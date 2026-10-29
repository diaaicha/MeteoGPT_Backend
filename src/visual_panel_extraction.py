
"""
Détection géométrique des panneaux météorologiques.

Fonctions reprises des sections 3.5.5.3 et 3.5.5.4
du traitement documentaire initial.
"""

# ============================================================
# PARAMÈTRES DE DÉTECTION — VALEURS D'ORIGINE
# ============================================================

MIN_AREA_RATIO = 0.02
MAX_AREA_RATIO = 0.20

MIN_WIDTH = 150
MIN_HEIGHT = 60

MIN_ASPECT_RATIO = 1.15
MAX_ASPECT_RATIO = 4.0

MIN_FILL_SATURATION = 0.05
IOU_DUPLICATE_THRESHOLD = 0.90


# ============================================================
# UTILITAIRES GÉOMÉTRIQUES
# ============================================================

def surface_bbox(bbox):
    x0, y0, x1, y1 = bbox
    largeur = max(0.0, x1 - x0)
    hauteur = max(0.0, y1 - y0)
    return largeur * hauteur


def aire_page(page):
    rect = page.rect
    return rect.width * rect.height


def ratio_surface_bbox(bbox, page):
    surface_page = aire_page(page)
    if surface_page <= 0:
        return 0.0
    return surface_bbox(bbox) / surface_page


def intersection_bbox(bbox_a, bbox_b):
    ax0, ay0, ax1, ay1 = bbox_a
    bx0, by0, bx1, by1 = bbox_b

    x0 = max(ax0, bx0)
    y0 = max(ay0, by0)
    x1 = min(ax1, bx1)
    y1 = min(ay1, by1)

    if x1 <= x0 or y1 <= y0:
        return None

    return (x0, y0, x1, y1)


def iou_bbox(bbox_a, bbox_b):
    intersection = intersection_bbox(bbox_a, bbox_b)

    if intersection is None:
        return 0.0

    aire_intersection = surface_bbox(intersection)
    aire_union = (
        surface_bbox(bbox_a)
        + surface_bbox(bbox_b)
        - aire_intersection
    )

    if aire_union <= 0:
        return 0.0

    return aire_intersection / aire_union


def dimensions_bbox(bbox):
    x0, y0, x1, y1 = bbox

    largeur = max(0.0, x1 - x0)
    hauteur = max(0.0, y1 - y0)

    ratio = largeur / hauteur if hauteur else 0.0

    return largeur, hauteur, ratio


def bbox_valide(bbox):
    if bbox is None or len(bbox) != 4:
        return False

    x0, y0, x1, y1 = bbox

    return x1 > x0 and y1 > y0


# ============================================================
# COULEURS
# ============================================================

def saturation_couleur(couleur):
    if couleur is None:
        return 0.0

    try:
        r, g, b = couleur
        maximum = max(r, g, b)
        minimum = min(r, g, b)

        if maximum == 0:
            return 0.0

        return (maximum - minimum) / maximum

    except Exception:
        return 0.0


# ============================================================
# DÉTECTION DES PANNEAUX
# ============================================================

def detecter_panneaux_page(page):
    """
    Détecte les rectangles vectoriels correspondant
    potentiellement à des panneaux météorologiques.

    Aucune coordonnée fixe ni localité prédéfinie.
    """

    candidats = []
    surface_page = aire_page(page)

    if surface_page <= 0:
        return candidats

    for drawing in page.get_drawings():

        rect = drawing.get("rect")

        if rect is None:
            continue

        bbox = (
            float(rect.x0),
            float(rect.y0),
            float(rect.x1),
            float(rect.y1)
        )

        if not bbox_valide(bbox):
            continue

        largeur, hauteur, ratio = dimensions_bbox(bbox)
        surface = surface_bbox(bbox)
        ratio_surface = surface / surface_page

        fill = drawing.get("fill")

        if fill is None:
            continue

        saturation = saturation_couleur(fill)

        if saturation < MIN_FILL_SATURATION:
            continue

        if not (
            MIN_AREA_RATIO <= ratio_surface <= MAX_AREA_RATIO
        ):
            continue

        if largeur < MIN_WIDTH or hauteur < MIN_HEIGHT:
            continue

        if not (
            MIN_ASPECT_RATIO <= ratio <= MAX_ASPECT_RATIO
        ):
            continue

        candidats.append({
            "bbox": bbox,
            "largeur": largeur,
            "hauteur": hauteur,
            "ratio": ratio,
            "surface": surface,
            "ratio_surface": ratio_surface,
            "fill": fill,
            "saturation": saturation
        })

    return candidats


# ============================================================
# DÉDOUBLONNAGE
# ============================================================

def dedoublonner_panneaux(candidats):
    """
    Conserve les rectangles distincts selon l'IoU.
    """

    if not candidats:
        return []

    candidats_tries = sorted(
        candidats,
        key=lambda item: item["surface"],
        reverse=True
    )

    conserves = []

    for candidat in candidats_tries:

        doublon = any(
            iou_bbox(
                candidat["bbox"],
                existant["bbox"]
            ) >= IOU_DUPLICATE_THRESHOLD
            for existant in conserves
        )

        if not doublon:
            conserves.append(candidat)

    conserves.sort(
        key=lambda item: (
            item["bbox"][1],
            item["bbox"][0]
        )
    )

    return conserves


def analyser_panneaux_page(page):
    """
    Détection suivie du dédoublonnage.
    """
    candidats = detecter_panneaux_page(page)
    return dedoublonner_panneaux(candidats)




# ============================================================
# LOT OCR 2 — RESSERREMENT ET RENDU DES PANNEAUX
# ============================================================

from pathlib import Path
import fitz


MARGE_RENDER = 0
SCALE_RENDER = 2.0
MIN_RECOUVREMENT = 0.50
MARGE_FRONTIERE = 2.0


def longueur_recouvrement(a0, a1, b0, b1):
    """Longueur de recouvrement entre deux intervalles."""
    return max(0.0, min(a1, b1) - max(a0, b0))


def recouvrement_horizontal(bbox_a, bbox_b):
    """Recouvrement horizontal rapporté à la largeur de A."""
    ax0, ay0, ax1, ay1 = bbox_a
    bx0, by0, bx1, by1 = bbox_b

    largeur_a = max(0.0, ax1 - ax0)

    if largeur_a <= 0:
        return 0.0

    recouvrement = longueur_recouvrement(
        ax0, ax1, bx0, bx1
    )

    return recouvrement / largeur_a


def recouvrement_vertical(bbox_a, bbox_b):
    """Recouvrement vertical rapporté à la hauteur de A."""
    ax0, ay0, ax1, ay1 = bbox_a
    bx0, by0, bx1, by1 = bbox_b

    hauteur_a = max(0.0, ay1 - ay0)

    if hauteur_a <= 0:
        return 0.0

    recouvrement = longueur_recouvrement(
        ay0, ay1, by0, by1
    )

    return recouvrement / hauteur_a


def resserrer_bbox(bbox, autres_bboxes):
    """
    Resserre un panneau selon les limites naturelles
    des panneaux situés en dessous ou à droite.

    Le bbox original n'est pas modifié.
    """
    x0, y0, x1, y1 = bbox

    bbox_final = (
        float(x0),
        float(y0),
        float(x1),
        float(y1),
    )

    candidats_sous = []
    candidats_droite = []

    for autre in autres_bboxes:
        ax0, ay0, ax1, ay1 = autre

        if autre == bbox:
            continue

        # Voisin situé en dessous
        rec_h = recouvrement_horizontal(bbox, autre)

        if rec_h >= MIN_RECOUVREMENT:
            if ay0 > y0 and ay0 < y1:
                candidats_sous.append({
                    "bbox": autre,
                    "distance": ay0 - y0,
                    "recouvrement": rec_h,
                })

        # Voisin situé à droite
        rec_v = recouvrement_vertical(bbox, autre)

        if rec_v >= MIN_RECOUVREMENT:
            if ax0 > x0 and ax0 < x1:
                candidats_droite.append({
                    "bbox": autre,
                    "distance": ax0 - x0,
                    "recouvrement": rec_v,
                })

    # Réduction de la limite inférieure
    if candidats_sous:
        candidat = min(
            candidats_sous,
            key=lambda x: x["distance"],
        )

        y1_nouveau = (
            candidat["bbox"][1] - MARGE_FRONTIERE
        )

        if y1_nouveau > y0:
            bbox_final = (
                bbox_final[0],
                bbox_final[1],
                bbox_final[2],
                y1_nouveau,
            )

    # Réduction de la limite droite
    if candidats_droite:
        candidat = min(
            candidats_droite,
            key=lambda x: x["distance"],
        )

        x1_nouveau = (
            candidat["bbox"][0] - MARGE_FRONTIERE
        )

        if x1_nouveau > bbox_final[0]:
            bbox_final = (
                bbox_final[0],
                bbox_final[1],
                x1_nouveau,
                bbox_final[3],
            )

    return bbox_final


def rendre_panneau(page, bbox, chemin_sortie):
    """
    Génère l'image PNG du panneau à partir du bbox
    fourni, sans ajouter de marge.
    """
    x0, y0, x1, y1 = bbox

    rectangle = fitz.Rect(
        x0 - MARGE_RENDER,
        y0 - MARGE_RENDER,
        x1 + MARGE_RENDER,
        y1 + MARGE_RENDER,
    )

    rectangle = rectangle & page.rect

    matrice = fitz.Matrix(
        SCALE_RENDER,
        SCALE_RENDER,
    )

    pixmap = page.get_pixmap(
        matrix=matrice,
        clip=rectangle,
        alpha=False,
    )

    chemin_sortie = Path(chemin_sortie)

    chemin_sortie.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    pixmap.save(str(chemin_sortie))

    return chemin_sortie




# ============================================================
# LOT OCR 3 — EXTRACTION OCR SPATIALE
# ============================================================

import pytesseract
from PIL import Image

OCR_LANG = "fra"
OCR_CONFIG = "--psm 6"


def extraire_ocr_spatial(chemin_image):
    """
    Effectue l'OCR d'un panneau et conserve :
    - texte OCR brut ;
    - mots et leurs coordonnées en pixels ;
    - lignes reconstruites spatialement.
    """

    with Image.open(chemin_image) as image:
        donnees = pytesseract.image_to_data(
            image,
            lang=OCR_LANG,
            config=OCR_CONFIG,
            output_type=pytesseract.Output.DICT,
        )

    mots = []

    for i in range(len(donnees["text"])):
        texte = str(donnees["text"][i]).strip()

        if not texte:
            continue

        try:
            confiance = float(donnees["conf"][i])
        except (TypeError, ValueError):
            confiance = -1.0

        x = int(donnees["left"][i])
        y = int(donnees["top"][i])
        largeur = int(donnees["width"][i])
        hauteur = int(donnees["height"][i])

        mots.append({
            "text": texte,
            "confidence": confiance,
            "x": x,
            "y": y,
            "width": largeur,
            "height": hauteur,
            "x2": x + largeur,
            "y2": y + hauteur,
        })

    # --------------------------------------------------------
    # RECONSTRUCTION SPATIALE DES LIGNES
    # --------------------------------------------------------

    mots_tries = sorted(
        mots,
        key=lambda mot: (mot["y"], mot["x"]),
    )

    lignes = []

    for mot in mots_tries:
        centre_y = mot["y"] + mot["height"] / 2

        ligne_trouvee = None

        for ligne in lignes:
            tolerance = max(
                mot["height"],
                ligne["hauteur_moyenne"],
            ) * 0.5

            if abs(centre_y - ligne["centre_y"]) <= tolerance:
                ligne_trouvee = ligne
                break

        if ligne_trouvee is None:
            lignes.append({
                "mots": [mot],
                "centre_y": centre_y,
                "hauteur_moyenne": mot["height"],
            })

        else:
            ligne_trouvee["mots"].append(mot)

            ligne_trouvee["centre_y"] = (
                sum(
                    m["y"] + m["height"] / 2
                    for m in ligne_trouvee["mots"]
                )
                / len(ligne_trouvee["mots"])
            )

            ligne_trouvee["hauteur_moyenne"] = (
                sum(
                    m["height"]
                    for m in ligne_trouvee["mots"]
                )
                / len(ligne_trouvee["mots"])
            )

    # --------------------------------------------------------
    # NORMALISATION DES LIGNES
    # --------------------------------------------------------

    lignes_finales = []

    for ligne in lignes:
        mots_ligne = sorted(
            ligne["mots"],
            key=lambda mot: mot["x"],
        )

        texte_ligne = " ".join(
            mot["text"] for mot in mots_ligne
        )

        if not texte_ligne.strip():
            continue

        lignes_finales.append({
            "text": texte_ligne,
            "mots": mots_ligne,
            "y": min(mot["y"] for mot in mots_ligne),
            "y2": max(mot["y2"] for mot in mots_ligne),
            "x": min(mot["x"] for mot in mots_ligne),
            "x2": max(mot["x2"] for mot in mots_ligne),
        })

    texte_brut = "\n".join(
        ligne["text"] for ligne in lignes_finales
    )

    return {
        "texte": texte_brut,
        "mots": mots,
        "lignes": lignes_finales,
    }



# ============================================================
# LOT OCR 4 — RECONNAISSANCE DES LOCALITÉS
# ============================================================

import re
import unicodedata
from rapidfuzz import fuzz, process


GAZETTEER_LOCALITES = [
    "Dakar", "Thiès", "Diourbel", "Mbour",
    "Saint-Louis", "Podor", "Louga", "Linguère",
    "Fatick", "Kaolack", "Kaffrine", "Matam",
    "Tambacounda", "Bakel", "Kédougou",
    "Kolda", "Sédhiou", "Ziguinchor",
    "Cap-Skiring",
]

SEUIL_LOCALITE = 50
SEUIL_LOCALITE_FORTE = 75


def normaliser_localite(texte):
    """Normalise un texte OCR avant comparaison."""
    if texte is None:
        return ""

    texte = str(texte).strip()
    if not texte:
        return ""

    texte = unicodedata.normalize("NFD", texte)

    texte = "".join(
        caractere
        for caractere in texte
        if unicodedata.category(caractere) != "Mn"
    )

    texte = texte.upper()
    texte = texte.replace("–", "-").replace("—", "-")
    texte = texte.replace("_", " ")
    texte = re.sub(r"[^A-Z0-9\- ]+", " ", texte)
    texte = re.sub(r"\s+", " ", texte).strip()

    return texte


gazetteer_normalise = {
    normaliser_localite(localite): localite
    for localite in GAZETTEER_LOCALITES
}

gazetteer_cles = list(gazetteer_normalise.keys())


def reconnaitre_localite(texte):
    """
    Recherche une localité dans une ligne OCR.

    Renvoie son nom canonique, le texte original
    et le score de reconnaissance, ou None.
    """
    if not texte:
        return None

    texte_original = str(texte).strip()
    if not texte_original:
        return None

    texte_normalise = normaliser_localite(
        texte_original
    )

    if not texte_normalise:
        return None

    resultat = process.extractOne(
        texte_normalise,
        gazetteer_cles,
        scorer=fuzz.ratio,
    )

    if resultat is None:
        return None

    meilleure_cle, score, _ = resultat
    score = float(score)
    localite = gazetteer_normalise[meilleure_cle]

    correspondance = {
        "localite": localite,
        "texte_ocr": texte_original,
        "score": round(score, 2),
    }

    # Correspondance forte
    if score >= SEUIL_LOCALITE_FORTE:
        return correspondance

    # Correspondance moyenne :
    # exige une ressemblance lexicale réelle.
    if score >= SEUIL_LOCALITE:
        tokens_ocr = set(texte_normalise.split())
        tokens_localite = set(meilleure_cle.split())

        if tokens_ocr.intersection(tokens_localite):
            return correspondance

        morceaux_valides = [
            morceau
            for morceau in tokens_localite
            if len(morceau) >= 5
            and morceau in texte_normalise
        ]

        if morceaux_valides:
            return correspondance

    return None


def reconnaitre_localites_panneau(panneau):
    """
    Reconnaît les localités dans les lignes OCR
    d'un panneau, en conservant leurs coordonnées.

    Attend panneau["ocr_lines"].
    """
    localites = []

    for ligne in panneau.get("ocr_lines", []):
        texte = str(ligne.get("text", "")).strip()

        if not texte:
            continue

        resultat = reconnaitre_localite(texte)

        if resultat is None:
            continue

        # Compatibilité avec les coordonnées du lot OCR 3.
        x = ligne.get("x")
        y = ligne.get("y")
        x2 = ligne.get("x2")
        y2 = ligne.get("y2")

        bbox = ligne.get("bbox")
        if (
            bbox is None
            and all(v is not None for v in (x, y, x2, y2))
        ):
            bbox = (x, y, x2, y2)

        largeur = ligne.get("width")
        hauteur = ligne.get("height")

        if largeur is None and x is not None and x2 is not None:
            largeur = x2 - x

        if hauteur is None and y is not None and y2 is not None:
            hauteur = y2 - y

        localites.append({
            "localite": resultat["localite"],
            "texte_ocr": resultat["texte_ocr"],
            "score": resultat["score"],
            "bbox": bbox,
            "x": x,
            "y": y,
            "width": largeur,
            "height": hauteur,
        })

    # Dédoublonnage par localité et position verticale.
    localites_uniques = []
    deja_vues = set()

    for localite in localites:
        try:
            y_arrondi = round(float(localite.get("y")), 1)
        except (TypeError, ValueError):
            y_arrondi = 0.0

        cle = (localite["localite"], y_arrondi)

        if cle in deja_vues:
            continue

        deja_vues.add(cle)
        localites_uniques.append(localite)

    # Tri spatial des ancres.
    localites_uniques.sort(
        key=lambda element: (
            float(element.get("y") or 0),
            float(element.get("x") or 0),
        )
    )

    return localites_uniques



# ============================================================
# LOT OCR 5 — ATTRIBUTION LOCALITÉ ↔ PANNEAU
# ============================================================

import math


def coordonnee_valide(valeur):
    """
    Vérifie qu'une coordonnée OCR est numérique,
    finie et positive ou nulle.
    """
    try:
        nombre = float(valeur)
        return math.isfinite(nombre) and nombre >= 0
    except (TypeError, ValueError):
        return False


def attribuer_localites_panneau(panneau):
    """
    Associe à un panneau les localités détectées par OCR.

    Préserve :
    - les ancres OCR originales ;
    - les coordonnées spatiales ;
    - une ancre par localité canonique ;
    - les panneaux contenant plusieurs localités.

    Ne suppose ni ordre fixe des villes,
    ni coordonnées prédéfinies.
    """

    localites = panneau.get("localites_detectees", [])

    # --------------------------------------------------------
    # 1. Validation des ancres spatiales
    # --------------------------------------------------------

    ancres_valides = []

    for ancre in localites:

        x = ancre.get("x")
        y = ancre.get("y")

        if not coordonnee_valide(x):
            continue

        if not coordonnee_valide(y):
            continue

        ancres_valides.append(ancre)

    # --------------------------------------------------------
    # 2. Suppression des doublons de localité
    # --------------------------------------------------------

    localites_panneau = []
    localites_deja_vues = set()

    for ancre in ancres_valides:

        nom = str(
            ancre.get("localite") or ""
        ).strip()

        if not nom:
            continue

        if nom in localites_deja_vues:
            continue

        localites_deja_vues.add(nom)

        # Copie légère pour préserver l'ancre initiale.
        ancre_conservee = dict(ancre)
        ancre_conservee["localite"] = nom

        localites_panneau.append(ancre_conservee)

    # --------------------------------------------------------
    # 3. Tri spatial
    # --------------------------------------------------------

    localites_panneau.sort(
        key=lambda ancre: (
            float(ancre.get("y")),
            float(ancre.get("x"))
        )
    )

    # --------------------------------------------------------
    # 4. Stockage du résultat
    # --------------------------------------------------------

    panneau["localites_panneau"] = localites_panneau

    return panneau



# ============================================================
# LOT OCR 6 — ANALYSE SPATIALE DES PANNEAUX
# ============================================================

def valeur_float(valeur, valeur_defaut=0.0):
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return valeur_defaut


def bbox_ligne_ocr(ligne):
    """Reconstruit les coordonnées d'une ligne OCR."""

    if all(cle in ligne for cle in ("x", "y", "x2", "y2")):
        return (
            valeur_float(ligne["x"]),
            valeur_float(ligne["y"]),
            valeur_float(ligne["x2"]),
            valeur_float(ligne["y2"]),
        )

    if all(
        cle in ligne
        for cle in ("x", "y", "width", "height")
    ):
        x = valeur_float(ligne["x"])
        y = valeur_float(ligne["y"])
        largeur = valeur_float(ligne["width"])
        hauteur = valeur_float(ligne["height"])

        return (x, y, x + largeur, y + hauteur)

    return None


def determiner_dimensions_ocr(panneau):
    """
    Détermine l'étendue du contenu OCR.

    Utilise les mots OCR, ou les lignes si les mots
    ne sont pas disponibles.
    """
    mots = panneau.get("ocr_words", [])

    x_min = None
    y_min = None
    x_max = 0.0
    y_max = 0.0

    if mots:
        bboxes = []

        for mot in mots:
            x = valeur_float(mot.get("x"))
            y = valeur_float(mot.get("y"))

            x2 = valeur_float(
                mot.get("x2"),
                x + valeur_float(mot.get("width")),
            )
            y2 = valeur_float(
                mot.get("y2"),
                y + valeur_float(mot.get("height")),
            )

            bboxes.append((x, y, x2, y2))

    else:
        bboxes = [
            bbox_ligne_ocr(ligne)
            for ligne in panneau.get("ocr_lines", [])
        ]
        bboxes = [
            bbox for bbox in bboxes
            if bbox is not None
        ]

    for x0, y0, x1, y1 in bboxes:
        x_min = x0 if x_min is None else min(x_min, x0)
        y_min = y0 if y_min is None else min(y_min, y0)
        x_max = max(x_max, x1)
        y_max = max(y_max, y1)

    if x_min is None:
        x_min = 0.0

    if y_min is None:
        y_min = 0.0

    return {
        "x_min": x_min,
        "y_min": y_min,
        "x_max": x_max,
        "y_max": y_max,
        "largeur": max(x_max - x_min, 1.0),
        "hauteur": max(y_max - y_min, 1.0),
    }


def construire_lignes_spatiales(panneau, dimensions_ocr):
    """Ajoute les positions absolues et relatives aux lignes."""

    lignes_spatiales = []

    x_min = dimensions_ocr["x_min"]
    y_min = dimensions_ocr["y_min"]
    largeur = dimensions_ocr["largeur"]
    hauteur = dimensions_ocr["hauteur"]

    for index, ligne in enumerate(
        panneau.get("ocr_lines", [])
    ):
        texte = str(ligne.get("text", "")).strip()

        if not texte:
            continue

        bbox = bbox_ligne_ocr(ligne)

        if bbox is None:
            continue

        x0, y0, x1, y1 = bbox

        cx = (x0 + x1) / 2
        cy = (y0 + y1) / 2

        x_rel = max(
            0.0,
            min(1.0, (cx - x_min) / largeur),
        )
        y_rel = max(
            0.0,
            min(1.0, (cy - y_min) / hauteur),
        )

        lignes_spatiales.append({
            "index": index,
            "text": texte,
            "bbox": bbox,
            "x0": x0,
            "y0": y0,
            "x1": x1,
            "y1": y1,
            "cx": cx,
            "cy": cy,
            "width": max(0.0, x1 - x0),
            "height": max(0.0, y1 - y0),
            "x_rel": x_rel,
            "y_rel": y_rel,
        })

    return lignes_spatiales


def trouver_ancre_localite(ligne, panneau):
    """
    Associe une ligne OCR à une ancre reconnue
    précédemment, par correspondance textuelle normalisée.
    """
    texte_ligne = normaliser_localite(
        ligne.get("text", "")
    )

    for ancre in panneau.get("localites_panneau", []):
        texte_ancre = normaliser_localite(
            ancre.get("texte_ocr", "")
        )

        if texte_ligne == texte_ancre:
            return ancre

    return None


def classifier_position_x(x_rel):
    if x_rel < 0.33:
        return "gauche"

    if x_rel > 0.67:
        return "droite"

    return "centre"


def classifier_position_y(y_rel):
    if y_rel < 0.25:
        return "haut"

    if y_rel > 0.75:
        return "bas"

    return "milieu"


def construire_blocs_spatiaux(lignes):
    """Regroupe les lignes selon leurs zones spatiales."""

    blocs = {
        "haut": [],
        "milieu": [],
        "bas": [],
        "gauche": [],
        "centre": [],
        "droite": [],
    }

    for ligne in lignes:
        zone_y = classifier_position_y(ligne["y_rel"])
        zone_x = classifier_position_x(ligne["x_rel"])

        ligne["zone_y"] = zone_y
        ligne["zone_x"] = zone_x

        blocs[zone_y].append(ligne)
        blocs[zone_x].append(ligne)

    return blocs


def analyser_panneau_spatial(panneau):
    """
    Réalise l'analyse spatiale d'un panneau déjà
    traité par OCR et attribution des localités.
    """

    dimensions = determiner_dimensions_ocr(panneau)

    lignes = construire_lignes_spatiales(
        panneau,
        dimensions,
    )

    for ligne in lignes:
        ancre = trouver_ancre_localite(ligne, panneau)

        if ancre is not None:
            ligne["est_ancre_localite"] = True
            ligne["localite"] = ancre["localite"]
            ligne["score_localite"] = ancre["score"]
        else:
            ligne["est_ancre_localite"] = False
            ligne["localite"] = None
            ligne["score_localite"] = None

    blocs = construire_blocs_spatiaux(lignes)

    ancres = [
        ligne
        for ligne in lignes
        if ligne["est_ancre_localite"]
    ]

    localites_detectees = []

    for ligne in ancres:
        nom = ligne["localite"]

        if nom and nom not in localites_detectees:
            localites_detectees.append(nom)

    return {
        "dimensions_ocr": dimensions,
        "lignes": lignes,
        "blocs": blocs,
        "ancres_localites": ancres,
        "localites_detectees": localites_detectees,
        "nombre_localites": len(localites_detectees),
        "multi_localite": len(localites_detectees) > 1,
        "nombre_lignes_ocr": len(lignes),
    }



# ============================================================
# LOT OCR 7A — OCR DE RÉCUPÉRATION PLEINE PAGE
# ============================================================

from copy import deepcopy
import re
import fitz
import pytesseract
from PIL import Image


SCALE_PAGE_OCR = 2.0
OCR_PAGE_LANG = "fra"
OCR_PAGE_CONFIG = "--psm 11"
TOLERANCE_LIGNE = 18


def normaliser_texte_fusion(texte):
    if texte is None:
        return ""

    return re.sub(r"\s+", " ", str(texte)).strip()


def reconstruire_lignes_fusion(
    mots,
    tolerance_y=TOLERANCE_LIGNE,
):
    """
    Reconstruit des lignes à partir de mots OCR
    exprimés dans un même repère spatial.
    """

    if not mots:
        return []

    mots_tries = sorted(
        mots,
        key=lambda mot: (
            float(mot.get("y", 0)),
            float(mot.get("x", 0)),
        ),
    )

    groupes = []

    for mot in mots_tries:
        y = float(mot.get("y", 0))
        y2 = float(mot.get("y2", y))
        centre_y = (y + y2) / 2

        groupe_trouve = None

        for groupe in groupes:
            if (
                abs(centre_y - groupe["centre_y"])
                <= tolerance_y
            ):
                groupe_trouve = groupe
                break

        if groupe_trouve is None:
            groupes.append({
                "centre_y": centre_y,
                "mots": [mot],
            })
        else:
            groupe_trouve["mots"].append(mot)

    lignes = []

    for groupe in groupes:
        mots_ligne = sorted(
            groupe["mots"],
            key=lambda mot: float(mot.get("x", 0)),
        )

        textes = [
            str(mot.get("text", "")).strip()
            for mot in mots_ligne
            if str(mot.get("text", "")).strip()
        ]

        if not textes:
            continue

        lignes.append({
            "text": " ".join(textes),
            "mots": deepcopy(mots_ligne),
            "x": min(float(m["x"]) for m in mots_ligne),
            "x2": max(float(m["x2"]) for m in mots_ligne),
            "y": min(float(m["y"]) for m in mots_ligne),
            "y2": max(float(m["y2"]) for m in mots_ligne),
        })

    lignes.sort(key=lambda ligne: (ligne["y"], ligne["x"]))

    return lignes


def ocr_page_complete_fusion(page):
    """
    OCR de récupération sur une page PDF entière.

    Ne détecte aucune localité : la source de vérité
    reste l'attribution réalisée au lot OCR 5.
    """

    pix = page.get_pixmap(
        matrix=fitz.Matrix(
            SCALE_PAGE_OCR,
            SCALE_PAGE_OCR,
        ),
        alpha=False,
        colorspace=fitz.csRGB,
    )

    image = Image.frombytes(
        "RGB",
        (pix.width, pix.height),
        pix.samples,
    )

    try:
        donnees = pytesseract.image_to_data(
            image,
            lang=OCR_PAGE_LANG,
            config=OCR_PAGE_CONFIG,
            output_type=pytesseract.Output.DICT,
        )
    finally:
        image.close()

    mots = []

    for i in range(len(donnees["text"])):
        texte = str(donnees["text"][i]).strip()

        if not texte:
            continue

        try:
            confiance = float(donnees["conf"][i])
        except (TypeError, ValueError):
            confiance = -1.0

        x = int(donnees["left"][i])
        y = int(donnees["top"][i])
        largeur = int(donnees["width"][i])
        hauteur = int(donnees["height"][i])

        mots.append({
            "text": texte,
            "confidence": confiance,
            "x": x,
            "y": y,
            "x2": x + largeur,
            "y2": y + hauteur,
            "width": largeur,
            "height": hauteur,
            "centre_x": x + largeur / 2,
            "centre_y": y + hauteur / 2,
        })

    return {
        "image_width": pix.width,
        "image_height": pix.height,
        "scale": SCALE_PAGE_OCR,
        "words": mots,
        "text": " ".join(
            mot["text"] for mot in mots
        ),
    }


def extraire_mots_panneau_fusion(page_data, panneau):
    """
    Sélectionne les mots OCR pleine page situés dans
    le rectangle du panneau.

    Les coordonnées retournées sont ramenées dans
    le repère de l'image du panneau.
    """

    if page_data is None:
        return []

    bbox = (
        panneau.get("bbox_rendu")
        or panneau.get("bbox")
    )

    if bbox is None:
        return []

    x0, y0, x1, y1 = map(float, bbox)

    scale = float(
        page_data.get("scale", SCALE_PAGE_OCR)
    )

    origine_x = x0 * scale
    origine_y = y0 * scale

    limite_x = x1 * scale
    limite_y = y1 * scale

    mots = []

    for mot in page_data.get("words", []):
        centre_x = float(
            mot.get(
                "centre_x",
                (mot["x"] + mot["x2"]) / 2,
            )
        )
        centre_y = float(
            mot.get(
                "centre_y",
                (mot["y"] + mot["y2"]) / 2,
            )
        )

        if not (
            origine_x <= centre_x <= limite_x
            and origine_y <= centre_y <= limite_y
        ):
            continue

        copie = deepcopy(mot)

        # Conservation des coordonnées pleine page.
        copie["page_bbox_px"] = (
            mot["x"],
            mot["y"],
            mot["x2"],
            mot["y2"],
        )

        # Projection dans les coordonnées du panneau.
        copie["x"] = mot["x"] - origine_x
        copie["y"] = mot["y"] - origine_y
        copie["x2"] = mot["x2"] - origine_x
        copie["y2"] = mot["y2"] - origine_y

        copie["centre_x"] = centre_x - origine_x
        copie["centre_y"] = centre_y - origine_y

        mots.append(copie)

    return mots



# ============================================================
# LOT OCR 7B — FUSION ET ASSOCIATION AUX LOCALITÉS
# ============================================================

from copy import deepcopy


def associer_lignes_aux_localites(lignes, localites):
    """
    Associe les informations OCR de récupération
    aux localités déjà reconnues.

    Pour un panneau multi-localités, la répartition
    se fait au niveau des mots afin de ne pas mélanger
    deux colonnes reconnues sur une même ligne.
    """

    if not localites:
        return []

    def position_ancre(ancre):
        bbox = ancre.get("bbox")
        x2 = ancre.get("x2")
        y2 = ancre.get("y2")

        if bbox is not None and len(bbox) == 4:
            if x2 is None:
                x2 = bbox[2]
            if y2 is None:
                y2 = bbox[3]

        return {
            "x": ancre.get("x"),
            "y": ancre.get("y"),
            "x2": x2,
            "y2": y2,
        }

    blocs = [
        {
            "localite": ancre.get("localite"),
            "position_localite": position_ancre(ancre),
            "lignes": [],
            "texte": "",
        }
        for ancre in localites
    ]

    # Cas mono-localité : comportement original conservé.
    if len(localites) == 1:
        blocs[0]["lignes"] = deepcopy(lignes)
        blocs[0]["texte"] = "\n".join(
            ligne["text"]
            for ligne in lignes
        ).strip()

        return blocs

    # Cas multi-localités : traiter chaque mot
    # séparément, même si l'OCR les a regroupés
    # dans une seule ligne.
    mots_par_localite = [
        [] for _ in localites
    ]

    for ligne in lignes:
        elements = ligne.get("mots") or [ligne]

        for element in elements:
            texte = str(
                element.get("text", "")
            ).strip()

            if not texte:
                continue

            cx = (
                float(element["x"])
                + float(element["x2"])
            ) / 2

            cy = (
                float(element["y"])
                + float(element["y2"])
            ) / 2

            meilleur_index = None
            meilleure_distance = None

            for index, ancre in enumerate(localites):
                lx = ancre.get("x")
                ly = ancre.get("y")

                if not (
                    coordonnee_valide(lx)
                    and coordonnee_valide(ly)
                ):
                    continue

                distance_y = abs(cy - float(ly))
                distance_x = abs(cx - float(lx))

                # Pondération spatiale du code initial.
                distance = distance_y + 0.35 * distance_x

                if (
                    meilleure_distance is None
                    or distance < meilleure_distance
                ):
                    meilleure_distance = distance
                    meilleur_index = index

            if meilleur_index is not None:
                mots_par_localite[meilleur_index].append(
                    deepcopy(element)
                )

    # Reconstruction indépendante par localité.
    for index, bloc in enumerate(blocs):
        lignes_locales = reconstruire_lignes_fusion(
            mots_par_localite[index]
        )

        bloc["lignes"] = lignes_locales
        bloc["texte"] = "\n".join(
            ligne["text"]
            for ligne in lignes_locales
        ).strip()

    return blocs


def fusionner_panneau_visuel(panneau, page_data=None):
    """
    Fusionne :
    - l'OCR original du panneau ;
    - l'OCR complémentaire de la page ;
    - les localités déjà attribuées ;
    - l'analyse spatiale existante.

    Aucune nouvelle localité ni valeur météo
    n'est déduite dans cette fonction.
    """

    fichier = str(
        panneau.get("fichier")
        or panneau.get("source_file")
        or ""
    ).strip()

    # OCR de récupération limité au panneau.
    mots_recuperation = extraire_mots_panneau_fusion(
        page_data,
        panneau,
    )

    lignes_recuperation = reconstruire_lignes_fusion(
        mots_recuperation
    )

    texte_recuperation = "\n".join(
        ligne["text"]
        for ligne in lignes_recuperation
    ).strip()

    ocr_original = str(
        panneau.get("ocr_text") or ""
    ).strip()

    localites = deepcopy(
        panneau.get("localites_panneau", [])
    )

    blocs_localites = associer_lignes_aux_localites(
        lignes_recuperation,
        localites,
    )

    # Fusion additive, sans suppression d'information.
    textes = []

    if ocr_original:
        textes.append(ocr_original)

    if texte_recuperation:
        textes.append(texte_recuperation)

    texte_fusionne = "\n".join(textes).strip()

    return {
        "fichier": fichier,
        "page": panneau.get("page"),
        "panel_id": panneau.get("panel_id"),
        "bbox": deepcopy(panneau.get("bbox")),
        "bbox_rendu": deepcopy(
            panneau.get("bbox_rendu")
        ),
        "chemin_image": panneau.get("chemin_image"),

        "ocr_original": {
            "texte": ocr_original,
            "mots": deepcopy(
                panneau.get("ocr_words", [])
            ),
            "lignes": deepcopy(
                panneau.get("ocr_lines", [])
            ),
        },

        "ocr_recuperation": {
            "texte": texte_recuperation,
            "mots": mots_recuperation,
            "lignes": lignes_recuperation,
        },

        "localites": localites,
        "blocs_localites": blocs_localites,

        "analyse_spatiale": deepcopy(
            panneau.get("analyse_spatiale", {})
        ),

        "texte_fusionne": texte_fusionne,
        "nombre_localites": len(localites),
        "multi_localite": len(localites) > 1,
    }


# ============================================================
# LOT OCR 8A — EXTRACTION DES CHAMPS MÉTÉOROLOGIQUES
# ============================================================

import re
import unicodedata


DIRECTIONS_VENT = [
    "Ouest à Sud-Ouest",
    "Sud-Ouest à Ouest",
    "Nord-Ouest à Ouest",
    "Nord-Est à Est",
    "Sud-Est à Est",
    "Nord-Ouest",
    "Sud-Ouest",
    "Nord-Est",
    "Sud-Est",
    "Nord",
    "Sud",
    "Est",
    "Ouest",
    "Variable",
]


def normaliser_texte_extraction(texte):
    """
    Normalisation pour les expressions régulières.
    Le texte original reste conservé séparément.
    """
    if texte is None:
        return ""

    texte = unicodedata.normalize(
        "NFKC", str(texte)
    )

    texte = "".join(
        caractere
        for caractere in unicodedata.normalize("NFD", texte)
        if unicodedata.category(caractere) != "Mn"
    )

    remplacements = {
        "IC": "°C",
        "lC": "°C",
        "lc": "°C",
        "oC": "°C",
        "OC": "°C",
        "\u00ad": "-",
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
    }

    for ancien, nouveau in remplacements.items():
        texte = texte.replace(ancien, nouveau)

    texte = re.sub(r"[ \t]+", " ", texte)
    texte = re.sub(r"\n+", "\n", texte)

    return texte.strip()


def normaliser_texte_ligne(texte):
    return re.sub(
        r"\s+",
        " ",
        normaliser_texte_extraction(texte)
    ).strip()


def _sources_meteo(texte_pdf, texte_ocr):
    """
    Parcourt les sources dans l'ordre de priorité :
    texte PDF natif, puis OCR.
    """
    for source_type, texte in (
        ("pdf_natif", texte_pdf),
        ("ocr", texte_ocr),
    ):
        if texte:
            yield source_type, normaliser_texte_ligne(texte)


def _extraire_motif(
    texte_pdf,
    texte_ocr,
    champ,
    motifs,
):
    """Extraction commune avec traçabilité."""

    for source_type, texte in _sources_meteo(
        texte_pdf, texte_ocr
    ):
        for motif, valeur in motifs:
            correspondance = re.search(
                motif,
                texte,
                flags=re.IGNORECASE,
            )

            if correspondance:
                valeur_finale = (
                    valeur(correspondance)
                    if callable(valeur)
                    else valeur
                )

                return {
                    champ: valeur_finale,
                    "source": correspondance.group(0),
                    "source_type": source_type,
                }

    return {
        champ: None,
        "source": None,
        "source_type": None,
    }


# ============================================================
# TEMPÉRATURE
# ============================================================

def extraire_temperature(texte_pdf, texte_ocr):
    """
    Reconnaît notamment :
    28°C/33°C, 28 °C / 33 °C, 28IC/33IC.
    """

    motifs = (
        re.compile(
            r"(\d{1,2})\s*[°ºoOIl]?\s*C"
            r"\s*[/\-]\s*"
            r"(\d{1,2})\s*[°ºoOIl]?\s*C",
            re.IGNORECASE,
        ),
        re.compile(
            r"(\d{1,2})\s*[°ºoOIl]?\s*C"
            r"\s*[/\-]\s*"
            r"(\d{1,2})\s*[°ºoOIl]?",
            re.IGNORECASE,
        ),
    )

    for source_type, texte in _sources_meteo(
        texte_pdf, texte_ocr
    ):
        for motif in motifs:
            correspondance = motif.search(texte)

            if not correspondance:
                continue

            t_min, t_max = sorted((
                int(correspondance.group(1)),
                int(correspondance.group(2)),
            ))

            return {
                "temperature_min": t_min,
                "temperature_max": t_max,
                "unite_temperature": "°C",
                "source": correspondance.group(0),
                "source_type": source_type,
            }

    return {
        "temperature_min": None,
        "temperature_max": None,
        "unite_temperature": "°C",
        "source": None,
        "source_type": None,
    }


# ============================================================
# TYPE DE TEMPS
# ============================================================

def extraire_temps(texte_pdf, texte_ocr):
    return _extraire_motif(
        texte_pdf,
        texte_ocr,
        "temps",
        [
            (r"\bTemps\s+Chaud\b", "Temps Chaud"),
        ],
    )


# ============================================================
# DIRECTION DU VENT
# ============================================================

def normaliser_direction(direction):
    direction_n = normaliser_texte_ligne(
        direction
    ).lower()

    direction_n = re.sub(
        r"\s*-\s*", "-", direction_n
    )

    for canonique in DIRECTIONS_VENT:
        if (
            normaliser_texte_ligne(canonique).lower()
            == direction_n
        ):
            return canonique

    return direction.strip()


def extraire_direction_vent(texte_pdf, texte_ocr):
    cardinal = r"(?:Nord|Sud|Est|Ouest)"

    direction = (
        rf"(?:{cardinal}"
        rf"(?:\s*-\s*{cardinal})?"
        rf"(?:\s+(?:a|à)\s+{cardinal}"
        rf"(?:\s*-\s*{cardinal})?)?"
        rf"|Variable)"
    )

    motif = rf"\bVent\s*:\s*({direction})"

    return _extraire_motif(
        texte_pdf,
        texte_ocr,
        "direction_vent",
        [
            (
                motif,
                lambda m: normaliser_direction(
                    m.group(1)
                ),
            )
        ],
    )


# ============================================================
# INTENSITÉ DU VENT
# ============================================================

def extraire_intensite_vent(texte_pdf, texte_ocr):
    motifs = [
        (
            r"\bFaible\s+(?:a|à)\s+modere\b",
            "Faible à modéré",
        ),
        (r"\bTres\s+fort\b", "Très fort"),
        (r"\bModere\b", "Modéré"),
        (r"\bFaible\b", "Faible"),
        (r"\bFort\b", "Fort"),
        (
            r"\bFaible\s+(?:a|à)\b",
            "Faible à",
        ),
    ]

    return _extraire_motif(
        texte_pdf,
        texte_ocr,
        "intensite_vent",
        motifs,
    )


# ============================================================
# PHÉNOMÈNES MÉTÉOROLOGIQUES
# ============================================================

def extraire_phenomene(texte_pdf, texte_ocr):
    motifs = [
        (
            r"\bNuageux\s+avec\s+risques\s+de\s+pluie\b",
            "Nuageux avec risques de pluie",
        ),
        (
            r"\bNuageux\s+avec\s+faibles\s+chances\s+de\s+pluie\b",
            "Nuageux avec faibles chances de pluie",
        ),
        (
            r"\bNuageux\s+la\s+nuit\s+avec\s+faibles\s+chances\s+de\s+pluie\b",
            "Nuageux la nuit avec faibles chances de pluie",
        ),
        (
            r"\bRisques\s+de\s+pluies\s+faibles\b",
            "Risques de pluies faibles",
        ),
        (
            r"\bRisques\s+de\s+pluie\s+faibles\b",
            "Risques de pluie faibles",
        ),
        (
            r"\bRisques\s+de\s+pluies\b",
            "Risques de pluies",
        ),
        (
            r"\bRisques\s+de\s+pluie\b",
            "Risques de pluie",
        ),
        (
            r"\bOrages\s+et\s+pluies\b",
            "Orages et pluies",
        ),
        (
            r"\bPassages\s+nuageux\b",
            "Passages Nuageux",
        ),
        (
            r"\bEnsoleille\b",
            "Ensoleille",
        ),
        (
            r"\bNuageux\b",
            "Nuageux",
        ),
        (
            r"\bOrages\b",
            "Orages",
        ),
        (
            r"\bPluies\b",
            "Pluies",
        ),
    ]

    return _extraire_motif(
        texte_pdf,
        texte_ocr,
        "phenomene",
        motifs,
    )



# ============================================================
# LOT 9 — EXTRACTION PAR LOCALITÉ ET VISUALUNITS
# ============================================================

from pathlib import Path
import re
import fitz


def extraire_texte_pdf_panneau(page, bbox):
    """
    Extrait les mots natifs dans le panneau.

    Les coordonnées sont converties depuis la page PDF
    vers l'image locale du panneau, à l'échelle du rendu.
    """

    vide = {
        "texte": "",
        "mots": [],
        "lignes": [],
        "statut": "BBOX_INVALIDE",
    }

    if bbox is None or len(bbox) != 4:
        return vide

    rectangle = fitz.Rect(*map(float, bbox)) & page.rect

    if rectangle.is_empty or rectangle.is_infinite:
        return vide

    mots = []

    for element in page.get_text(
        "words",
        clip=rectangle,
        sort=True,
    ):
        if len(element) < 5:
            continue

        wx0, wy0, wx1, wy1, texte = element[:5]
        texte = str(texte).strip()

        if not texte:
            continue

        # Coordonnées locales en pixels.
        x0 = (wx0 - rectangle.x0) * SCALE_RENDER
        y0 = (wy0 - rectangle.y0) * SCALE_RENDER
        x1 = (wx1 - rectangle.x0) * SCALE_RENDER
        y1 = (wy1 - rectangle.y0) * SCALE_RENDER

        mots.append({
            "text": texte,
            "x": x0,
            "y": y0,
            "x2": x1,
            "y2": y1,
            "width": x1 - x0,
            "height": y1 - y0,
            "page_bbox_pdf": [
                float(wx0), float(wy0),
                float(wx1), float(wy1),
            ],
        })

    lignes = reconstruire_lignes_fusion(mots)

    return {
        "texte": "\n".join(
            ligne["text"] for ligne in lignes
        ),
        "mots": mots,
        "lignes": lignes,
        "statut": "OK" if mots else "SANS_TEXTE_NATIF",
    }


def combiner_textes_distincts(*textes):
    """Fusionne les lignes sans répéter les lignes identiques."""

    lignes = []
    deja_vues = set()

    for texte in textes:
        for ligne in str(texte or "").splitlines():
            ligne = ligne.strip()

            if not ligne:
                continue

            cle = normaliser_texte_ligne(ligne).lower()

            if cle not in deja_vues:
                deja_vues.add(cle)
                lignes.append(ligne)

    return "\n".join(lignes)


def construire_texte_unite_meteo(unite):
    """Construit le texte structuré destiné au RAG."""

    parties = []

    champs = (
        ("localite", "Localité"),
        ("temps", "Temps"),
        ("phenomene", "Phénomène"),
        ("direction_vent", "Direction du vent"),
        ("intensite_vent", "Intensité du vent"),
    )

    for cle, libelle in champs:
        valeur = unite.get(cle)

        if valeur:
            parties.append(f"{libelle} : {valeur}")

    t_min = unite.get("temperature_min")
    t_max = unite.get("temperature_max")

    if t_min is not None and t_max is not None:
        parties.insert(
            1 if parties else 0,
            f"Température : {t_min} °C / {t_max} °C",
        )

    return "\n".join(parties)


def extraire_unites_meteo_fusion(fusion, page):
    """
    Produit une extraction par localité réellement reconnue.

    Les informations du panneau complet ne sont jamais
    copiées dans chaque localité d'un panneau multi-localités.
    """

    localites = fusion.get("localites") or []

    if not localites:
        return []

    extraction_pdf = extraire_texte_pdf_panneau(
        page,
        fusion.get("bbox_rendu") or fusion.get("bbox"),
    )

    ocr_original = fusion.get("ocr_original") or {}
    ocr_recuperation = fusion.get("ocr_recuperation") or {}

    sources_lignes = {
        "pdf_natif": extraction_pdf["lignes"],
        "ocr_original": ocr_original.get("lignes") or [],
        "ocr_recuperation": ocr_recuperation.get("lignes") or [],
    }

    repartitions = {
        nom: associer_lignes_aux_localites(
            lignes,
            localites,
        )
        for nom, lignes in sources_lignes.items()
    }

    extractions = []

    for index, ancre in enumerate(localites):
        nom = ancre.get("localite")

        if not nom:
            continue

        texte_pdf = repartitions["pdf_natif"][index]["texte"]

        texte_ocr = combiner_textes_distincts(
            repartitions["ocr_original"][index]["texte"],
            repartitions["ocr_recuperation"][index]["texte"],
        )

        # Le texte brut du panneau ne peut servir de repli
        # que lorsqu'une seule localité est présente.
        if len(localites) == 1:
            texte_ocr = combiner_textes_distincts(
                texte_ocr,
                ocr_original.get("texte"),
                ocr_recuperation.get("texte"),
            )

        temperature = extraire_temperature(
            texte_pdf, texte_ocr
        )
        temps = extraire_temps(
            texte_pdf, texte_ocr
        )
        phenomene = extraire_phenomene(
            texte_pdf, texte_ocr
        )
        direction = extraire_direction_vent(
            texte_pdf, texte_ocr
        )
        intensite = extraire_intensite_vent(
            texte_pdf, texte_ocr
        )

        resultats = {
            "temperature": temperature,
            "temps": temps,
            "phenomene": phenomene,
            "direction_vent": direction,
            "intensite_vent": intensite,
        }

        unite = {
            "localite": nom,
            "temperature_min": temperature["temperature_min"],
            "temperature_max": temperature["temperature_max"],
            "unite_temperature": temperature["unite_temperature"],
            "temps": temps["temps"],
            "phenomene": phenomene["phenomene"],
            "direction_vent": direction["direction_vent"],
            "intensite_vent": intensite["intensite_vent"],
            "texte_ocr": texte_ocr,
            "texte_pdf_natif": texte_pdf,
            "texte_combine": combiner_textes_distincts(
                texte_pdf, texte_ocr
            ),
            "sources_extraction": {
                cle: valeur["source"]
                for cle, valeur in resultats.items()
            },
            "types_sources": {
                cle: valeur["source_type"]
                for cle, valeur in resultats.items()
            },
            "fichier": fusion.get("fichier"),
            "page": fusion.get("page"),
            "panel_id": fusion.get("panel_id"),
            "bbox_panneau": fusion.get("bbox"),
            "chemin_image": fusion.get("chemin_image"),
            "statut_pdf_natif": extraction_pdf["statut"],
        }

        extractions.append(unite)

    return extractions


def construire_unite_visuelle(extraction, occurrence):
    """
    Construit une VisualUnit compatible avec le chunking API.
    Aucun champ météorologique n'est recalculé.
    """

    fichier = Path(
        str(extraction.get("fichier") or "document.pdf")
    ).name

    document_id = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        Path(fichier).stem,
    ).strip("_")

    page = int(extraction.get("page") or 0)

    panel_id = re.sub(
        r"[^A-Za-z0-9_-]+",
        "_",
        str(extraction.get("panel_id") or "0"),
    ).strip("_")

    visual_unit_id = (
        f"{document_id}_p{page:02d}"
        f"_panel{panel_id}_u{occurrence:02d}"
    )

    chemin_image = extraction.get("chemin_image")
    bbox = extraction.get("bbox_panneau")

    texte_structure = construire_texte_unite_meteo(
        extraction
    )

    unite = {
        "visual_unit_id": visual_unit_id,
        "unit_id": visual_unit_id,
        "type": "visual",
        "sous_type": "panneau_meteorologique",
        "document_id": document_id,
        "document_source_id": document_id,
        "source_file": fichier,
        "fichier": fichier,
        "page": page,
        "panel_id": extraction.get("panel_id"),
        "bbox": bbox,
        "image_path": chemin_image,
        "chemin_image": chemin_image,
        "localite": extraction.get("localite"),
        "temperature_min": extraction.get("temperature_min"),
        "temperature_max": extraction.get("temperature_max"),
        "unite_temperature": extraction.get(
            "unite_temperature", "°C"
        ),
        "temps": extraction.get("temps"),
        "phenomene": extraction.get("phenomene"),
        "direction_vent": extraction.get("direction_vent"),
        "intensite_vent": extraction.get("intensite_vent"),
        "texte": texte_structure,
        "texte_structure": texte_structure,
        "texte_ocr": extraction.get("texte_ocr", ""),
        "texte_pdf_natif": extraction.get(
            "texte_pdf_natif", ""
        ),
        "texte_combine": extraction.get(
            "texte_combine", ""
        ),
        "sources_extraction": extraction.get(
            "sources_extraction", {}
        ),
        "types_sources": extraction.get(
            "types_sources", {}
        ),
        "statut_pdf_natif": extraction.get(
            "statut_pdf_natif"
        ),
        "source_image_presente": bool(
            chemin_image and Path(chemin_image).is_file()
        ),
        "bbox_presente": bool(bbox),
    }

    return unite


def construire_unites_visuelles_fusion(fusion, page):
    """
    Transforme les extractions d'un panneau en VisualUnit.

    Le numéro d'occurrence distingue plusieurs localités
    à l'intérieur d'un même panneau.
    """
    extractions = extraire_unites_meteo_fusion(fusion, page)

    return [
        construire_unite_visuelle(extraction, index)
        for index, extraction in enumerate(
            extractions, start=1
        )
    ]




# ============================================================
# LOT 10A — ORCHESTRATION DES VISUALUNITS D'UN PDF
# ============================================================

def extraire_visual_units_pdf(chemin_pdf, repertoire_images):
    """
    Traite les panneaux d'un PDF donné.

    Enchaînement :
    détection -> rendu -> OCR -> localités ->
    analyse spatiale -> fusion -> VisualUnits.

    Aucun accès à Qdrant ni aux fichiers JSON globaux.
    """

    chemin_pdf = Path(chemin_pdf)
    repertoire_images = Path(repertoire_images)

    if not chemin_pdf.is_file():
        raise FileNotFoundError(
            f"PDF introuvable : {chemin_pdf}"
        )

    repertoire_images.mkdir(
        parents=True,
        exist_ok=True,
    )

    nom_document = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        chemin_pdf.stem,
    ).strip("_")

    visual_units = []

    with fitz.open(chemin_pdf) as document:

        for numero_page, page in enumerate(
            document,
            start=1,
        ):
            # 1. Détection géométrique.
            panneaux = analyser_panneaux_page(page)

            if not panneaux:
                continue

            toutes_bboxes = [
                tuple(panneau["bbox"])
                for panneau in panneaux
            ]

            # 2. OCR pleine page, une seule fois.
            ocr_page = ocr_page_complete_fusion(page)

            for numero_panneau, candidat in enumerate(
                panneaux,
                start=1,
            ):
                try:
                    bbox_original = tuple(
                        candidat["bbox"]
                    )

                    bbox_rendu = resserrer_bbox(
                        bbox_original,
                        toutes_bboxes,
                    )

                    # 3. Rendu du panneau.
                    chemin_image = (
                        repertoire_images
                        / (
                            f"{nom_document}"
                            f"_p{numero_page:02d}"
                            f"_panel{numero_panneau:02d}.png"
                        )
                    )

                    rendre_panneau(
                        page,
                        bbox_rendu,
                        chemin_image,
                    )

                    # 4. OCR spatial du panneau.
                    resultat_ocr = extraire_ocr_spatial(
                        chemin_image
                    )

                    panneau = {
                        "fichier": chemin_pdf.name,
                        "page": numero_page,
                        "panel_id": numero_panneau,
                        "bbox": bbox_rendu,
                        "bbox_original": bbox_original,
                        "bbox_rendu": bbox_rendu,
                        "chemin_image": str(chemin_image),
                        "ocr_text": resultat_ocr["texte"],
                        "ocr_words": resultat_ocr["mots"],
                        "ocr_lines": resultat_ocr["lignes"],
                        "ocr_status": "OK",
                    }

                    # 5. Reconnaissance et attribution
                    # des localités.
                    panneau["localites_detectees"] = (
                        reconnaitre_localites_panneau(panneau)
                    )

                    attribuer_localites_panneau(panneau)

                    # 6. Analyse spatiale.
                    panneau["analyse_spatiale"] = (
                        analyser_panneau_spatial(panneau)
                    )

                    # 7. Fusion native + OCR.
                    fusion = fusionner_panneau_visuel(
                        panneau,
                        ocr_page,
                    )

                    # 8. Construction des VisualUnits.
                    unites_panneau = (
                        construire_unites_visuelles_fusion(
                            fusion,
                            page,
                        )
                    )

                    visual_units.extend(unites_panneau)

                except Exception as erreur:
                    raise RuntimeError(
                        "Échec de l'extraction visuelle "
                        f"de {chemin_pdf.name}, "
                        f"page {numero_page}, "
                        f"panneau {numero_panneau}"
                    ) from erreur

    return visual_units