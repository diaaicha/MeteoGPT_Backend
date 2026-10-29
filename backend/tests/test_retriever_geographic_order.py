
from datetime import datetime
from zoneinfo import ZoneInfo

import retriever as r


NOW = datetime(
    2026, 9, 19, 14, 0,
    tzinfo=ZoneInfo("Africa/Dakar")
)


def chunk(
    identifiant,
    categorie,
    localite,
    publication,
    fin_validite="2026-09-20T23:00:00",
):
    return {
        "chunk_id": identifiant,
        "category": categorie,
        "localite": localite,
        "date_publication": publication,
        "date_debut_validite": "2026-09-17T00:00:00",
        "date_fin_validite": fin_validite,
    }


def contraintes(localite, categories, mode="current"):
    return {
        "category": {
            "mode": "general",
            "categories": categories,
        },
        "location": {
            "mode": (
                "specific"
                if localite else "general"
            ),
            "localite": localite,
        },
        "temporal": {
            "mode": mode,
            "expression": "maintenant",
            "start": NOW,
            "end": NOW,
        },
    }


def preparer(monkeypatch, chunks):
    monkeypatch.setattr(r, "BM25_CHUNKS", chunks)
    monkeypatch.setattr(
        r,
        "CATEGORIES_LOCALITE_STRUCTUREE",
        {"meteo_matin", "meteo_soir"},
    )


def test_localite_prioritaire_sur_publication(monkeypatch):
    preparer(monkeypatch, [
        chunk(
            "saint_louis_18",
            "meteo_matin",
            "Saint-Louis",
            "2026-09-18T08:00:00",
        ),
        chunk(
            "dakar_19",
            "meteo_matin",
            "Dakar",
            "2026-09-19T08:00:00",
        ),
    ])

    resultat = r.selectionner_chunks_admissibles(
        "Météo à Saint-Louis",
        contraintes=contraintes(
            "Saint-Louis",
            ["meteo_matin"],
        ),
        now=NOW,
    )

    assert resultat["chunk_ids"] == [
        "saint_louis_18"
    ]
    assert resultat["data_status"] == "valid"
    assert resultat["fallback_used"] is False
    assert resultat["counts"]["after_geography"] == 1


def test_requete_generale_conserve_chunk_general(monkeypatch):
    preparer(monkeypatch, [
        chunk(
            "general_18",
            "meteo_matin",
            None,
            "2026-09-18T08:00:00",
        ),
        chunk(
            "dakar_19",
            "meteo_matin",
            "Dakar",
            "2026-09-19T08:00:00",
        ),
    ])

    resultat = r.selectionner_chunks_admissibles(
        "Météo générale",
        contraintes=contraintes(
            None,
            ["meteo_matin"],
        ),
        now=NOW,
    )

    assert resultat["chunk_ids"] == [
        "general_18"
    ]


def test_categorie_sans_localite_structuree(monkeypatch):
    preparer(monkeypatch, [
        chunk(
            "marine_18",
            "navigation_cotiere",
            None,
            "2026-09-18T08:00:00",
        ),
        chunk(
            "marine_19",
            "navigation_cotiere",
            None,
            "2026-09-19T08:00:00",
        ),
    ])

    resultat = r.selectionner_chunks_admissibles(
        "Navigation près de Saint-Louis",
        contraintes=contraintes(
            "Saint-Louis",
            ["navigation_cotiere"],
        ),
        now=NOW,
    )

    assert resultat["chunk_ids"] == [
        "marine_19"
    ]


def test_derniere_publication_meme_localite(monkeypatch):
    preparer(monkeypatch, [
        chunk(
            "saint_louis_18",
            "meteo_matin",
            "Saint-Louis",
            "2026-09-18T08:00:00",
        ),
        chunk(
            "saint_louis_19",
            "meteo_matin",
            "Saint-Louis",
            "2026-09-19T08:00:00",
        ),
    ])

    resultat = r.selectionner_chunks_admissibles(
        "Météo à Saint-Louis",
        contraintes=contraintes(
            "Saint-Louis",
            ["meteo_matin"],
        ),
        now=NOW,
    )

    assert resultat["chunk_ids"] == [
        "saint_louis_19"
    ]


def test_fallback_expire_conserve_localite(monkeypatch):
    preparer(monkeypatch, [
        chunk(
            "saint_louis_expire",
            "meteo_matin",
            "Saint-Louis",
            "2026-09-18T08:00:00",
            "2026-09-18T23:00:00",
        ),
        chunk(
            "dakar_valide",
            "meteo_matin",
            "Dakar",
            "2026-09-19T08:00:00",
        ),
    ])

    c = contraintes(
        "Saint-Louis",
        ["meteo_matin"],
    )
    c["category"]["mode"] = "explicit"

    resultat = r.selectionner_chunks_admissibles(
        "Bulletin du matin à Saint-Louis",
        contraintes=c,
        now=NOW,
    )

    assert resultat["chunk_ids"] == [
        "saint_louis_expire"
    ]
    assert resultat["data_status"] == "stale"
    assert resultat["fallback_used"] is True
