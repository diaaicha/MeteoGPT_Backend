
import fitz

from src.visual_panel_extraction import (
    extraire_texte_pdf_panneau,
    extraire_unites_meteo_fusion,
    construire_unites_visuelles_fusion,
)


def creer_page():
    doc = fitz.open()
    page = doc.new_page(width=500, height=350)
    return doc, page


def test_extraction_pdf_natif_dans_panneau():
    doc, page = creer_page()

    page.insert_text((80, 110), "Dakar")
    page.insert_text((80, 145), "27°C/33°C")

    resultat = extraire_texte_pdf_panneau(
        page,
        (50, 60, 230, 230),
    )

    assert resultat["statut"] == "OK"
    assert "Dakar" in resultat["texte"]
    assert len(resultat["mots"]) >= 2
    assert resultat["mots"][0]["x"] >= 0
    assert "page_bbox_pdf" in resultat["mots"][0]

    doc.close()


def test_deux_localites_temperatures_distinctes():
    doc, page = creer_page()

    page.insert_text((80, 110), "Dakar")
    page.insert_text((80, 145), "27°C/33°C")

    page.insert_text((310, 110), "Thies")
    page.insert_text((310, 145), "20°C/24°C")

    fusion = {
        "fichier": "Meteo_matin_test.pdf",
        "page": 1,
        "panel_id": "01",
        "bbox": (50, 60, 450, 230),
        "bbox_rendu": (50, 60, 450, 230),
        "localites": [
            {"localite": "Dakar", "x": 60, "y": 70},
            {"localite": "Thiès", "x": 520, "y": 70},
        ],
        "ocr_original": {"texte": "", "lignes": []},
        "ocr_recuperation": {"texte": "", "lignes": []},
    }

    unites = extraire_unites_meteo_fusion(fusion, page)

    assert len(unites) == 2

    par_ville = {
        unite["localite"]: unite
        for unite in unites
    }

    assert par_ville["Dakar"]["temperature_min"] == 27
    assert par_ville["Dakar"]["temperature_max"] == 33

    assert par_ville["Thiès"]["temperature_min"] == 20
    assert par_ville["Thiès"]["temperature_max"] == 24

    assert "20°C/24°C" not in (
        par_ville["Dakar"]["texte_pdf_natif"]
    )
    assert "27°C/33°C" not in (
        par_ville["Thiès"]["texte_pdf_natif"]
    )

    doc.close()


def test_pas_de_localite_pas_unite():
    doc, page = creer_page()

    fusion = {
        "bbox": (10, 10, 200, 150),
        "localites": [],
    }

    assert extraire_unites_meteo_fusion(
        fusion, page
    ) == []

    doc.close()


def test_interdiction_repli_global_multi_localites():
    doc, page = creer_page()

    fusion = {
        "fichier": "Meteo_soir_test.pdf",
        "page": 1,
        "panel_id": "02",
        "bbox": (10, 10, 300, 200),
        "localites": [
            {"localite": "Dakar", "x": 20, "y": 20},
            {"localite": "Thiès", "x": 200, "y": 20},
        ],
        "ocr_original": {
            "texte": "29°C/35°C",
            "lignes": [],
        },
        "ocr_recuperation": {
            "texte": "",
            "lignes": [],
        },
    }

    unites = extraire_unites_meteo_fusion(fusion, page)

    assert len(unites) == 2
    assert all(
        unite["temperature_min"] is None
        for unite in unites
    )
    assert all(
        unite["temperature_max"] is None
        for unite in unites
    )

    doc.close()


def test_visual_units_format_compatible_api():
    doc, page = creer_page()

    page.insert_text((80, 110), "Dakar")
    page.insert_text((80, 145), "27°C/33°C")

    fusion = {
        "fichier": "Meteo_matin_test.pdf",
        "page": 1,
        "panel_id": "01",
        "bbox": (50, 60, 230, 230),
        "bbox_rendu": (50, 60, 230, 230),
        "chemin_image": "panneau_test.png",
        "localites": [
            {"localite": "Dakar", "x": 60, "y": 70}
        ],
        "ocr_original": {"texte": "", "lignes": []},
        "ocr_recuperation": {"texte": "", "lignes": []},
    }

    unites = construire_unites_visuelles_fusion(
        fusion, page
    )

    assert len(unites) == 1

    unite = unites[0]

    assert unite["type"] == "visual"
    assert unite["source_file"] == "Meteo_matin_test.pdf"
    assert unite["document_id"] == "Meteo_matin_test"
    assert unite["localite"] == "Dakar"
    assert unite["temperature_min"] == 27
    assert unite["temperature_max"] == 33

    assert unite["visual_unit_id"]
    assert unite["image_path"] == "panneau_test.png"
    assert "Dakar" in unite["texte"]
    assert "27 °C / 33 °C" in unite["texte"]

    doc.close()
