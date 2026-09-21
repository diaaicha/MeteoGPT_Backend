from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas.chat import ChatResponse
from backend.app.services import chat_service


client = TestClient(app)


# ============================================================
# 1. ROUTE CHAT — SUCCÈS
# ============================================================

def test_chat_success(
    monkeypatch
):
    """
    Vérifie qu'une requête Chat valide retourne HTTP 200
    sans appeler le pipeline RAG réel.
    """

    def fake_process_chat(
        *,
        query,
        thread_id=None,
        user_preferences=None,
    ):
        return ChatResponse(
            success=True,
            thread_id=(
                thread_id
                or "generated-thread"
            ),
            answer="Temps chaud à Dakar.",
            route="rag",
            intent="meteo_generale",
            generation_mode="rag_text",
            grounded=True,
            retrieval_executed=True,
            use_multimodal=False,
            sources=[],
            latency_ms=125.0,
            error=None,
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
                "Quel temps est prévu à Dakar ?",
            "thread_id":
                "test-thread-001",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert data["thread_id"] == "test-thread-001"
    assert data["answer"] == "Temps chaud à Dakar."
    assert data["route"] == "rag"
    assert data["intent"] == "meteo_generale"
    assert data["generation_mode"] == "rag_text"
    assert data["grounded"] is True
    assert data["retrieval_executed"] is True
    assert data["use_multimodal"] is False
    assert data["error"] is None


# ============================================================
# 2. THREAD_ID FACULTATIF
# ============================================================

def test_chat_without_thread_id(
    monkeypatch
):
    """
    Vérifie que l'endpoint accepte l'absence de thread_id.
    """

    def fake_process_chat(
        *,
        query,
        thread_id=None,
        user_preferences=None,
    ):
        return ChatResponse(
            success=True,
            thread_id="generated-thread",
            answer="Réponse test.",
            sources=[],
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
                "Quel temps fait-il ?",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["thread_id"] == "generated-thread"


# ============================================================
# 3. QUERY VIDE
# ============================================================

def test_chat_empty_query():
    """
    Une requête vide doit être rejetée par Pydantic.
    """

    response = client.post(
        "/api/v1/chat",
        json={
            "query": "",
        },
    )

    assert response.status_code == 422


# ============================================================
# 4. QUERY MANQUANTE
# ============================================================

def test_chat_missing_query():
    """
    Le champ query est obligatoire.
    """

    response = client.post(
        "/api/v1/chat",
        json={},
    )

    assert response.status_code == 422


# ============================================================
# 5. ERREUR DU SERVICE
# ============================================================

def test_chat_internal_error(
    monkeypatch
):
    """
    Une exception inattendue du service est convertie en HTTP 500.
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

    assert response.json() == {
        "detail": (
            "Une erreur interne est survenue "
            "pendant le traitement de la requête."
        )
    }


# ============================================================
# 6. SERVICE — PIPELINE MOCKÉ
# ============================================================

def test_chat_service_maps_pipeline_result(
    monkeypatch
):
    """
    Vérifie la transformation :
    sortie interne rag_pipeline
        →
    ChatResponse publique.

    Aucun appel réel à Gemini, E5 ou Qdrant.
    """

    def fake_pipeline(
        query,
        *,
        thread_id="default",
        user_preferences=None,
        top_k=5,
        now=None,
        generation_client=None,
    ):
        return {
            "success": True,
            "query": query,
            "route": "rag",
            "intent": "meteo_generale",
            "answer": "Il fera chaud à Dakar.",
            "generation_mode": "rag_text",
            "grounded": True,
            "retrieval_executed": True,
            "use_multimodal": False,
            "sources_used": [],
            "latencies_ms": {
                "agent": 10.0,
                "retrieval": 50.0,
                "generation": 100.0,
                "total": 160.0,
            },
            "error": None,
        }

    monkeypatch.setattr(
        chat_service,
        "_load_process_text_request",
        lambda: fake_pipeline,
    )

    result = chat_service.process_chat(
        query="Quel temps est prévu à Dakar ?",
        thread_id="service-test-thread",
    )

    assert isinstance(
        result,
        ChatResponse
    )

    assert result.success is True
    assert (
        result.thread_id
        == "service-test-thread"
    )
    assert (
        result.answer
        == "Il fera chaud à Dakar."
    )
    assert result.route == "rag"
    assert result.intent == "meteo_generale"
    assert result.grounded is True
    assert result.retrieval_executed is True
    assert result.latency_ms == 160.0
    assert result.error is None


# ============================================================
# 7. SERVICE — GÉNÉRATION AUTOMATIQUE THREAD_ID
# ============================================================

def test_chat_service_generates_thread_id(
    monkeypatch
):
    """
    Vérifie qu'un identifiant de conversation est généré
    lorsque le client n'en fournit pas.
    """

    captured = {}

    def fake_pipeline(
        query,
        *,
        thread_id="default",
        user_preferences=None,
        top_k=5,
        now=None,
        generation_client=None,
    ):
        captured["thread_id"] = thread_id

        return {
            "success": True,
            "answer": "Réponse.",
            "sources_used": [],
            "latencies_ms": {
                "total": 10.0,
            },
        }

    monkeypatch.setattr(
        chat_service,
        "_load_process_text_request",
        lambda: fake_pipeline,
    )

    result = chat_service.process_chat(
        query="Bonjour MeteoGPT",
    )

    assert result.thread_id
    assert (
        captured["thread_id"]
        == result.thread_id
    )
    assert (
        result.thread_id
        != "default"
    )


# ============================================================
# 8. SERVICE — TIMEOUT STRUCTURÉ DU PIPELINE
# ============================================================

def test_chat_service_pipeline_timeout(
    monkeypatch
):
    """
    Un timeout géré par le pipeline reste une réponse
    structurée et ne devient pas une exception Python.
    """

    def fake_pipeline(
        query,
        *,
        thread_id="default",
        user_preferences=None,
        top_k=5,
        now=None,
        generation_client=None,
    ):
        return {
            "success": False,
            "route": "rag",
            "intent": "meteo_generale",
            "answer": (
                "La génération de la réponse "
                "a pris trop de temps. "
                "Veuillez réessayer."
            ),
            "generation_mode": "rag_text",
            "grounded": False,
            "retrieval_executed": True,
            "use_multimodal": False,
            "sources_used": [],
            "latencies_ms": {
                "total": 30000.0,
            },
            "error": "timeout",
        }

    monkeypatch.setattr(
        chat_service,
        "_load_process_text_request",
        lambda: fake_pipeline,
    )

    result = chat_service.process_chat(
        query="Quel temps fait-il ?",
        thread_id="timeout-test",
    )

    assert result.success is False
    assert result.error == "timeout"
    assert result.grounded is False
    assert result.latency_ms == 30000.0


# ============================================================
# 9. SERVICE — NORMALISATION DES SOURCES
# ============================================================

def test_chat_service_normalizes_sources(
    monkeypatch
):
    """
    Vérifie que les sources internes du pipeline sont
    correctement transformées en sources publiques API.

    Le chemin image_path reste volontairement interne
    et n'est pas exposé dans ChatSource.
    """

    def fake_pipeline(
        query,
        *,
        thread_id="default",
        user_preferences=None,
        top_k=5,
        now=None,
        generation_client=None,
    ):
        return {
            "success": True,
            "route": "rag",
            "intent": "meteo_generale",
            "answer": "Temps chaud à Dakar.",
            "generation_mode": "rag_text",
            "grounded": True,
            "retrieval_executed": True,
            "use_multimodal": False,
            "sources_used": [
                {
                    "rank": 1,
                    "chunk_id": "chunk-001",
                    "chunk_type": "visual",
                    "source_file": "bulletin.pdf",
                    "category": "meteo_generale",
                    "page": 2,
                    "localite": "Dakar",
                    "date_publication": "2026-09-17",
                    "date_debut_validite":
                        "2026-09-17",
                    "date_fin_validite":
                        "2026-09-18",
                    "image_path":
                        (
                            "data/extracted/api/"
                            "visuals/test.png"
                        ),
                }
            ],
            "latencies_ms": {
                "total": 120.0,
            },
            "error": None,
        }

    monkeypatch.setattr(
        chat_service,
        "_load_process_text_request",
        lambda: fake_pipeline,
    )

    result = chat_service.process_chat(
        query="Quel temps est prévu à Dakar ?",
        thread_id="source-test",
    )

    assert len(result.sources) == 1

    source = result.sources[0]

    assert source.rank == 1
    assert source.chunk_id == "chunk-001"
    assert source.chunk_type == "visual"
    assert source.source_file == "bulletin.pdf"
    assert source.category == "meteo_generale"
    assert source.page == 2
    assert source.localite == "Dakar"
    assert (
        source.date_publication
        == "2026-09-17"
    )
    assert (
        source.date_debut_validite
        == "2026-09-17"
    )
    assert (
        source.date_fin_validite
        == "2026-09-18"
    )

    public_source = (
        source.model_dump()
    )

    assert "image_path" not in public_source