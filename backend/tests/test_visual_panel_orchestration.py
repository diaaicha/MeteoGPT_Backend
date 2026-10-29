
import fitz
import pytest

from src import visual_panel_extraction as extraction


def creer_pdf_avec_panneau(tmp_path):
    chemin = tmp_path / "Meteo_matin_test.pdf"

    doc = fitz.open()
    page = doc.new_page(width=600, height=800)

    page.draw_rect(
        fitz.Rect(80, 100, 300, 210),
        color=None,
        fill=(0.1, 0.4, 0.9),
    )

    page.insert_text(
        (110, 180),
        "27°C/33°C",
    )

    doc.save(str(chemin))
    doc.close()

    return chemin


def test_orchestration_extrait_visual_unit(
    monkeypatch, tmp_path
):
    chemin = creer_pdf_avec_panneau(tmp_path)

    appels = []

    def faux_ocr(image, lang, config, output_type):
        appels.append(config)

        # OCR pleine page : aucun mot complémentaire.
        if config == "--psm 11":
            return {
                "text": [],
                "conf": [],
                "left": [],
                "top": [],
                "width": [],
                "height": [],
            }

        # OCR du panneau : ancre de localité.
        return {
            "text": ["Dakar"],
            "conf": ["95"],
            "left": [30],
            "top": [20],
            "width": [60],
            "height": [20],
        }

    monkeypatch.setattr(
        extraction.pytesseract,
        "image_to_data",
        faux_ocr,
    )

    unites = extraction.extraire_visual_units_pdf(
        chemin,
        tmp_path / "images",
    )

    assert len(unites) == 1

    unite = unites[0]

    assert unite["source_file"] == chemin.name
    assert unite["localite"] == "Dakar"
    assert unite["visual_unit_id"]
    assert unite["page"] == 1
    assert unite["temperature_min"] == 27
    assert unite["temperature_max"] == 33
    assert unite["source_image_presente"] is True

    # Une analyse OCR de la page, une du panneau.
    assert appels.count("--psm 11") == 1
    assert appels.count("--psm 6") == 1


def test_pdf_sans_panneau_ne_declenche_pas_ocr(
    monkeypatch, tmp_path
):
    chemin = tmp_path / "Meteo_soir_vide.pdf"

    doc = fitz.open()
    doc.new_page(width=600, height=800)
    doc.save(str(chemin))
    doc.close()

    def ocr_interdit(*args, **kwargs):
        raise AssertionError(
            "OCR déclenché sur une page sans panneau."
        )

    monkeypatch.setattr(
        extraction.pytesseract,
        "image_to_data",
        ocr_interdit,
    )

    unites = extraction.extraire_visual_units_pdf(
        chemin,
        tmp_path / "images",
    )

    assert unites == []


def test_echec_ocr_est_signale(
    monkeypatch, tmp_path
):
    chemin = creer_pdf_avec_panneau(tmp_path)

    def faux_ocr(*args, **kwargs):
        raise RuntimeError("Erreur Tesseract simulée")

    monkeypatch.setattr(
        extraction.pytesseract,
        "image_to_data",
        faux_ocr,
    )

    with pytest.raises(
        RuntimeError,
        match="Échec|Erreur Tesseract",
    ):
        extraction.extraire_visual_units_pdf(
            chemin,
            tmp_path / "images",
        )
