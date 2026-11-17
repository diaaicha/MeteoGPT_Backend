
import pytest
import agent


@pytest.mark.parametrize(
    "question",
    [
        "Qu'est-ce que tu peux faire ?",
        "Qu'est-ce que vous pouvez faire ?",
        "Tu sers à quoi ?",
        "Comment fonctionne ton service ?",
        "Comment ça marche ce service ?",
        "As-tu accès aux bulletins météo ?",
        "Avez-vous accès aux bulletins ?",
    ],
)
def test_nouvelles_capacites_v2(question):
    decision = agent.detecter_interaction_evidente(
        question
    )

    assert decision is not None
    assert decision["intent"] == agent.INTENT_CAPABILITIES
    assert decision["route"] == agent.ROUTE_STATIC
    assert decision["needs_retrieval"] is False


@pytest.mark.parametrize(
    "question",
    [
        "Comment fonctionne la houle ?",
        "Quels sont les paramètres météo demain ?",
        "As-tu accès aux bulletins météo pour Dakar demain ?",
        "Peux-tu me donner les prévisions demain ?",
        "Et la pêche demain ?",
    ],
)
def test_pas_interception_abusive(question):
    decision = agent.detecter_interaction_evidente(
        question
    )

    assert decision is None


@pytest.mark.parametrize(
    "question, intent",
    [
        ("Que peux-tu faire ?", agent.INTENT_CAPABILITIES),
        ("Bonjour !", agent.INTENT_GREETING),
        (
            "Je veux modifier mes préférences météo",
            agent.INTENT_PERSONALIZATION,
        ),
    ],
)
def test_comportements_historiques_preserves(
    question,
    intent,
):
    decision = agent.detecter_interaction_evidente(
        question
    )

    assert decision is not None
    assert decision["intent"] == intent
    assert decision["route"] == agent.ROUTE_STATIC
