
from datetime import datetime

import pytest
import agent
import retriever


NOW = datetime(
    2026, 9, 21, 12, 0,
    tzinfo=retriever.METEOGPT_TIMEZONE,
)


@pytest.mark.parametrize(
    "question",
    [
        "Pourquoi la mer est-elle agitée à Dakar aujourd'hui ?",
        "Pourquoi y a-t-il des orages ce soir ?",
        "Pourquoi le vent était-il fort hier ?",
    ],
)
def test_question_causale_datee_utilise_rag(question):
    decision = agent.detecter_intention_meteo(
        question,
        now=NOW,
    )

    assert decision is not None
    assert decision["route"] == agent.ROUTE_RAG
    assert decision["needs_retrieval"] is True


@pytest.mark.parametrize(
    "question",
    [
        "Pourquoi la pluie se forme-t-elle ?",
        "Comment se forme la houle ?",
        "Pourquoi la pression atmosphérique varie-t-elle ?",
    ],
)
def test_explication_generale_reste_direct_llm(question):
    decision = agent.detecter_intention_meteo(
        question,
        now=NOW,
    )

    assert decision is not None
    assert decision["intent"] == agent.INTENT_METEO_KNOWLEDGE
    assert decision["route"] == agent.ROUTE_DIRECT_LLM


def test_prevision_ordinaire_reste_rag():
    decision = agent.detecter_intention_meteo(
        "Quelle est la houle demain à Dakar ?",
        now=NOW,
    )

    assert decision is not None
    assert decision["route"] == agent.ROUTE_RAG
