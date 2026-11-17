
import pytest
import agent


def decision(intent, route):
    return agent.construire_decision_agent(
        query="requete de test",
        intent=intent,
        route=route,
        needs_retrieval=(route == agent.ROUTE_RAG),
    )


def etat(
    query="Et demain ?",
    effective_query=None,
    last_intent=None,
    context_used=False,
    needs_visual=False,
):
    return {
        "query": query,
        "effective_query": effective_query or query,
        "session_context": {
            "last_intent": last_intent,
        },
        "contextualisation": {
            "context_used": context_used,
        },
        "needs_visual": needs_visual,
    }


def simuler(
    monkeypatch,
    interaction=None,
    meteo=None,
    suivi=False,
    fallback=None,
):
    monkeypatch.setattr(
        agent,
        "detecter_interaction_evidente",
        lambda query: interaction,
    )
    monkeypatch.setattr(
        agent,
        "detecter_intention_meteo",
        lambda query: meteo,
    )
    monkeypatch.setattr(
        agent,
        "est_requete_de_suivi",
        lambda query: suivi,
    )
    monkeypatch.setattr(
        agent,
        "classifier_requete_fallback",
        lambda query: fallback,
    )


def test_interaction_evidente_prioritaire(monkeypatch):
    simuler(
        monkeypatch,
        interaction=decision(
            agent.INTENT_GREETING,
            agent.ROUTE_STATIC,
        ),
        meteo=decision(
            agent.INTENT_METEO_GENERALE,
            agent.ROUTE_RAG,
        ),
    )

    resultat = agent.node_classifier(
        etat(query="Bonjour !")
    )["decision"]

    assert resultat["intent"] == agent.INTENT_GREETING
    assert resultat["route"] == agent.ROUTE_STATIC


def test_nouvelle_intention_prime_sur_ancienne(monkeypatch):
    simuler(
        monkeypatch,
        meteo=decision(
            agent.INTENT_METEO_GENERALE,
            agent.ROUTE_RAG,
        ),
        suivi=True,
    )

    resultat = agent.node_classifier(
        etat(
            query="Et la pluie demain ?",
            last_intent=agent.INTENT_PECHE_ARTISANALE,
        )
    )["decision"]

    assert resultat["intent"] == agent.INTENT_METEO_GENERALE
    assert resultat["route"] == agent.ROUTE_RAG


def test_changement_explicite_vers_peche(monkeypatch):
    simuler(
        monkeypatch,
        meteo=decision(
            agent.INTENT_PECHE_ARTISANALE,
            agent.ROUTE_RAG,
        ),
        suivi=True,
    )

    resultat = agent.node_classifier(
        etat(
            query="Et pour la pêche artisanale ?",
            last_intent=agent.INTENT_NAVIGATION_COTIERE,
        )
    )["decision"]

    assert resultat["intent"] == agent.INTENT_PECHE_ARTISANALE


def test_heritage_si_aucune_nouvelle_intention(monkeypatch):
    simuler(monkeypatch, suivi=True)

    resultat = agent.node_classifier(
        etat(
            query="Et après-demain ?",
            last_intent=agent.INTENT_NAVIGATION_COTIERE,
        )
    )["decision"]

    assert resultat["intent"] == agent.INTENT_NAVIGATION_COTIERE
    assert resultat["route"] == agent.ROUTE_RAG
    assert resultat["context_used"] is True


def test_intention_non_heritable(monkeypatch):
    simuler(
        monkeypatch,
        suivi=True,
        fallback=decision(
            agent.INTENT_METEO_GENERALE,
            agent.ROUTE_RAG,
        ),
    )

    resultat = agent.node_classifier(
        etat(last_intent=agent.INTENT_GREETING)
    )["decision"]

    assert resultat["intent"] == agent.INTENT_METEO_GENERALE


def test_fallback_conserve_contextualisation(monkeypatch):
    simuler(
        monkeypatch,
        fallback=decision(
            agent.INTENT_METEO_KNOWLEDGE,
            agent.ROUTE_DIRECT_LLM,
        ),
    )

    resultat = agent.node_classifier(
        etat(
            query="Question explicative",
            context_used=True,
        )
    )["decision"]

    assert resultat["route"] == agent.ROUTE_DIRECT_LLM
    assert resultat["context_used"] is True


def test_aucune_decision_declenche_clarification(monkeypatch):
    simuler(monkeypatch)

    resultat = agent.node_classifier(
        etat(query="Demande indéterminée")
    )["decision"]

    assert resultat["route"] == agent.ROUTE_CLARIFY
    assert resultat["needs_clarification"] is True
    assert resultat["intent"] == agent.INTENT_UNKNOWN


def test_classifier_ne_modifie_pas_effective_query(monkeypatch):
    simuler(
        monkeypatch,
        meteo=decision(
            agent.INTENT_PECHE_ARTISANALE,
            agent.ROUTE_RAG,
        ),
    )

    requete_effective = (
        "Et après-demain pour la pêche artisanale ?"
    )

    state = etat(
        query="Et après-demain ?",
        effective_query=requete_effective,
        last_intent=agent.INTENT_PECHE_ARTISANALE,
        needs_visual=True,
    )

    sortie = agent.node_classifier(state)

    assert state["effective_query"] == requete_effective
    assert "effective_query" not in sortie
    assert sortie["decision"]["needs_visual"] is True
    assert sortie["decision"]["query"] == "Et après-demain ?"
