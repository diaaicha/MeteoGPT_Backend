
import agent


def mettre_a_jour(question, intention, precedent=None):
    return agent.mettre_a_jour_contexte_session(
        session_context=precedent or {},
        contextualisation={
            "query": question,
            "effective_query": question,
        },
        decision={
            "route": agent.ROUTE_RAG,
            "intent": intention,
        },
    )


def test_memorise_houle_sans_domaine_impose():
    contexte = mettre_a_jour(
        "Quelle est la houle demain ?",
        agent.INTENT_METEO_GENERALE,
    )

    assert contexte["last_maritime_subject"] == "houle"
    assert contexte["last_intent"] == (
        agent.INTENT_METEO_GENERALE
    )


def test_peche_explicite_ne_devient_pas_ambigue():
    contexte = mettre_a_jour(
        "Houle pour la pêche artisanale demain ?",
        agent.INTENT_PECHE_ARTISANALE,
    )

    assert "last_maritime_subject" not in contexte
    assert contexte["last_intent"] == (
        agent.INTENT_PECHE_ARTISANALE
    )


def test_nouveau_sujet_efface_ancien_sujet():
    contexte = mettre_a_jour(
        "Va-t-il pleuvoir demain ?",
        agent.INTENT_METEO_GENERALE,
        {"last_maritime_subject": "houle"},
    )

    assert "last_maritime_subject" not in contexte


def test_connaissance_ne_conserve_pas_sujet_precedent():
    contexte = agent.mettre_a_jour_contexte_session(
        session_context={
            "last_maritime_subject": "houle"
        },
        contextualisation={
            "query": "Comment se forme la houle ?",
            "effective_query": "Comment se forme la houle ?",
        },
        decision={
            "route": agent.ROUTE_DIRECT_LLM,
            "intent": agent.INTENT_METEO_KNOWLEDGE,
        },
    )

    assert "last_maritime_subject" not in contexte
