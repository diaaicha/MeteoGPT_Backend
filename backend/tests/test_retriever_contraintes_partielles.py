
from datetime import datetime

import retriever


def test_contrainte_partielle_completee_sans_ecrasement(
    monkeypatch,
):
    now = datetime(
        2026, 9, 21, 12, 0,
        tzinfo=retriever.METEOGPT_TIMEZONE,
    )

    chunk = {
        "chunk_id": "test_peche_001",
        "category": "peche_artisanale",
        "content": "Conditions maritimes pour la pêche.",
        "date_publication": "2026-09-21T08:00:00+00:00",
        "date_debut_validite": "2026-09-21T08:00:00+00:00",
        "date_fin_validite": "2026-09-23T23:59:59+00:00",
    }

    monkeypatch.setattr(
        retriever, "BM25_CHUNKS", [chunk]
    )
    monkeypatch.setattr(
        retriever, "CATEGORIES_LOCALITE_STRUCTUREE", set()
    )

    contraintes = {
        "category": {
            "mode": "explicit",
            "categories": ["peche_artisanale"],
        }
    }

    resultat = retriever.selectionner_chunks_admissibles(
        query="Quelle est la houle demain ?",
        contraintes=contraintes,
        now=now,
    )

    effectives = resultat["constraints"]

    assert effectives["category"] == contraintes["category"]
    assert effectives["temporal"]["expression"] == "demain"
    assert effectives["location"]["mode"] == "general"

    assert resultat["chunk_ids"] == ["test_peche_001"]

    # Aucune mutation des contraintes de l'Agent.
    assert list(contraintes) == ["category"]
