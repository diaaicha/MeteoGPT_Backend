

import os
from unittest.mock import patch

# Isole les variables d'environnement pendant l'importation.
# Le .env reste accessible aux modules qui en ont besoin,
# puis l'environnement initial est restaure.
with patch.dict(os.environ, os.environ.copy(), clear=True):
    import rag_pipeline



def preparer_pipeline_mock(monkeypatch, agent_result):
    appels_retriever = []

    monkeypatch.setattr(
        rag_pipeline.agent,
        "analyze_query",
        lambda **kwargs: agent_result,
    )

    def fake_retrieve(**kwargs):
        appels_retriever.append(kwargs)
        return {"results": []}

    monkeypatch.setattr(
        rag_pipeline.retriever,
        "retrieve",
        fake_retrieve,
    )

    monkeypatch.setattr(
        rag_pipeline.generation,
        "generate_response",
        lambda **kwargs: {
            "success": True,
            "answer": "Réponse de test",
            "generation_mode": "test",
            "grounded": False,
            "sources_used": [],
        },
    )

    return appels_retriever


def test_pipeline_conserve_appel_historique(monkeypatch):
    appels = preparer_pipeline_mock(
        monkeypatch,
        {
            "route": "rag",
            "intent": "meteo_generale",
            "effective_query": "météo",
        },
    )

    result = rag_pipeline.process_text_request(
        "météo",
        top_k=4,
    )

    assert result["success"] is True
    assert appels == [{
        "query": "météo",
        "top_k": 4,
        "now": None,
    }]


def test_pipeline_transmet_contraintes_agent(monkeypatch):
    contraintes = {
        "category": {
            "mode": "explicit",
            "categories": ["peche_artisanale"],
        },
        "location": {
            "mode": "general",
            "localite": None,
        },
        "temporal": {
            "mode": "current",
        },
    }

    appels = preparer_pipeline_mock(
        monkeypatch,
        {
            "route": "rag",
            "intent": "peche_artisanale",
            "effective_query": "conditions de pêche",
            "retrieval_constraints": contraintes,
        },
    )

    result = rag_pipeline.process_text_request(
        "conditions de pêche",
        top_k=4,
    )

    assert result["success"] is True
    assert len(appels) == 1
    assert appels[0]["contraintes"] is contraintes
    assert appels[0]["query"] == "conditions de pêche"
