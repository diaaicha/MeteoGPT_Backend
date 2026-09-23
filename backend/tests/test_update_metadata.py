from src.meteogpt_update_api_pipeline import (
    inferer_categorie_document_api,
    inferer_validite_api,
)


def test_inferer_categorie_meteo_soir():

    result = inferer_categorie_document_api(
        "Bulletin_Meteo soir_21-09-2026.pdf"
    )

    assert result == {
        "category": "meteo_soir",
        "document_type": "bulletin_meteo_soir",
    }


def test_inferer_validite_meteo_soir():

    result = inferer_validite_api(
        "Bulletin_Meteo soir_21-09-2026.pdf",
        "meteo_soir",
    )

    assert result == {
        "date_publication": "2026-09-21",
        "date_debut_validite": "2026-09-21 21:00",
        "date_fin_validite": "2026-09-22 21:00",
    }


def test_inferer_categorie_marine_nationale():

    result = inferer_categorie_document_api(
        "Bulletin_Marine nationale_21-09-2026.pdf"
    )

    assert result == {
        "category": "marine_nationale",
        "document_type": "bulletin_marine_nationale",
    }


def test_inferer_validite_marine_nationale():

    result = inferer_validite_api(
        "Bulletin_Marine nationale_21-09-2026.pdf",
        "marine_nationale",
    )

    assert result == {
        "date_publication": "2026-09-21",
        "date_debut_validite": "2026-09-21 12:00",
        "date_fin_validite": "2026-09-22 12:00",
    }