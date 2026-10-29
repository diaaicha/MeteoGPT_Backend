
from src.visual_panel_extraction import (
    normaliser_localite,
    reconnaitre_localite,
    reconnaitre_localites_panneau,
)


def test_normalisation_localites():
    assert normaliser_localite("Thiès") == "THIES"
    assert normaliser_localite("Saint–Louis") == "SAINT-LOUIS"


def test_reconnaissance_exacte_et_erreur_ocr():
    assert reconnaitre_localite("THIES")["localite"] == "Thiès"
    assert reconnaitre_localite("Diorbel")["localite"] == "Diourbel"


def test_correspondance_moyenne_avec_token_exact():
    resultat = reconnaitre_localite("Dakar 23 C")

    assert resultat is not None
    assert resultat["localite"] == "Dakar"
    assert 50 <= resultat["score"] < 75


def test_faux_positif_rejete():
    assert reconnaitre_localite("Faible . |") is None
    assert reconnaitre_localite("Vent") is None


def test_ancres_spatiales_et_dedoublonnage():
    panneau = {
        "ocr_lines": [
            {
                "text": "Dakar",
                "x": 20, "y": 10,
                "x2": 70, "y2": 25,
            },
            {
                "text": "Dakar",
                "x": 25, "y": 10.02,
                "x2": 75, "y2": 25,
            },
            {
                "text": "Thiès",
                "x": 15, "y": 45,
                "x2": 75, "y2": 60,
            },
        ]
    }

    resultat = reconnaitre_localites_panneau(panneau)

    assert len(resultat) == 2
    assert [r["localite"] for r in resultat] == [
        "Dakar", "Thiès"
    ]
    assert resultat[0]["bbox"] == (20, 10, 70, 25)
    assert resultat[0]["width"] == 50
    assert resultat[0]["height"] == 15
