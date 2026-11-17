
from uuid import uuid4

import pytest

import agent
import retriever


CONTEXTE = {
    "last_intent": agent.INTENT_METEO_GENERALE,
    "last_maritime_subject": "houle",
}


@pytest.mark.parametrize(
    "question",
    [
        "Et demain ?",
        "Et après-demain ?",
        "Et ce soir ?",
    ],
)
def test_suivi_temporel_conserve_houle(question):
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


def test_nouveau_phenomene_ne_reprend_pas_houle():
    resultat = agent.enrichir_requete_contexte(
        "Et la pluie demain ?",
        session_context=CONTEXTE,
    )

    assert "houle" not in resultat["effective_query"]


def test_domaine_explicite_prioritaire():
    resultat = agent.enrichir_requete_contexte(
        "Et pour la pêche artisanale demain ?",
        session_context=CONTEXTE,
    )

    assert "houle" not in resultat["effective_query"]

    categories = retriever.detecter_categories_requete(
        resultat["effective_query"]
    )

    assert categories["categories"] == [
        "peche_artisanale"
    ]


def test_absence_de_memoire_ne_reinvente_pas_sujet():
    resultat = agent.enrichir_requete_contexte(
        "Et après-demain ?",
        session_context={
            "last_intent": agent.INTENT_METEO_GENERALE,
        },
    )

    assert "houle" not in resultat["effective_query"]


def test_localite_memorisee_et_sujet_conserves():
    resultat = agent.enrichir_requete_contexte(
        "Et demain ?",
        session_context={
            **CONTEXTE,
            "last_location": "Dakar",
        },
    )

    assert "Dakar" in resultat["effective_query"]
    assert "houle" in resultat["effective_query"]


def test_deux_tours_conservent_categories_maritimes():
    thread_id = str(uuid4())

    premier = agent.analyze_query(
        "Quelle est la houle demain ?",
        thread_id=thread_id,
    )

    second = agent.analyze_query(
        "Et après-demain ?",
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
