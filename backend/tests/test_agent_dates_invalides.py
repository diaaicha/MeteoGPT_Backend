
from datetime import datetime
from uuid import uuid4

import pytest

import agent
import retriever


@pytest.mark.parametrize(
    "question",
    [
        "Météo le 31/02/2026",
        "Vent le 31 février 2026",
    ],
)
def test_date_invalide_declenche_clarification(question):
    with pytest.raises(retriever.DateMeteoInvalide):
        retriever.resoudre_temporalite(question)

    resultat = agent.analyze_query(
        question,
        thread_id=str(uuid4()),
    )

    assert resultat["route"] == agent.ROUTE_CLARIFY
    assert resultat["intent"] == agent.INTENT_UNKNOWN
    assert resultat["needs_clarification"] is True
    assert resultat["needs_retrieval"] is False
    assert "date" in resultat["clarification_message"].lower()


def test_date_bissextile_valide():
    now = datetime(
        2026, 9, 21, 12,
        tzinfo=retriever.METEOGPT_TIMEZONE,
    )

    temporalite = retriever.resoudre_temporalite(
        "Houle le 29/02/2028",
        now=now,
    )

    assert temporalite["mode"] == "explicit"
    assert temporalite["start"].date().isoformat() == "2028-02-29"


def test_date_invalide_ne_remplace_pas_le_contexte():
    thread_id = str(uuid4())

    agent.analyze_query(
        "Quelle est la houle demain ?",
        thread_id=thread_id,
    )

    erreur = agent.analyze_query(
        "Et le 31/02/2026 ?",
        thread_id=thread_id,
    )

    suivi = agent.analyze_query(
        "Et après-demain ?",
        thread_id=thread_id,
    )

    assert erreur["route"] == agent.ROUTE_CLARIFY
    assert suivi["route"] == agent.ROUTE_RAG
    assert "houle" in suivi["effective_query"]
