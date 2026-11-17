
import pytest
import agent


def test_suivi_conserve_indicateur_contexte(monkeypatch):
    monkeypatch.setattr(
        agent, "detecter_interaction_evidente",
        lambda query: None
    )
    monkeypatch.setattr(
        agent, "detecter_intention_meteo",
        lambda query: None
    )

    state = {
        "query": "Et demain ?",
        "effective_query": "Et demain ?",
        "session_context": {
            "last_intent": agent.INTENT_PECHE_ARTISANALE
        },
        "contextualisation": {
            "context_used": False
        },
    }

    decision = agent.node_classifier(state)["decision"]

    assert decision["intent"] == agent.INTENT_PECHE_ARTISANALE
    assert decision["route"] == agent.ROUTE_RAG
    assert decision["context_used"] is True


@pytest.mark.parametrize(
    "contextualisation_utilisee",
    [False, True]
)
def test_classification_conserve_contexte(
    monkeypatch,
    contextualisation_utilisee
):
    monkeypatch.setattr(
        agent,
        "detecter_interaction_evidente",
        lambda query: None
    )

    def classification_meteo(query):
        return agent.construire_decision_agent(
            query=query,
            route=agent.ROUTE_RAG,
            intent=agent.INTENT_METEO_GENERALE,
            needs_retrieval=True,
            context_used=False,
        )

    monkeypatch.setattr(
        agent,
        "detecter_intention_meteo",
        classification_meteo
    )

    state = {
        "query": "météo",
        "effective_query": "météo",
        "session_context": {},
        "contextualisation": {
            "context_used": contextualisation_utilisee
        },
    }

    decision = agent.node_classifier(state)["decision"]

    assert decision["intent"] == agent.INTENT_METEO_GENERALE
    assert decision["context_used"] is contextualisation_utilisee
