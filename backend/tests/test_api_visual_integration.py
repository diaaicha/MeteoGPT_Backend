
import json

import fitz
import pytest

from src import meteogpt_update_api_pipeline as pipeline
from src import visual_panel_extraction as extraction


def creer_config(tmp_path):
    return pipeline.MeteoGPTApiConfig(
        root_dir=str(tmp_path),
    )


def sauvegarder_visuels(config, units):
    config.visual_units_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    config.visual_units_file.write_text(
        json.dumps(units, ensure_ascii=False),
        encoding="utf-8",
    )


@pytest.mark.parametrize("periode", ["matin", "soir"])
def test_nouveau_pdf_declenche_extraction_ocr(
    monkeypatch, tmp_path, periode
):
    config = creer_config(tmp_path)

    pdf = tmp_path / f"Meteo_{periode}_test.pdf"
    pdf.touch()

    appels = []

    def faux_extracteur(chemin, repertoire):
        appels.append(chemin.name)

        return [{
            "visual_unit_id": "visual_test",
            "document_id": pdf.stem,
            "page": 1,
            "localite": "Dakar",
            "texte": "Localité : Dakar",
        }]

    monkeypatch.setattr(
        extraction,
        "extraire_visual_units_pdf",
        faux_extracteur,
    )

    resultat = pipeline.construire_visual_units_api(
        [pdf],
        config,
    )

    assert appels == [pdf.name]
    assert len(resultat) == 1

    assert resultat[0]["source_file"] == pdf.name
    assert resultat[0]["category"] == (
        f"meteo_{periode}"
    )
    assert resultat[0]["localite"] == "Dakar"


def test_pdf_sans_panneau_ne_reutilise_pas_ancien(
    monkeypatch, tmp_path
):
    config = creer_config(tmp_path)

    pdf = tmp_path / "Meteo_soir_test.pdf"
    pdf.touch()

    sauvegarder_visuels(config, [{
        "source_file": pdf.name,
        "visual_unit_id": "ancien_visuel",
        "localite": "Thiès",
    }])

    monkeypatch.setattr(
        extraction,
        "extraire_visual_units_pdf",
        lambda chemin, repertoire: [],
    )

    resultat = pipeline.construire_visual_units_api(
        [pdf],
        config,
    )

    assert resultat == []


def test_autre_categorie_conserve_comportement(
    monkeypatch, tmp_path
):
    config = creer_config(tmp_path)

    pdf = tmp_path / "Marine_nationale_test.pdf"
    pdf.touch()

    sauvegarder_visuels(config, [{
        "source_file": pdf.name,
        "visual_unit_id": "marine_existant",
        "localite": None,
    }])

    def ocr_interdit(*args, **kwargs):
        raise AssertionError(
            "OCR panneau non prévu pour Marine nationale"
        )

    monkeypatch.setattr(
        extraction,
        "extraire_visual_units_pdf",
        ocr_interdit,
    )

    resultat = pipeline.construire_visual_units_api(
        [pdf],
        config,
    )

    assert len(resultat) == 1
    assert resultat[0]["visual_unit_id"] == (
        "marine_existant"
    )


def test_page_images_utilise_visuels_fournis(
    monkeypatch, tmp_path
):
    config = creer_config(tmp_path)

    pdf = tmp_path / "Meteo_matin_test.pdf"

    doc = fitz.open()
    doc.new_page(width=300, height=200)
    doc.save(str(pdf))
    doc.close()

    def reconstruction_interdite(*args, **kwargs):
        raise AssertionError(
            "Deuxième construction des VisualUnits"
        )

    monkeypatch.setattr(
        pipeline,
        "construire_visual_units_api",
        reconstruction_interdite,
    )

    document_id = pipeline.nom_fichier_securise_api(
        pdf.stem
    )

    pages = pipeline.construire_page_image_units_api(
        [pdf],
        config,
        visual_units=[{
            "document_id": document_id,
            "source_file": pdf.name,
            "page": 1,
            "visual_unit_id": "visual_001",
        }],
    )

    assert len(pages) == 1
    assert pages[0]["contains_panel"] is True
    assert pages[0]["contains_visual_units"] is True


def test_remplacement_json_avec_liste_vide(tmp_path):
    config = creer_config(tmp_path)

    sauvegarder_visuels(config, [
        {
            "source_file": "Meteo_soir_test.pdf",
            "visual_unit_id": "ancien",
        },
        {
            "source_file": "Marine_nationale_test.pdf",
            "visual_unit_id": "a_conserver",
        },
    ])

    resultat = pipeline.update_global_json_file(
        config.visual_units_file,
        [],
        source_files_to_replace=[
            "Meteo_soir_test.pdf",
        ],
    )

    assert len(resultat) == 1
    assert resultat[0]["visual_unit_id"] == (
        "a_conserver"
    )
