
from datetime import datetime

import pytest
import agent
import retriever


NOW = datetime(
    2026, 9, 21, 12, 0,
    tzinfo=retriever.METEOGPT_TIMEZONE,
)


@pytest.mark.parametrize(
    "query",
    [
        "Pourquoi la pluie se forme-t-elle ?",
        "Qu'est-ce que la pluie ?",
        "D'où viennent les pluies ?",
        "Quelle est l'origine des averses ?",
    ],
)
def test_questions_explicatives_sans_retrieval(query):
    decision = agent.detecter_intention_meteo(
        query,
        now=NOW,
    )

    assert decision is not None
    assert decision["intent"] == agent.INTENT_METEO_KNOWLEDGE
    assert decision["route"] == agent.ROUTE_DIRECT_LLM
    assert decision["needs_retrieval"] is False


@pytest.mark.parametrize(
    "query",
    [
        "Va-t-il pleuvoir demain à Dakar ?",
        "Pluie à Dakar demain",
        "Orages et averses demain",
       
    ],
)
def test_previsions_restent_dans_le_rag(query):
    decision = agent.detecter_intention_meteo(
        query,
        now=NOW,
    )

    assert decision is not None

    assert decision["intent"] in {
        agent.INTENT_METEO_GENERALE,
        agent.INTENT_METEO_LOCALE,
    }

    assert decision["route"] == agent.ROUTE_RAG
    assert decision["needs_retrieval"] is True
