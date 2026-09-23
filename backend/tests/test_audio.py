from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.api.routes import audio
from backend.app.schemas.audio import (
    AudioTranscriptionResponse,
)


client = TestClient(app)


def test_audio_transcribe_success(
    monkeypatch,
):
    def fake_transcribe_audio_file(
        *,
        audio_path,
        speech_client=None,
    ):
        assert audio_path.exists()

        return AudioTranscriptionResponse(
            success=True,
            transcription=(
                "Quel temps fait-il à Dakar ?"
            ),
            model="test-stt-model",
            mime_type="audio/wav",
            latency_ms=42.0,
            error=None,
        )

    monkeypatch.setattr(
        audio.audio_service,
        "transcribe_audio_file",
        fake_transcribe_audio_file,
    )

    response = client.post(
        "/api/v1/audio/transcribe",
        files={
            "file": (
                "question.wav",
                b"fake-audio-content",
                "audio/wav",
            )
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True

    assert (
        body["transcription"]
        == "Quel temps fait-il à Dakar ?"
    )

    assert (
        body["model"]
        == "test-stt-model"
    )

    assert (
        body["mime_type"]
        == "audio/wav"
    )

    assert body["latency_ms"] == 42.0

    assert body["error"] is None


def test_audio_transcribe_empty_file():
    response = client.post(
        "/api/v1/audio/transcribe",
        files={
            "file": (
                "empty.wav",
                b"",
                "audio/wav",
            )
        },
    )

    assert response.status_code == 400

    assert (
        response.json()["detail"]
        == "Le fichier audio est vide."
    )


def test_audio_transcribe_disabled(
    monkeypatch,
):
    monkeypatch.setattr(
        audio,
        "get_settings",
        lambda: SimpleNamespace(
            enable_speech=False
        ),
    )

    response = client.post(
        "/api/v1/audio/transcribe",
        files={
            "file": (
                "question.wav",
                b"fake-audio-content",
                "audio/wav",
            )
        },
    )

    assert response.status_code == 503

    assert (
        response.json()["detail"]
        == "Le service audio est désactivé."
    )




def test_audio_chat_success(
    monkeypatch,
):
    def fake_process_audio_chat(
        *,
        audio_path,
        output_mode,
        thread_id=None,
        user_preferences=None,
        generation_client=None,
        speech_client=None,
        audio_output_path=None,
    ):
        assert audio_path.exists()
        assert output_mode == "text"

        return {
            "success": True,
            "thread_id": thread_id or "test-thread",
            "status": "ok",
            "output_mode": "text",
            "transcription": (
                "Quel temps fera-t-il demain à Dakar ?"
            ),
            "answer": (
                "Demain à Dakar, les conditions prévues sont..."
            ),
            "route": "weather",
            "intent": "forecast",
            "generation_mode": "rag",
            "grounded": True,
            "retrieval_executed": True,
            "use_multimodal": False,
            "sources": [],
            "audio_available": False,
            "audio_url": None,
            "latencies_ms": {
                "stt": 100.0,
                "pipeline": 200.0,
                "tts": 0.0,
                "total": 300.0,
            },
            "error": None,
        }

    monkeypatch.setattr(
        audio.audio_service,
        "process_audio_chat",
        fake_process_audio_chat,
    )

    response = client.post(
        "/api/v1/audio/chat",
        files={
            "file": (
                "question.wav",
                b"fake-audio-content",
                "audio/wav",
            )
        },
        data={
            "thread_id": "test-thread",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True
    assert body["thread_id"] == "test-thread"
    assert body["output_mode"] == "text"

    assert (
        body["transcription"]
        == "Quel temps fera-t-il demain à Dakar ?"
    )

    assert body["grounded"] is True
    assert body["retrieval_executed"] is True
    assert body["audio_available"] is False
    assert body["error"] is None


def test_audio_chat_empty_file():
    response = client.post(
        "/api/v1/audio/chat",
        files={
            "file": (
                "empty.wav",
                b"",
                "audio/wav",
            )
        },
    )

    assert response.status_code == 400

    assert (
        response.json()["detail"]
        == "Le fichier audio est vide."
    )


def test_audio_chat_disabled(
    monkeypatch,
):
    monkeypatch.setattr(
        audio,
        "get_settings",
        lambda: SimpleNamespace(
            enable_speech=False
        ),
    )

    response = client.post(
        "/api/v1/audio/chat",
        files={
            "file": (
                "question.wav",
                b"fake-audio-content",
                "audio/wav",
            )
        },
    )

    assert response.status_code == 503

    assert (
        response.json()["detail"]
        == "Le service audio est désactivé."
    )