from uuid import UUID

from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


# ============================================================
# 1. REQUEST_ID PRÉSENT
# ============================================================

def test_request_id_header_present():
    """
    Chaque requête HTTP doit recevoir un request_id.
    """

    response = client.get(
        "/health"
    )

    assert response.status_code == 200

    request_id = response.headers.get(
        "X-Request-ID"
    )

    assert request_id is not None

    # Vérifie qu'il s'agit bien d'un UUID valide.
    UUID(request_id)


# ============================================================
# 2. REQUEST_ID UNIQUE
# ============================================================

def test_request_id_is_unique():
    """
    Deux requêtes distinctes doivent recevoir
    deux request_id différents.
    """

    response_1 = client.get(
        "/health"
    )

    response_2 = client.get(
        "/health"
    )

    request_id_1 = response_1.headers.get(
        "X-Request-ID"
    )

    request_id_2 = response_2.headers.get(
        "X-Request-ID"
    )

    assert request_id_1
    assert request_id_2

    assert (
        request_id_1
        != request_id_2
    )


# ============================================================
# 3. REQUEST_ID SUR ERREUR DE VALIDATION
# ============================================================

def test_request_id_present_on_validation_error():
    """
    Le request_id doit également être présent
    lorsque FastAPI retourne une erreur 422.
    """

    response = client.post(
        "/api/v1/chat",
        json={
            "query": "",
        },
    )

    assert response.status_code == 422

    request_id = response.headers.get(
        "X-Request-ID"
    )

    assert request_id is not None

    UUID(request_id)


# ============================================================
# 4. REQUEST_ID SUR ERREUR INTERNE
# ============================================================

def test_request_id_present_on_internal_error(
    monkeypatch
):
    """
    Même une erreur interne HTTP 500 doit conserver
    l'identifiant de requête.
    """

    def fake_process_chat(
        *,
        query,
        thread_id=None,
        user_preferences=None,
    ):
        raise RuntimeError(
            "Erreur simulée."
        )

    monkeypatch.setattr(
        "backend.app.api.routes.chat."
        "chat_service.process_chat",
        fake_process_chat,
    )

    response = client.post(
        "/api/v1/chat",
        json={
            "query":
                "Quel temps fait-il à Dakar ?",
        },
    )

    assert response.status_code == 500

    request_id = response.headers.get(
        "X-Request-ID"
    )

    assert request_id is not None

    UUID(request_id)