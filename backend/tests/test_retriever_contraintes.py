
import retriever


def test_retrieve_ancien_appel_reste_compatible(monkeypatch):
    appels = []

    def fake_hybrid(*, query, top_k, now):
        appels.append((query, top_k, now))
        return {"ok": True}

    monkeypatch.setattr(
        retriever,
        "hybrid_metadata_retrieve",
        fake_hybrid
    )

    result = retriever.retrieve(
        "requete de test",
        top_k=3
    )

    assert result == {"ok": True}
    assert appels == [("requete de test", 3, None)]


def test_retrieve_transmet_les_contraintes(monkeypatch):
    contraintes = {
        "temporal": {"mode": "current"},
        "location": {"mode": "general"},
        "category": {
            "mode": "general",
            "categories": ["meteo_matin", "meteo_soir", "meteo_72h"]
        }
    }

    def fake_hybrid(*, query, top_k, now, contraintes):
        return {"contraintes_recues": contraintes}

    monkeypatch.setattr(
        retriever,
        "hybrid_metadata_retrieve",
        fake_hybrid
    )

    result = retriever.retrieve(
        "requete de test",
        contraintes=contraintes
    )

    assert result["contraintes_recues"] is contraintes


def test_hybrid_transmet_les_contraintes_au_filtrage(monkeypatch):
    contraintes = {
        "temporal": {"mode": "current"},
        "location": {"mode": "general"},
        "category": {
            "mode": "explicit",
            "categories": ["peche_artisanale"]
        }
    }

    appels = []

    def fake_selection(*, query, contraintes, now):
        appels.append(contraintes)
        return {
            "chunk_ids": [],
            "constraints": contraintes,
            "data_status": "unavailable",
            "fallback_used": False,
            "latest_available_until": None,
            "counts": {"initial": 0, "final": 0}
        }

    monkeypatch.setattr(
        retriever,
        "_ensure_initialized",
        lambda: None
    )

    monkeypatch.setattr(
        retriever,
        "selectionner_chunks_admissibles",
        fake_selection
    )

    result = retriever.hybrid_metadata_retrieve(
        "requete de test",
        contraintes=contraintes
    )

    assert appels == [contraintes]
    assert result["constraints"] is contraintes
    assert result["results"] == []
