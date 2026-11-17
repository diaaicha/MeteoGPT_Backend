
import os
from uuid import uuid4
from unittest.mock import patch

# Eviter que l'import du pipeline modifie
# l'environnement des autres tests.
with patch.dict(os.environ, os.environ.copy(), clear=True):
    os.environ.setdefault(
        "GEMINI_API_KEY",
        "test-no-network",
    )
    import rag_pipeline

import agent
import retriever


def preparer_pipeline(monkeypatch):
    appels = []

    def faux_retriever(*args, **kwargs):
        appels.append(dict(kwargs))
        return {
            "results": [],
            "data_status": "unavailable",
        }

    def fausse_generation(
        agent_result,
        retrieval_result=None,
        client=None,
    ):
        return {
            "success": True,
            "answer": "Réponse simulée",
            "generation_mode": "rag_text",
            "grounded": False,
        }

    monkeypatch.setattr(
        rag_pipeline.retriever,
        "retrieve",
        faux_retriever,
    )
    monkeypatch.setattr(
        rag_pipeline.generation,
        "generate_response",
        fausse_generation,
    )

    return appels


def test_houle_ambigue_transmise_au_retriever(monkeypatch):
    appels = preparer_pipeline(monkeypatch)

    resultat = rag_pipeline.process_text_request(
        "Quelle est la houle demain ?",
        thread_id=str(uuid4()),
    )

    assert resultat["route"] == agent.ROUTE_RAG
    assert resultat["retrieval_executed"] is True
    assert len(appels) == 1

    requete_transmise = appels[0]["query"]

    assert "houle" in requete_transmise.lower()

    categories = retriever.detecter_categories_requete(
        requete_transmise
    )

    assert set(categories["categories"]) == {
        "navigation_cotiere",
        "marine_nationale",
    }


def test_suivi_houle_transmis_au_retriever(monkeypatch):
    appels = preparer_pipeline(monkeypatch)
    thread_id = str(uuid4())

    rag_pipeline.process_text_request(
        "Quelle est la houle demain ?",
        thread_id=thread_id,
    )

    resultat = rag_pipeline.process_text_request(
        "Et après-demain ?",
        thread_id=thread_id,
    )

    assert resultat["route"] == agent.ROUTE_RAG
    assert resultat["context_used"] is True
    assert len(appels) == 2

    requete_transmise = appels[1]["query"]

    assert "houle" in requete_transmise.lower()
    assert requete_transmise == resultat["effective_query"]


def test_contraintes_structurees_transmises(monkeypatch):
    appels = preparer_pipeline(monkeypatch)

    contraintes = {
        "category": {
            "mode": "explicit",
            "categories": ["peche_artisanale"],
        },
    }

    def faux_agent(**kwargs):
        return {
            "query": kwargs["query"],
            "effective_query": kwargs["query"],
            "route": agent.ROUTE_RAG,
            "intent": agent.INTENT_PECHE_ARTISANALE,
            "needs_retrieval": True,
            "retrieval_constraints": contraintes,
        }

    monkeypatch.setattr(
        rag_pipeline.agent,
        "analyze_query",
        faux_agent,
    )

    rag_pipeline.process_text_request(
        "Houle pour la pêche artisanale demain",
        thread_id=str(uuid4()),
    )

    assert len(appels) == 1
    assert appels[0]["contraintes"] == contraintes


def test_route_non_rag_ne_lance_pas_retriever(monkeypatch):
    appels = preparer_pipeline(monkeypatch)

    def faux_agent(**kwargs):
        return {
            "query": kwargs["query"],
            "effective_query": kwargs["query"],
            "route": agent.ROUTE_STATIC,
            "intent": agent.INTENT_GREETING,
            "needs_retrieval": False,
        }

    monkeypatch.setattr(
        rag_pipeline.agent,
        "analyze_query",
        faux_agent,
    )

    resultat = rag_pipeline.process_text_request(
        "Bonjour",
        thread_id=str(uuid4()),
    )

    assert resultat["route"] == agent.ROUTE_STATIC
    assert resultat["retrieval_executed"] is False
    assert appels == []
