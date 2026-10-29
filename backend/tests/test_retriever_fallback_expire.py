
from datetime import date, datetime
from zoneinfo import ZoneInfo

import retriever as r


TZ = ZoneInfo("Africa/Dakar")
NOW = datetime(2026, 9, 21, 14, 0, tzinfo=TZ)


def chunk(identifiant, publication, fin):
    return {
        "chunk_id": identifiant,
        "date_publication": publication,
        "date_fin_validite": fin,
    }


def temporalite(cible=NOW, mode="current", cutoff=None):
    resultat = {
        "mode": mode,
        "start": cible,
        "end": cible,
    }

    if cutoff is not None:
        resultat["publication_cutoff"] = cutoff

    return resultat


def ids(chunks, periode):
    return [
        c["chunk_id"]
        for c in r.selectionner_chunks_fallback_expire(
            chunks,
            periode,
            NOW
        )
    ]


def test_exclut_publication_future():
    candidats = [
        chunk(
            "futur",
            "2026-09-22T08:00:00",
            "2026-09-20T23:00:00",
        ),
    ]

    assert ids(candidats, temporalite()) == []


def test_exclut_publication_posterieure_date_historique():
    cible = datetime(2026, 9, 17, tzinfo=TZ)

    candidats = [
        chunk(
            "publie_apres",
            "2026-09-18T08:00:00",
            "2026-09-16T23:00:00",
        ),
    ]

    assert ids(
        candidats,
        temporalite(cible, "explicit"),
    ) == []


def test_respecte_cutoff_historique():
    cible = datetime(2026, 9, 18, tzinfo=TZ)

    candidats = [
        chunk(
            "publication_tardive",
            "2026-09-18T08:00:00",
            "2026-09-17T23:00:00",
        ),
    ]

    assert ids(
        candidats,
        temporalite(
            cible,
            "duration",
            cutoff=date(2026, 9, 17),
        ),
    ) == []


def test_conserve_derniere_fin_validite():
    candidats = [
        chunk(
            "ancien",
            "2026-09-18T08:00:00",
            "2026-09-19T23:00:00",
        ),
        chunk(
            "recent",
            "2026-09-20T08:00:00",
            "2026-09-20T23:00:00",
        ),
    ]

    assert ids(
        candidats,
        temporalite(),
    ) == ["recent"]


def test_date_future_utilise_publication_deja_disponible():
    cible = datetime(2026, 9, 23, tzinfo=TZ)

    candidats = [
        chunk(
            "disponible",
            "2026-09-20T08:00:00",
            "2026-09-22T23:00:00",
        ),
        chunk(
            "pas_encore_publie",
            "2026-09-22T08:00:00",
            "2026-09-22T23:01:00",
        ),
    ]

    assert ids(
        candidats,
        temporalite(cible, "relative"),
    ) == ["disponible"]


def test_conserve_ex_aequo():
    candidats = [
        chunk(
            "a",
            "2026-09-20T08:00:00",
            "2026-09-20T23:00:00",
        ),
        chunk(
            "b",
            "2026-09-20T09:00:00",
            "2026-09-20T23:00:00",
        ),
    ]

    assert ids(
        candidats,
        temporalite(),
    ) == ["a", "b"]


def test_date_publication_inconnue():
    candidats = [
        chunk(
            "inconnu",
            None,
            "2026-09-20T23:00:00",
        ),
    ]

    assert ids(candidats, temporalite()) == []
