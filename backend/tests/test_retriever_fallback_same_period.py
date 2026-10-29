
from datetime import datetime
from zoneinfo import ZoneInfo

import retriever as r


NOW = datetime(
    2026, 9, 21, 14, 0,
    tzinfo=ZoneInfo("Africa/Dakar"),
)


def chunk(
    identifiant,
    categorie,
    localite,
    publication="2026-09-21T08:00:00",
    fin="2026-09-21T23:00:00",
):
    return {
        "chunk_id": identifiant,
        "category": categorie,
        "localite": localite,
        "date_publication": publication,
        "date_debut_validite": "2026-09-20T00:00:00",
        "date_fin_validite": fin,
    }


def contraintes(localite):
    return {
        "category": {
            "mode": "general",
            "categories": ["meteo_matin"],
        },
        "location": {
            "mode": "specific" if localite else "general",
            "localite": localite,
        },
        "temporal": {
            "mode": "current",
            "expression": "maintenant",
            "start": NOW,
            "end": NOW,
        },
    }


def evaluer(monkeypatch, chunks, localite):
    monkeypatch.setattr(r, "BM25_CHUNKS", chunks)
    monkeypatch.setattr(
        r,
        "CATEGORIES_LOCALITE_STRUCTUREE",
        {"meteo_matin", "meteo_soir"},
    )

    return r.selectionner_chunks_admissibles(
        "Question météo",
        contraintes=contraintes(localite),
        now=NOW,
    )


def test_ne_retourne_pas_une_autre_ville(monkeypatch):
    resultat = evaluer(
        monkeypatch,
        [chunk("dakar", "meteo_soir", "Dakar")],
        "Saint-Louis",
    )

    assert resultat["chunk_ids"] == []
    assert resultat["data_status"] == "unavailable"


def test_selection_geographique_avant_fraicheur(monkeypatch):
    resultat = evaluer(
        monkeypatch,
        [
            chunk(
                "saint_louis",
                "meteo_soir",
                "Saint-Louis",
                publication="2026-09-20T08:00:00",
            ),
            chunk(
                "dakar",
                "meteo_soir",
                "Dakar",
            ),
        ],
        "Saint-Louis",
    )

    assert resultat["chunk_ids"] == ["saint_louis"]
    assert resultat["data_status"] == "alternative_same_date"


def test_demande_generale_autorise_repli_large(monkeypatch):
    resultat = evaluer(
        monkeypatch,
        [chunk("dakar", "meteo_soir", "Dakar")],
        None,
    )

    assert resultat["chunk_ids"] == ["dakar"]
    assert resultat["fallback_used"] is True


def test_categorie_non_structuree_reste_admissible(monkeypatch):
    resultat = evaluer(
        monkeypatch,
        [chunk("marine", "navigation_cotiere", None)],
        "Saint-Louis",
    )

    assert resultat["chunk_ids"] == ["marine"]
    assert resultat["data_status"] == "alternative_same_date"


def test_fallback_expire_preserve_la_localite(monkeypatch):
    resultat = evaluer(
        monkeypatch,
        [
            chunk(
                "saint_louis_expire",
                "meteo_matin",
                "Saint-Louis",
                publication="2026-09-20T08:00:00",
                fin="2026-09-20T23:00:00",
            ),
            chunk(
                "dakar_recent",
                "meteo_soir",
                "Dakar",
            ),
        ],
        "Saint-Louis",
    )

    assert resultat["chunk_ids"] == [
        "saint_louis_expire"
    ]
    assert resultat["data_status"] == "stale"
    assert resultat["fallback_used"] is True
