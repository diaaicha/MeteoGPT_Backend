
import pytest
import agent


@pytest.mark.parametrize(
    "question",
    [
        "C'est quoi un thalweg ?",
        "Explique-moi le crachin",
        "Que signifie haboob ?",
        "Pourquoi une surcote se produit-elle ?",
    ],
)
def test_connaissances_nouveaux_concepts(question):
    decision = agent.detecter_intention_meteo(
        question
    )

    assert decision is not None
    assert decision["intent"] == agent.INTENT_METEO_KNOWLEDGE
    assert decision["route"] == agent.ROUTE_DIRECT_LLM
    assert decision["needs_retrieval"] is False


@pytest.mark.parametrize(
    "question",
    [
        "Houle demain à Dakar ?",
        "Conditions de pêche demain",
    ],
)
def test_previsions_conservent_route_rag(question):
    decision = agent.detecter_intention_meteo(
        question
    )

    assert decision is not None
    assert decision["route"] == agent.ROUTE_RAG
    assert decision["needs_retrieval"] is True


def test_concept_seul_ne_force_pas_direct_llm():
    decision = agent.detecter_intention_meteo(
        "Surcote demain ?",
    )

    assert (
        decision is None
        or decision["route"] != agent.ROUTE_DIRECT_LLM
    )