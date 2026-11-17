
import pytest

import agent


@pytest.mark.parametrize(
    "question",
    [
        "Bonjour 👋",
        "bjr",
        "slt",
        "salaam",
        "salam alaykoum",
        "assalamou alaikum",
        "coucou tu es la",
    ],
)
def test_nouvelles_salutations_v2(question):
    decision = agent.detecter_interaction_evidente(
        question
    )

    assert decision is not None
    assert decision["intent"] == agent.INTENT_GREETING
    assert decision["route"] == agent.ROUTE_STATIC
    assert decision["needs_retrieval"] is False


def test_salutation_historique_preservee():
    decision = agent.detecter_interaction_evidente(
        "Bonjour !"
    )

    assert decision is not None
    assert decision["intent"] == agent.INTENT_GREETING


@pytest.mark.parametrize(
    "question",
    [
        "Bonjour, météo demain ?",
        "bjr pluie demain",
        "slt météo aujourd'hui",
    ],
)
def test_salutation_avec_demande_meteo_non_interceptee(
    question,
):
    decision = agent.detecter_interaction_evidente(
        question
    )

    assert decision is None
