
from datetime import datetime

import pytest
import agent
import retriever


NOW = datetime(
    2026, 9, 21, 12, 0,
    tzinfo=retriever.METEOGPT_TIMEZONE,
)


@pytest.mark.parametrize(
    "question, intention_attendue",
    [
        (
            "Pourquoi y avait-il de la pluie le 20 septembre 2026 ?",
            agent.INTENT_HISTORIQUE,
        ),
        (
            "Pourquoi le vent était-il fort le 20/09/2026 ?",
            agent.INTENT_HISTORIQUE,
        ),
        (
            "Pourquoi y avait-il des orages hier ?",
            agent.INTENT_HISTORIQUE,
        ),
        (
            "Pourquoi le vent est-il fort demain ?",
            agent.INTENT_METEO_GENERALE,
        ),
        (
            "Pourquoi y a-t-il des orages ce soir ?",
            agent.INTENT_METEO_GENERALE,
        ),
        (
            "Pourquoi la pluie se forme-t-elle ?",
            agent.INTENT_METEO_KNOWLEDGE,
        ),
        (
            "Pourquoi un anticyclone se forme-t-il ?",
            agent.INTENT_METEO_KNOWLEDGE,
        ),
        (
            "Pourquoi la pluie se forme-t-elle en septembre ?",
            agent.INTENT_METEO_KNOWLEDGE,
        ),
    ],
)
def test_distinction_temporelle_connaissance(
    question,
    intention_attendue,
):
    decision = agent.detecter_intention_meteo(
        question,
        now=NOW,
    )

    assert decision is not None
    assert decision["intent"] == intention_attendue

    if intention_attendue == agent.INTENT_METEO_KNOWLEDGE:
        assert decision["route"] == agent.ROUTE_DIRECT_LLM
        assert decision["needs_retrieval"] is False
    else:
        assert decision["route"] == agent.ROUTE_RAG
        assert decision["needs_retrieval"] is True


def test_resolution_temporelle_reutilisee(monkeypatch):
    fonction_originale = (
        agent.retriever.resoudre_temporalite
    )

    appels = []

    def observer(query, now=None):
        appels.append(query)
        return fonction_originale(query, now=now)

    monkeypatch.setattr(
        agent.retriever,
        "resoudre_temporalite",
        observer,
    )

    decision = agent.detecter_intention_meteo(
        "Pourquoi le vent était-il fort le 20 septembre 2026 ?",
        now=NOW,
    )

    assert decision["intent"] == agent.INTENT_HISTORIQUE
    assert len(appels) == 1
