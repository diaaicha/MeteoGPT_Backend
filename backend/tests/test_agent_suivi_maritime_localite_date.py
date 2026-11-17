
import re
from uuid import uuid4

import pytest

import agent
import retriever


CONTEXTE = {
    "last_intent": agent.INTENT_METEO_GENERALE,
    "last_maritime_subject": "houle",
}


@pytest.fixture
def saint_louis_reconnue(monkeypatch):
    detection_originale = (
        retriever.detecter_localite_requete
    )

    def detecter(query):
        texte = agent.normaliser_requete_agent(query)

        if re.search(r"\bsaint louis\b", texte):
            return {
                "mode": "specific",
                "localite": "Saint-Louis",
            }

        return detection_originale(query)

    monkeypatch.setattr(
        retriever,
        "detecter_localite_requete",
        detecter,
    )


@pytest.mark.parametrize(
    "question",
    [
        "Et à Saint-Louis ?",
        "Et le 22 septembre 2026 ?",
        "Et le 22/09/2026 ?",
        "Et à Saint-Louis le 22 septembre 2026 ?",
    ],
)
def test_changement_lieu_date_conserve_houle(
    question,
    saint_louis_reconnue,
):
    resultat = agent.enrichir_requete_contexte(
        question,
        session_context=CONTEXTE,
    )

    assert "houle" in resultat["effective_query"]
    assert resultat["context_used"] is True

    assert (
        "session_maritime_subject"
        in resultat["context_sources"]
    )

    categories = retriever.detecter_categories_requete(
        resultat["effective_query"]
    )

    assert set(categories["categories"]) == {
        "navigation_cotiere",
        "marine_nationale",
    }


@pytest.mark.parametrize(
    "question",
    [
        "Et la pluie à Saint-Louis demain ?",
        "Et pour la pêche artisanale à Saint-Louis ?",
        "Et à Saint-Louis en parlant de pluie ?",
    ],
)
def test_nouveau_sujet_ne_reprend_pas_houle(
    question,
    saint_louis_reconnue,
):
    resultat = agent.enrichir_requete_contexte(
        question,
        session_context=CONTEXTE,
    )

    assert "houle" not in resultat["effective_query"]

    assert (
        "session_maritime_subject"
        not in resultat["context_sources"]
    )


def test_deux_tours_conservent_houle_avec_date():
    thread_id = str(uuid4())

    premier = agent.analyze_query(
        "Quelle est la houle demain ?",
        thread_id=thread_id,
    )

    second = agent.analyze_query(
        "Et le 22 septembre 2026 ?",
        thread_id=thread_id,
    )

    assert premier["route"] == agent.ROUTE_RAG
    assert second["route"] == agent.ROUTE_RAG

    assert second["context_used"] is True
    assert "houle" in second["effective_query"]

    categories = retriever.detecter_categories_requete(
        second["effective_query"]
    )

    assert set(categories["categories"]) == {
        "navigation_cotiere",
        "marine_nationale",
    }
