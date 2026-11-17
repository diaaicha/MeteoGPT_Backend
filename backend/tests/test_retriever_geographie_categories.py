
from datetime import datetime

import pytest
import retriever


def contrainte_dakar():
    return {
        "mode": "specific",
        "localite": "Dakar",
    }


@pytest.mark.parametrize(
    "categorie",
    [
        "navigation_cotiere",
        "peche_artisanale",
        "marine_nationale",
    ],
)
def test_categorie_specialisee_sans_localite_structuree(
    monkeypatch,
    categorie,
):
    monkeypatch.setattr(
        retriever,
        "CATEGORIES_LOCALITE_STRUCTUREE",
        {"meteo_matin", "meteo_soir"},
    )

    chunk = {
        "category": categorie,
        "localite": None,
    }

    assert retriever.chunk_geographiquement_admissible(
        chunk,
        contrainte_dakar(),
    ) is True


def test_panneau_de_la_localite_demandee_est_admissible(
    monkeypatch,
):
    monkeypatch.setattr(
        retriever,
        "CATEGORIES_LOCALITE_STRUCTUREE",
        {"meteo_matin"},
    )

    chunk = {
        "category": "meteo_matin",
        "localite": "Dakar",
    }

    assert retriever.chunk_geographiquement_admissible(
        chunk,
        contrainte_dakar(),
    ) is True


def test_panneau_autre_localite_est_exclu(
    monkeypatch,
):
    monkeypatch.setattr(
        retriever,
        "CATEGORIES_LOCALITE_STRUCTUREE",
        {"meteo_matin"},
    )

    chunk = {
        "category": "meteo_matin",
        "localite": "Thiès",
    }

    assert retriever.chunk_geographiquement_admissible(
        chunk,
        contrainte_dakar(),
    ) is False


def test_chunk_non_localise_reste_admissible(
    monkeypatch,
):
    monkeypatch.setattr(
        retriever,
        "CATEGORIES_LOCALITE_STRUCTUREE",
        {"meteo_matin"},
    )

    chunk = {
        "category": "meteo_matin",
        "localite": None,
    }

    assert retriever.chunk_geographiquement_admissible(
        chunk,
        contrainte_dakar(),
    ) is True


def test_demande_generale_preserve_filtrage_panneaux(
    monkeypatch,
):
    monkeypatch.setattr(
        retriever,
        "CATEGORIES_LOCALITE_STRUCTUREE",
        {"meteo_matin"},
    )

    contrainte = {
        "mode": "general",
        "localite": None,
    }

    panneau = {
        "category": "meteo_matin",
        "localite": "Dakar",
    }

    chunk_general = {
        "category": "meteo_matin",
        "localite": None,
    }

    assert retriever.chunk_geographiquement_admissible(
        panneau, contrainte
    ) is False

    assert retriever.chunk_geographiquement_admissible(
        chunk_general, contrainte
    ) is True


def test_categorie_specialisee_avec_localite_structuree(
    monkeypatch,
):
    # Si une categorie possede reellement des localites
    # structurees, conserver son filtrage existant.
    monkeypatch.setattr(
        retriever,
        "CATEGORIES_LOCALITE_STRUCTUREE",
        {"navigation_cotiere"},
    )

    chunk = {
        "category": "navigation_cotiere",
        "localite": "Thiès",
    }

    assert retriever.chunk_geographiquement_admissible(
        chunk,
        contrainte_dakar(),
    ) is False


def test_selection_conserve_bulletin_navigation_sans_localite(
    monkeypatch,
):
    now = datetime(
        2026, 9, 21, 12, 0,
        tzinfo=retriever.METEOGPT_TIMEZONE,
    )

    chunks = [
        {
            "chunk_id": "nav-test",
            "category": "navigation_cotiere",
            "content": "Conditions de navigation",
        },
        {
            "chunk_id": "meteo-test",
            "category": "meteo_matin",
            "localite": "Thiès",
            "content": "Bulletin météorologique",
        },
    ]

    monkeypatch.setattr(
        retriever,
        "BM25_CHUNKS",
        chunks,
    )

    monkeypatch.setattr(
        retriever,
        "CATEGORIES_LOCALITE_STRUCTUREE",
        {"meteo_matin"},
    )

    # Neutraliser uniquement la selection temporelle :
    # ce test porte sur la categorie et la geographie.
    monkeypatch.setattr(
        retriever,
        "selectionner_chunks_temporels",
        lambda *, chunks, temporalite, now: chunks,
    )

    contraintes = {
        "category": {
            "mode": "explicit",
            "categories": ["navigation_cotiere"],
        },
        "location": {
            "mode": "specific",
            "localite": "Dakar",
        },
        "temporal": {
            "mode": "current",
            "start": now,
            "end": now,
        },
    }

    resultat = retriever.selectionner_chunks_admissibles(
        query="Conditions de navigation à Dakar",
        contraintes=contraintes,
        now=now,
    )

    assert resultat["chunk_ids"] == ["nav-test"]
    assert resultat["data_status"] == "valid"
    assert resultat["fallback_used"] is False
