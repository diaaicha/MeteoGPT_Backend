
from datetime import datetime

import agent
import retriever


NOW = datetime(
    2026, 9, 21, 12,
    tzinfo=retriever.METEOGPT_TIMEZONE,
)



def test_houle_ambigue_ne_force_pas_navigation():
    question = "Quelle est la houle demain ?"

    decision = agent.detecter_intention_meteo(
        question,
        now=NOW,
    )

    assert decision is not None
    assert decision["route"] == agent.ROUTE_RAG
    assert decision["needs_retrieval"] is True

    assert decision["intent"] not in {
        agent.INTENT_NAVIGATION_COTIERE,
        agent.INTENT_MARINE_NATIONALE,
    }

    categories = retriever.detecter_categories_requete(
        question
    )

    assert set(categories["categories"]) == {
        "navigation_cotiere",
        "marine_nationale",
    }



def test_peche_avec_accents_valides():
    question = (
        "Houle pour la p\u00eache artisanale demain"
    )

    categories = retriever.detecter_categories_requete(
        question
    )

    assert categories["categories"] == [
        "peche_artisanale"
    ]

    decision = agent.detecter_intention_meteo(
        question,
        now=NOW,
    )

    assert decision["intent"] == (
        agent.INTENT_PECHE_ARTISANALE
    )


def test_etat_de_la_mer_est_maritime():
    question = (
        "Quel est l'\u00e9tat de la mer demain ?"
    )

    categories = retriever.detecter_categories_requete(
        question
    )

    assert set(categories["categories"]) == {
        "navigation_cotiere",
        "marine_nationale",
    }


def test_navigation_explicitement_demandee():
    question = (
        "Vent pour la navigation "
        "c\u00f4ti\u00e8re demain"
    )

    decision = agent.detecter_intention_meteo(
        question,
        now=NOW,
    )

    assert decision["intent"] == (
        agent.INTENT_NAVIGATION_COTIERE
    )


def test_houle_historique_reste_historique():
    decision = agent.detecter_intention_meteo(
        "Quelle \u00e9tait la houle hier ?",
        now=NOW,
    )

    assert decision["intent"] == (
        agent.INTENT_HISTORIQUE
    )


def test_explication_houle_reste_connaissance():
    decision = agent.detecter_intention_meteo(
        "Comment se forme la houle ?",
        now=NOW,
    )

    assert decision["intent"] == (
        agent.INTENT_METEO_KNOWLEDGE
    )

    assert decision["route"] == (
        agent.ROUTE_DIRECT_LLM
    )
