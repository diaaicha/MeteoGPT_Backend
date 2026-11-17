
import pytest
import agent


@pytest.mark.parametrize(
    "question",
    [
        "Quelle sera la météo là-bas ?",
        "Quel temps dans cette zone ?",
        "La météo à cet endroit demain ?",
        "Quel temps pour eux ?",
    ],
)
def test_reference_geographique_sans_contexte(question):
    resultat = agent.detecter_besoin_clarification(
        question
    )

    assert resultat["needs_clarification"] is True
    assert resultat["clarification_message"]


@pytest.mark.parametrize(
    "session, preferences",
    [
        ({"last_location": "Dakar"}, {}),
        (
            {"last_intent": agent.INTENT_NAVIGATION_COTIERE},
            {},
        ),
        ({}, {"preferred_location": "Saint-Louis"}),
    ],
)
def test_reference_avec_contexte(
    session,
    preferences,
):
    resultat = agent.detecter_besoin_clarification(
        "Quel temps là-bas ?",
        session_context=session,
        user_preferences=preferences,
    )

    assert resultat["needs_clarification"] is False


@pytest.mark.parametrize(
    "question",
    [
        "Cette chose ?",
        "Est-ce prêt maintenant ?",
        "Tu peux faire ça ?",
    ],
)
def test_pas_de_clarification_geographique_abusive(
    question,
):
    resultat = agent.detecter_besoin_clarification(
        question
    )

    assert resultat["needs_clarification"] is False


def test_cas_special_interrompt_classification():
    state = {
        "query": "Quel temps là-bas ?",
        "effective_query": "Quel temps là-bas ?",
        "session_context": {},
        "contextualisation": {
            "context_used": False,
        },
    }

    sortie = agent.node_analyser_cas_speciaux(state)
    decision = sortie["decision"]

    assert decision["route"] == agent.ROUTE_CLARIFY
    assert decision["needs_clarification"] is True
    assert decision["needs_retrieval"] is False

    assert agent.route_apres_cas_speciaux(
        {"decision": decision}
    ) == "finaliser"


def test_absence_ambiguite_autorise_classification():
    state = {
        "query": "Quel temps là-bas ?",
        "effective_query": "Quel temps là-bas ?",
        "session_context": {
            "last_location": "Dakar",
        },
        "contextualisation": {
            "context_used": True,
        },
    }

    sortie = agent.node_analyser_cas_speciaux(state)

    assert sortie["decision"] is None

    assert agent.route_apres_cas_speciaux(
        {"decision": None}
    ) == "classifier"


def test_finalisation_preserve_intention_precedente():
    contexte_initial = {
        "last_location": "Dakar",
        "last_intent": agent.INTENT_PECHE_ARTISANALE,
    }

    state = {
        "session_context": contexte_initial,
        "contextualisation": {
            "query": "Bonjour !",
            "effective_query": "Bonjour !",
        },
        "decision": {
            "route": agent.ROUTE_STATIC,
            "intent": agent.INTENT_GREETING,
        },
    }

    sortie = agent.node_finaliser(state)
    contexte_final = sortie["session_context"]

    assert contexte_final["last_location"] == "Dakar"
    assert contexte_final["last_intent"] == (
        agent.INTENT_PECHE_ARTISANALE
    )

    # La session d'entree ne doit pas etre modifiee.
    assert contexte_initial == {
        "last_location": "Dakar",
        "last_intent": agent.INTENT_PECHE_ARTISANALE,
    }
