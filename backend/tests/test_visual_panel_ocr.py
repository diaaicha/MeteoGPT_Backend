
from PIL import Image

from src import visual_panel_extraction as extraction


def creer_image_test(tmp_path):
    chemin = tmp_path / "panneau.png"
    Image.new("RGB", (300, 150), "white").save(chemin)
    return chemin


def test_ocr_spatial_reconstruit_lignes(monkeypatch, tmp_path):
    chemin = creer_image_test(tmp_path)

    donnees = {
        "text": ["23", "Dakar", "C", "Vent"],
        "conf": ["85", "97", "90", "92"],
        "left": [60, 10, 80, 10],
        "top": [10, 10, 10, 40],
        "width": [15, 40, 12, 30],
        "height": [12, 12, 12, 12],
    }

    appels = []

    def faux_ocr(image, lang, config, output_type):
        appels.append({
            "lang": lang,
            "config": config,
            "output_type": output_type,
        })
        return donnees

    monkeypatch.setattr(
        extraction.pytesseract,
        "image_to_data",
        faux_ocr,
    )

    resultat = extraction.extraire_ocr_spatial(chemin)

    assert resultat["texte"] == "Dakar 23 C\nVent"
    assert len(resultat["mots"]) == 4
    assert len(resultat["lignes"]) == 2

    assert resultat["lignes"][0]["x"] == 10
    assert resultat["lignes"][0]["x2"] == 92
    assert resultat["lignes"][1]["y"] == 40

    assert appels[0]["lang"] == "fra"
    assert appels[0]["config"] == "--psm 6"


def test_ocr_spatial_ignore_elements_vides(
    monkeypatch, tmp_path
):
    chemin = creer_image_test(tmp_path)

    donnees = {
        "text": ["", "   "],
        "conf": ["-1", "-1"],
        "left": [0, 0],
        "top": [0, 0],
        "width": [0, 0],
        "height": [0, 0],
    }

    monkeypatch.setattr(
        extraction.pytesseract,
        "image_to_data",
        lambda *args, **kwargs: donnees,
    )

    resultat = extraction.extraire_ocr_spatial(chemin)

    assert resultat == {
        "texte": "",
        "mots": [],
        "lignes": [],
    }


def test_ocr_spatial_confiance_invalide(
    monkeypatch, tmp_path
):
    chemin = creer_image_test(tmp_path)

    donnees = {
        "text": ["Thiès"],
        "conf": ["invalide"],
        "left": [12],
        "top": [20],
        "width": [46],
        "height": [15],
    }

    monkeypatch.setattr(
        extraction.pytesseract,
        "image_to_data",
        lambda *args, **kwargs: donnees,
    )

    resultat = extraction.extraire_ocr_spatial(chemin)

    assert resultat["mots"][0]["text"] == "Thiès"
    assert resultat["mots"][0]["confidence"] == -1.0
    assert resultat["mots"][0]["x2"] == 58
    assert resultat["mots"][0]["y2"] == 35
