
import fitz

from src import visual_panel_extraction as extraction


def test_reconstruction_lignes_fusion():
    mots = [
        {"text": "27", "x": 85, "y": 10, "x2": 110, "y2": 25},
        {"text": "Vent", "x": 10, "y": 55, "x2": 45, "y2": 70},
        {"text": "Dakar", "x": 10, "y": 10, "x2": 65, "y2": 25},
    ]

    lignes = extraction.reconstruire_lignes_fusion(mots)

    assert len(lignes) == 2
    assert lignes[0]["text"] == "Dakar 27"
    assert lignes[1]["text"] == "Vent"
    assert lignes[0]["x"] == 10
    assert lignes[0]["x2"] == 110


def test_ocr_page_complete_mode_recuperation(monkeypatch):
    doc = fitz.open()
    page = doc.new_page(width=200, height=100)

    donnees = {
        "text": ["Dakar", "27"],
        "conf": ["95", "80"],
        "left": [20, 90],
        "top": [15, 15],
        "width": [50, 20],
        "height": [15, 15],
    }

    appels = []

    def faux_ocr(image, lang, config, output_type):
        appels.append((lang, config))
        return donnees

    monkeypatch.setattr(
        extraction.pytesseract,
        "image_to_data",
        faux_ocr,
    )

    resultat = extraction.ocr_page_complete_fusion(page)

    assert appels == [("fra", "--psm 11")]
    assert resultat["scale"] == 2.0
    assert resultat["image_width"] == 400
    assert resultat["image_height"] == 200
    assert resultat["text"] == "Dakar 27"
    assert resultat["words"][0]["centre_x"] == 45

    doc.close()


def test_projection_coordonnees_page_vers_panneau():
    page_data = {
        "scale": 2.0,
        "words": [
            {
                "text": "Dakar",
                "x": 210, "y": 120,
                "x2": 270, "y2": 140,
                "centre_x": 240,
                "centre_y": 130,
            },
            {
                "text": "Hors panneau",
                "x": 500, "y": 120,
                "x2": 570, "y2": 140,
                "centre_x": 535,
                "centre_y": 130,
            },
        ],
    }

    panneau = {
        "bbox_rendu": (100, 50, 200, 150)
    }

    mots = extraction.extraire_mots_panneau_fusion(
        page_data,
        panneau,
    )

    assert len(mots) == 1
    assert mots[0]["text"] == "Dakar"

    assert mots[0]["x"] == 10
    assert mots[0]["y"] == 20
    assert mots[0]["x2"] == 70
    assert mots[0]["y2"] == 40

    assert mots[0]["page_bbox_px"] == (
        210, 120, 270, 140
    )


def test_absence_ocr_page_ou_bbox():
    assert extraction.extraire_mots_panneau_fusion(
        None,
        {"bbox": (0, 0, 100, 100)},
    ) == []

    assert extraction.extraire_mots_panneau_fusion(
        {"scale": 2.0, "words": []},
        {},
    ) == []


def test_association_mono_localite():
    lignes = [
        {
            "text": "Pluie faible",
            "x": 20, "y": 40,
            "x2": 110, "y2": 55,
        }
    ]

    localites = [
        {"localite": "Dakar", "x": 10, "y": 10}
    ]

    blocs = extraction.associer_lignes_aux_localites(
        lignes, localites
    )

    assert len(blocs) == 1
    assert blocs[0]["localite"] == "Dakar"
    assert blocs[0]["texte"] == "Pluie faible"
    assert blocs[0]["lignes"] == lignes


def test_association_multi_localites_meme_ligne():
    lignes = [
        {
            "text": "PLUIE CHAUD",
            "x": 30, "y": 50,
            "x2": 270, "y2": 65,
            "mots": [
                {
                    "text": "PLUIE",
                    "x": 30, "y": 50,
                    "x2": 80, "y2": 65,
                },
                {
                    "text": "CHAUD",
                    "x": 220, "y": 50,
                    "x2": 270, "y2": 65,
                },
            ],
        }
    ]

    localites = [
        {"localite": "Dakar", "x": 20, "y": 10},
        {"localite": "Thiès", "x": 210, "y": 10},
    ]

    blocs = extraction.associer_lignes_aux_localites(
        lignes, localites
    )

    assert blocs[0]["texte"] == "PLUIE"
    assert blocs[1]["texte"] == "CHAUD"


def test_association_sans_localite():
    blocs = extraction.associer_lignes_aux_localites(
        [{"text": "Vent", "x": 10, "y": 10,
          "x2": 50, "y2": 25}],
        [],
    )

    assert blocs == []


def test_fusion_panneau_avec_ocr_recuperation():
    panneau = {
        "fichier": "Bulletin_Meteo_soir.pdf",
        "page": 2,
        "panel_id": "panel01",
        "bbox": (100, 50, 200, 150),
        "bbox_rendu": (100, 50, 200, 150),
        "chemin_image": "panel01.png",
        "ocr_text": "Dakar",
        "ocr_words": [],
        "ocr_lines": [],
        "localites_panneau": [
            {"localite": "Dakar", "x": 10, "y": 10}
        ],
        "analyse_spatiale": {"nombre_localites": 1},
    }

    page_data = {
        "scale": 2.0,
        "words": [
            {
                "text": "Pluie",
                "x": 220, "y": 120,
                "x2": 270, "y2": 140,
                "centre_x": 245,
                "centre_y": 130,
            }
        ],
    }

    fusion = extraction.fusionner_panneau_visuel(
        panneau,
        page_data,
    )

    assert fusion["texte_fusionne"] == "Dakar\nPluie"
    assert fusion["nombre_localites"] == 1
    assert fusion["multi_localite"] is False

    assert fusion["blocs_localites"][0]["texte"] == "Pluie"
    assert fusion["ocr_recuperation"]["mots"][0]["x"] == 20

    # Les données originales ne sont pas altérées.
    assert panneau["ocr_text"] == "Dakar"
    assert panneau["localites_panneau"][0]["x"] == 10


def test_fusion_sans_ocr_page():
    panneau = {
        "fichier": "Bulletin_Meteo_matin.pdf",
        "page": 2,
        "panel_id": "panel02",
        "bbox": (10, 10, 100, 80),
        "ocr_text": "Thiès\nTempérature",
        "ocr_words": [],
        "ocr_lines": [],
        "localites_panneau": [],
    }

    fusion = extraction.fusionner_panneau_visuel(
        panneau,
        None,
    )

    assert fusion["texte_fusionne"] == (
        "Thiès\nTempérature"
    )
    assert fusion["ocr_recuperation"]["mots"] == []
    assert fusion["blocs_localites"] == []
    assert fusion["nombre_localites"] == 0