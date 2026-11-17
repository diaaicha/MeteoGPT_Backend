
import pytest

import agent


@pytest.fixture
def sans_localite(monkeypatch):
    monkeypatch.setattr(
        agent.retriever,
        "detecter_localite_requete",
        lambda query: {
            "mode": "general",
            "localite": None,
        },
    )


@pytest.mark.parametrize(
    "intention, question, categorie",
    [
        (
            agent.INTENT_PECHE_ARTISANALE,
            "Et demain ?",
            "peche_artisanale",
        ),
        (
            agent.INTENT_NAVIGATION_COTIERE,
            "Et le vent ?",
            "navigation_cotiere",
        ),
        (
            agent.INTENT_MARINE_NATIONALE,
            "Et la houle ?",
            "marine_nationale",
        ),
    ],
)
def test_suivi_conserve_categorie_maritime(
    sans_localite,
    intention,
    question,
    categorie,
):
    resultat = agent.enrichir_requete_contexte(
        query=question,
        session_context={
            "last_intent": intention,
        },
    )

    classification = (
        agent.retriever.detecter_categories_requete(
            resultat["effective_query"]
        )
    )

    assert classification["categories"] == [categorie]
    assert resultat["context_used"] is True
    assert "session_intent" in resultat["context_sources"]


def test_changement_explicite_vers_peche(sans_localite):
    resultat = agent.enrichir_requete_contexte(
        query="Et la pêche artisanale ?",
        session_context={
            "last_intent": agent.INTENT_NAVIGATION_COTIERE,
        },
    )

    assert (
        resultat["effective_query"]
        == "Et la pêche artisanale ?"
    )


def test_changement_explicite_vers_meteo(sans_localite):
    resultat = agent.enrichir_requete_contexte(
        query="Et la météo ?",
        session_context={
            "last_intent": agent.INTENT_PECHE_ARTISANALE,
        },
    )

    assert resultat["effective_query"] == "Et la météo ?"


def test_absence_contexte_ne_force_pas_domaine(
    sans_localite,
):
    resultat = agent.enrichir_requete_contexte(
        query="Et demain ?",
        session_context={},
    )

    assert resultat["effective_query"] == "Et demain ?"
    assert "session_intent" not in resultat["context_sources"]


def test_suivi_non_meteo_ne_force_pas_domaine(
    sans_localite,
):
    resultat = agent.enrichir_requete_contexte(
        query="Et le prix du carburant ?",
        session_context={
            "last_intent": agent.INTENT_PECHE_ARTISANALE,
        },
    )

    assert (
        resultat["effective_query"]
        == "Et le prix du carburant ?"
    )
