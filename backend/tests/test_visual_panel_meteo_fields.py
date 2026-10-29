
from src.visual_panel_extraction import (
    extraire_temperature,
    extraire_temps,
    extraire_direction_vent,
    extraire_intensite_vent,
    extraire_phenomene,
)


def test_temperature_priorite_pdf_natif():
    resultat = extraire_temperature(
        "28°C/33°C",
        "20°C/25°C",
    )

    assert resultat["temperature_min"] == 28
    assert resultat["temperature_max"] == 33
    assert resultat["source_type"] == "pdf_natif"


def test_temperature_ocr_variante():
    resultat = extraire_temperature(
        "",
        "28IC/33IC",
    )

    assert resultat["temperature_min"] == 28
    assert resultat["temperature_max"] == 33
    assert resultat["source_type"] == "ocr"


def test_absence_temperature_n_invente_rien():
    resultat = extraire_temperature(
        "Bulletin météorologique",
        "Ciel nuageux",
    )

    assert resultat["temperature_min"] is None
    assert resultat["temperature_max"] is None
    assert resultat["source_type"] is None


def test_reconnaissance_temps_chaud():
    resultat = extraire_temps("", "Temps Chaud")

    assert resultat["temps"] == "Temps Chaud"
    assert resultat["source_type"] == "ocr"


def test_direction_vent_composee():
    resultat = extraire_direction_vent(
        "",
        "Vent : Ouest à Sud-Ouest",
    )

    assert (
        resultat["direction_vent"]
        == "Ouest à Sud-Ouest"
    )


def test_intensite_composee():
    resultat = extraire_intensite_vent(
        "",
        "Vent faible à modéré",
    )

    assert (
        resultat["intensite_vent"]
        == "Faible à modéré"
    )


def test_phenomene_formulation_longue():
    resultat = extraire_phenomene(
        "",
        "Nuageux la nuit avec faibles chances de pluie",
    )

    assert resultat["phenomene"] == (
        "Nuageux la nuit avec faibles chances de pluie"
    )


def test_phenomene_absent():
    resultat = extraire_phenomene(
        "Bulletin météo",
        "Aucune information lisible",
    )

    assert resultat["phenomene"] is None
    assert resultat["source"] is None
    assert resultat["source_type"] is None
