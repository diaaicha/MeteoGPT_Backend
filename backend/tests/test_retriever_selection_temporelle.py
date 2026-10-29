
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import retriever


TZ = ZoneInfo("Africa/Dakar")
NOW = datetime(2026, 9, 21, 21, 30, tzinfo=TZ)


def chunk(identifiant, publication, debut, fin, categorie="meteo_72h"):
    return {
        "chunk_id": identifiant,
        "category": categorie,
        "date_publication": publication,
        "date_debut_validite": debut,
        "date_fin_validite": fin,
    }


def identifiants(chunks):
    return {c["chunk_id"] for c in chunks}


def test_publication_historique():
    documents = [
        chunk("17", "2026-09-17", "2026-09-17", "2026-09-20"),
        chunk("18", "2026-09-18", "2026-09-18", "2026-09-21"),
    ]

    temporalite = retriever.resoudre_temporalite(
        "bulletin 72 h du 17 septembre",
        now=NOW,
    )

    assert temporalite["mode"] == "publication"

    resultat = retriever.selectionner_chunks_temporels(
        documents, temporalite, NOW
    )

    assert identifiants(resultat) == {"17"}


def test_horizon_historique():
    documents = [
        chunk("17", "2026-09-17", "2026-09-17", "2026-09-20"),
        chunk("18", "2026-09-18", "2026-09-18", "2026-09-21"),
    ]

    temporalite = retriever.resoudre_temporalite(
        "trois jours suivant le 17 septembre",
        now=NOW,
    )

    resultat = retriever.selectionner_chunks_temporels(
        documents, temporalite, NOW
    )

    assert identifiants(resultat) == {"17"}


def test_meteo_courante_derniere_publication():
    documents = [
        chunk("ancien", "2026-09-20", "2026-09-20", "2026-09-23"),
        chunk("recent", "2026-09-21", "2026-09-21", "2026-09-23"),
        chunk(
            "marine", "2026-09-19",
            "2026-09-19", "2026-09-23",
            "marine_nationale"
        ),
    ]

    temporalite = retriever.resoudre_temporalite(
        "météo ajd",
        now=NOW,
    )

    resultat = retriever.selectionner_chunks_temporels(
        documents, temporalite, NOW
    )

    assert identifiants(resultat) == {"recent", "marine"}


def test_demain_choisit_la_derniere_publication_disponible():
    documents = [
        chunk("ancien", "2026-09-20", "2026-09-20", "2026-09-23"),
        chunk("recent", "2026-09-21", "2026-09-21", "2026-09-23"),
        chunk("futur", "2026-09-22", "2026-09-22", "2026-09-24"),
    ]

    temporalite = retriever.resoudre_temporalite(
        "météo dm",
        now=NOW,
    )

    resultat = retriever.selectionner_chunks_temporels(
        documents, temporalite, NOW
    )

    assert identifiants(resultat) == {"recent"}


def test_bulletin_publie_plus_tard_non_disponible():
    documents = [
        chunk(
            "futur_ce_soir",
            "2026-09-21T23:00:00",
            "2026-09-21",
            "2026-09-24",
        )
    ]

    temporalite = retriever.resoudre_temporalite(
        "météo ajd",
        now=NOW,
    )

    resultat = retriever.selectionner_chunks_temporels(
        documents, temporalite, NOW
    )

    assert resultat == []


def test_publication_demandee_absente():
    documents = [
        chunk("18", "2026-09-18", "2026-09-18", "2026-09-21")
    ]

    temporalite = retriever.resoudre_temporalite(
        "bulletin 72 h du 17 septembre",
        now=NOW,
    )

    resultat = retriever.selectionner_chunks_temporels(
        documents, temporalite, NOW
    )

    assert resultat == []


def test_publication_precise_absente_sans_fallback(monkeypatch):
    ancien = {
        "chunk_id": "bulletin_15",
        "category": "meteo_72h",
        "date_publication": "2026-09-15",
        "date_debut_validite": "2026-09-15",
        "date_fin_validite": "2026-09-16",
    }

    monkeypatch.setattr(
        retriever, "BM25_CHUNKS", [ancien]
    )

    resultat = retriever.selectionner_chunks_admissibles(
        query="bulletin 72 h du 17 septembre",
        now=NOW,
    )

    assert resultat["constraints"]["temporal"]["mode"] == "publication"
    assert resultat["chunk_ids"] == []
    assert resultat["data_status"] == "unavailable"
    assert resultat["fallback_used"] is False


def test_repli_expire_conserve_pour_demande_courante(monkeypatch):
    ancien = {
        "chunk_id": "bulletin_15",
        "category": "meteo_72h",
        "date_publication": "2026-09-15",
        "date_debut_validite": "2026-09-15",
        "date_fin_validite": "2026-09-16",
    }

    monkeypatch.setattr(
        retriever, "BM25_CHUNKS", [ancien]
    )

    resultat = retriever.selectionner_chunks_admissibles(
        query="prévisions des 72 prochaines heures",
        now=NOW,
    )

    assert resultat["chunk_ids"] == ["bulletin_15"]
    assert resultat["data_status"] == "stale"
    assert resultat["fallback_used"] is True


def test_fallback_expire_respecte_localite(monkeypatch):
    documents = [
        {
            "chunk_id": "saint_louis_expire",
            "category": "meteo_soir",
            "localite": "Saint-Louis",
            "date_publication": "2026-09-17",
            "date_debut_validite": "2026-09-17",
            "date_fin_validite": "2026-09-18T23:59:59",
        },
        {
            "chunk_id": "dakar_expire",
            "category": "meteo_soir",
            "localite": "Dakar",
            "date_publication": "2026-09-19",
            "date_debut_validite": "2026-09-19",
            "date_fin_validite": "2026-09-20T23:59:59",
        },
    ]

    monkeypatch.setattr(
        retriever, "BM25_CHUNKS", documents
    )

    monkeypatch.setattr(
        retriever,
        "CATEGORIES_LOCALITE_STRUCTUREE",
        {"meteo_soir"}
    )

    monkeypatch.setattr(
        retriever,
        "LOCALITES_CONNNUES",
        {
            "saint louis": "Saint-Louis",
            "dakar": "Dakar",
        }
    )

    resultat = retriever.selectionner_chunks_admissibles(
        query="météo pour Saint-Louis aujourd'hui",
        now=NOW,
    )

    assert resultat["chunk_ids"] == [
        "saint_louis_expire"
    ]

    assert resultat["data_status"] == "stale"
    assert resultat["fallback_used"] is True
