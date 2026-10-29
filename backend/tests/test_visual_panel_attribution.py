
from src.visual_panel_extraction import (
    coordonnee_valide,
    attribuer_localites_panneau,
)


def test_validation_coordonnees():
    assert coordonnee_valide(0)
    assert coordonnee_valide(25.5)
    assert coordonnee_valide("12.5")

    assert not coordonnee_valide(-2)
    assert not coordonnee_valide(None)
    assert not coordonnee_valide("invalide")
    assert not coordonnee_valide(float("nan"))


def test_attribution_localite_unique():
    panneau = {
        "ocr_lines": [{"text": "Dakar"}],
        "localites_detectees": [
            {
                "localite": "Dakar",
                "texte_ocr": "DAKAR",
                "score": 100,
                "x": 20,
                "y": 15,
            }
        ],
    }

    resultat = attribuer_localites_panneau(panneau)

    assert len(resultat["localites_panneau"]) == 1
    assert resultat["localites_panneau"][0]["localite"] == "Dakar"
    assert resultat["localites_panneau"][0]["x"] == 20
    assert resultat["ocr_lines"] == [{"text": "Dakar"}]


def test_panneau_plusieurs_localites():
    panneau = {
        "localites_detectees": [
            {"localite": "Thiès", "x": 40, "y": 80},
            {"localite": "Dakar", "x": 20, "y": 20},
            {"localite": "Mbour", "x": 10, "y": 55},
        ]
    }

    resultat = attribuer_localites_panneau(panneau)

    assert [
        ancre["localite"]
        for ancre in resultat["localites_panneau"]
    ] == ["Dakar", "Mbour", "Thiès"]


def test_doublons_et_coordonnees_invalides():
    panneau = {
        "localites_detectees": [
            {"localite": "Dakar", "x": 10, "y": 20},
            {"localite": "Dakar", "x": 12, "y": 25},
            {"localite": "Thiès", "x": -1, "y": 30},
            {"localite": "Fatick", "x": None, "y": 40},
            {"localite": "Mbour", "x": 15, "y": 50},
        ]
    }

    resultat = attribuer_localites_panneau(panneau)

    assert [
        ancre["localite"]
        for ancre in resultat["localites_panneau"]
    ] == ["Dakar", "Mbour"]

    # Les ancres détectées d'origine restent disponibles.
    assert len(resultat["localites_detectees"]) == 5


def test_panneau_sans_localite():
    panneau = {
        "localites_detectees": []
    }

    resultat = attribuer_localites_panneau(panneau)

    assert resultat["localites_panneau"] == []