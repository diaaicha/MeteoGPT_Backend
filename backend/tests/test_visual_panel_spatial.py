
from src.visual_panel_extraction import (
    bbox_ligne_ocr,
    determiner_dimensions_ocr,
    classifier_position_x,
    classifier_position_y,
    analyser_panneau_spatial,
)


def test_reconstruction_bbox_ligne():
    ligne = {
        "x": 10,
        "y": 20,
        "width": 50,
        "height": 15,
    }

    assert bbox_ligne_ocr(ligne) == (
        10.0, 20.0, 60.0, 35.0
    )

    assert bbox_ligne_ocr({"text": "Dakar"}) is None


def test_dimensions_ocr_a_partir_des_mots():
    panneau = {
        "ocr_words": [
            {
                "x": 10, "y": 20,
                "x2": 110, "y2": 60,
            },
            {
                "x": 5, "y": 15,
                "x2": 80, "y2": 45,
            },
        ],
    }

    dimensions = determiner_dimensions_ocr(panneau)

    assert dimensions["x_min"] == 5
    assert dimensions["y_min"] == 15
    assert dimensions["largeur"] == 105
    assert dimensions["hauteur"] == 45


def test_classification_positions():
    assert classifier_position_x(0.1) == "gauche"
    assert classifier_position_x(0.5) == "centre"
    assert classifier_position_x(0.9) == "droite"

    assert classifier_position_y(0.1) == "haut"
    assert classifier_position_y(0.5) == "milieu"
    assert classifier_position_y(0.9) == "bas"


def test_analyse_spatiale_panneau_multi_localites():
    panneau = {
        "ocr_words": [
            {"x": 10, "y": 10, "x2": 70, "y2": 30},
            {"x": 10, "y": 50, "x2": 110, "y2": 70},
            {"x": 10, "y": 90, "x2": 80, "y2": 110},
        ],
        "ocr_lines": [
            {
                "text": "Dakar",
                "x": 10, "y": 10,
                "x2": 70, "y2": 30,
            },
            {
                "text": "Vent fort",
                "x": 10, "y": 50,
                "x2": 110, "y2": 70,
            },
            {
                "text": "Thies",
                "x": 10, "y": 90,
                "x2": 80, "y2": 110,
            },
        ],
        "localites_panneau": [
            {
                "localite": "Dakar",
                "texte_ocr": "Dakar",
                "score": 100,
            },
            {
                "localite": "Thiès",
                "texte_ocr": "Thies",
                "score": 95,
            },
        ],
    }

    resultat = analyser_panneau_spatial(panneau)

    assert resultat["nombre_lignes_ocr"] == 3
    assert resultat["nombre_localites"] == 2
    assert resultat["multi_localite"] is True

    assert resultat["localites_detectees"] == [
        "Dakar", "Thiès"
    ]

    assert len(resultat["ancres_localites"]) == 2

    assert resultat["lignes"][0]["zone_y"] == "haut"
    assert resultat["lignes"][1]["zone_y"] == "milieu"
    assert resultat["lignes"][2]["zone_y"] == "bas"

    assert resultat["lignes"][1]["est_ancre_localite"] is False


def test_analyse_panneau_sans_ocr():
    resultat = analyser_panneau_spatial({
        "ocr_words": [],
        "ocr_lines": [],
        "localites_panneau": [],
    })

    assert resultat["nombre_lignes_ocr"] == 0
    assert resultat["nombre_localites"] == 0
    assert resultat["multi_localite"] is False
    assert resultat["dimensions_ocr"]["largeur"] == 1.0
    assert resultat["blocs"]["haut"] == []
