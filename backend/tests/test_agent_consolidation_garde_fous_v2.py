
import pytest
import agent


# Les regles de V2 ne doivent pas intercepter
# ces demandes avant la classification meteorologique.

@pytest.mark.parametrize(
    "question",
    [
        "Quels paramètres météo sont utilisés pour les prévisions ?",
        "Merci, je veux connaître la météo demain",
        "Comment fonctionne un algorithme de prévision ?",
        "J'utilise Python pour analyser les bulletins météo",
    ],
)
def test_interactions_non_interceptees(question):
    decision = agent.detecter_interaction_evidente(
        question
    )

    assert decision is None


@pytest.mark.parametrize(
    "question, intention",
    [
        (
            "Je veux modifier mes préférences météo",
            agent.INTENT_PERSONALIZATION,
        ),
        (
            "Tu sers à quoi ?",
            agent.INTENT_CAPABILITIES,
        ),
    ],
)
def test_interactions_existantes_preservees(
    question, intention
):
    decision = agent.detecter_interaction_evidente(
        question
    )

    assert decision is not None
    assert decision["intent"] == intention
    assert decision["route"] == agent.ROUTE_STATIC


# Verifier les seuils E5 sans appeler le modele.
# Ces tests protegent la decision existante.

@pytest.mark.parametrize(
    "score, margin",
    [
        (0.87, 0.10),
        (0.96, 0.01),
    ],
)
def test_e5_refuse_confiance_insuffisante(
    monkeypatch, score, margin
):
    monkeypatch.setattr(
        agent,
        "classifier_fallback_e5",
        lambda query: {
            "intent": agent.INTENT_METEO_GENERALE,
            "score": score,
            "margin": margin,
        },
    )

    decision = agent.classifier_requete_fallback(
        "Question météo ambiguë"
    )

    assert decision is None


@pytest.mark.parametrize(
    "intention, route",
    [
        (
            agent.INTENT_METEO_GENERALE,
            agent.ROUTE_RAG,
        ),
        (
            agent.INTENT_METEO_KNOWLEDGE,
            agent.ROUTE_DIRECT_LLM,
        ),
        (
            agent.INTENT_OUT_OF_SCOPE,
            agent.ROUTE_OUT_OF_SCOPE,
        ),
    ],
)
def test_e5_conserve_mapping_intention_route(
    monkeypatch, intention, route
):
    monkeypatch.setattr(
        agent,
        "classifier_fallback_e5",
        lambda query: {
            "intent": intention,
            "score": 0.92,
            "margin": 0.04,
        },
    )

    decision = agent.classifier_requete_fallback(
        "Requête de vérification"
    )

    assert decision is not None
    assert decision["intent"] == intention
    assert decision["route"] == route
    assert decision["needs_retrieval"] is (
        route == agent.ROUTE_RAG
    )
