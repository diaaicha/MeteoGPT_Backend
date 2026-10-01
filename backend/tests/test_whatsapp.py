from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.api.routes import whatsapp as whatsapp_route


client = TestClient(app)


def test_whatsapp_webhook_verification_success(
    monkeypatch,
):
    settings = SimpleNamespace(
        enable_whatsapp=True,
        whatsapp_verify_token="test-verify-token",
    )

    monkeypatch.setattr(
        whatsapp_route,
        "get_settings",
        lambda: settings,
    )

    response = client.get(
        "/api/v1/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "test-verify-token",
            "hub.challenge": "123456",
        },
    )

    assert response.status_code == 200
    assert response.text == "123456"


def test_whatsapp_webhook_rejects_invalid_token(
    monkeypatch,
):
    settings = SimpleNamespace(
        enable_whatsapp=True,
        whatsapp_verify_token="correct-token",
    )

    monkeypatch.setattr(
        whatsapp_route,
        "get_settings",
        lambda: settings,
    )

    response = client.get(
        "/api/v1/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong-token",
            "hub.challenge": "123456",
        },
    )

    assert response.status_code == 403


def test_whatsapp_webhook_disabled(
    monkeypatch,
):
    settings = SimpleNamespace(
        enable_whatsapp=False,
        whatsapp_verify_token="test-verify-token",
    )

    monkeypatch.setattr(
        whatsapp_route,
        "get_settings",
        lambda: settings,
    )

    response = client.get(
        "/api/v1/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "test-verify-token",
            "hub.challenge": "123456",
        },
    )

    assert response.status_code == 503


def test_extract_whatsapp_text_message():
    from backend.app.services.whatsapp_service import (
        extract_text_messages,
    )

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "business-account-id",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number":
                                    "221000000000",
                                "phone_number_id":
                                    "123456789",
                            },
                            "contacts": [
                                {
                                    "profile": {
                                        "name": "Test User",
                                    },
                                    "wa_id":
                                        "221770000000",
                                }
                            ],
                            "messages": [
                                {
                                    "from":
                                        "221770000000",
                                    "id":
                                        "wamid.TEST123",
                                    "timestamp":
                                        "1690000000",
                                    "type":
                                        "text",
                                    "text": {
                                        "body":
                                            "Quel temps fera-t-il à Dakar ?"
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }

    messages = extract_text_messages(
        payload
    )

    assert len(messages) == 1

    message = messages[0]

    assert (
        message.sender
        == "221770000000"
    )

    assert (
        message.message_id
        == "wamid.TEST123"
    )

    assert (
        message.text
        == "Quel temps fera-t-il à Dakar ?"
    )

def test_extract_whatsapp_audio_message():
    from backend.app.services.whatsapp_service import (
        extract_audio_messages,
    )

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messages": [
                                {
                                    "from":
                                        "221770000000",
                                    "id":
                                        "wamid.AUDIO123",
                                    "type":
                                        "audio",
                                    "audio": {
                                        "id":
                                            "media-audio-123",
                                        "mime_type":
                                            "audio/ogg; codecs=opus",
                                        "voice":
                                            True,
                                    },
                                }
                            ]
                        },
                    }
                ],
            }
        ],
    }

    messages = extract_audio_messages(
        payload
    )

    assert len(messages) == 1

    message = messages[0]

    assert (
        message.sender
        == "221770000000"
    )

    assert (
        message.message_id
        == "wamid.AUDIO123"
    )

    assert (
        message.media_id
        == "media-audio-123"
    )

    assert (
        message.mime_type
        == "audio/ogg; codecs=opus"
    )

def test_whatsapp_webhook_receives_text_message(
    monkeypatch,
):
    settings = SimpleNamespace(
        enable_whatsapp=True,
        whatsapp_verify_token="test-token",
    )

    monkeypatch.setattr(
        whatsapp_route,
        "get_settings",
        lambda: settings,
    )

    monkeypatch.setattr(
        whatsapp_route,
        "process_whatsapp_text_message",
        lambda message: None,
    )

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "business-account-id",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product":
                                "whatsapp",
                            "messages": [
                                {
                                    "from":
                                        "221770000000",
                                    "id":
                                        "wamid.TEST123",
                                    "type":
                                        "text",
                                    "text": {
                                        "body":
                                            "Météo à Dakar"
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }

    response = client.post(
        "/api/v1/whatsapp/webhook",
        json=payload,
    )

    assert response.status_code == 200

    assert response.json() == {
        "status": "received",
        "messages_received": 1,
    }


def test_whatsapp_webhook_accepts_event_without_text_message(
    monkeypatch,
):
    settings = SimpleNamespace(
        enable_whatsapp=True,
        whatsapp_verify_token="test-token",
    )

    monkeypatch.setattr(
        whatsapp_route,
        "get_settings",
        lambda: settings,
    )

    response = client.post(
        "/api/v1/whatsapp/webhook",
        json={
            "object":
                "whatsapp_business_account",
            "entry": [],
        },
    )

    assert response.status_code == 200

    assert response.json() == {
        "status": "received",
        "messages_received": 0,
    }

def test_whatsapp_text_message_uses_sender_as_thread_id(
    monkeypatch,
):
    from backend.app.schemas.whatsapp import (
        WhatsAppTextMessage,
    )

    from backend.app.services import (
        whatsapp_service,
    )

    captured = {}

    def fake_process_chat(
        *,
        query,
        thread_id=None,
        user_preferences=None,
    ):
        captured["query"] = query
        captured["thread_id"] = thread_id

        return SimpleNamespace(
            success=True,
            answer="Réponse météo de test",
        )

    monkeypatch.setattr(
        whatsapp_service,
        "process_chat",
        fake_process_chat,
    )

    message = WhatsAppTextMessage(
        sender="221770000000",
        message_id="wamid.TEST123",
        text="Météo à Dakar",
    )

    sent = {}

    def fake_send(
        *,
        recipient,
        text,
        http_client=None,
    ):
        sent["recipient"] = recipient
        sent["text"] = text

        return {
            "messages": [
                {
                    "id": "wamid.TEST"
                }
            ]
        }

    monkeypatch.setattr(
        whatsapp_service,
        "send_whatsapp_text_message",
        fake_send,
    )

    whatsapp_service.process_whatsapp_text_message(
        message
    )

    assert captured["query"] == "Météo à Dakar"

    assert (
        captured["thread_id"]
        == "221770000000"
    )

    assert (
        sent["recipient"]
        == "221770000000"
    )

    assert (
        sent["text"]
        == "Réponse météo de test"
    )

def test_whatsapp_webhook_schedules_text_processing(
    monkeypatch,
):
    settings = SimpleNamespace(
        enable_whatsapp=True,
        whatsapp_verify_token="test-token",
    )

    monkeypatch.setattr(
        whatsapp_route,
        "get_settings",
        lambda: settings,
    )

    captured = []

    def fake_process_message(
        message,
    ):
        captured.append(
            message
        )

    monkeypatch.setattr(
        whatsapp_route,
        "process_whatsapp_text_message",
        fake_process_message,
    )

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from":
                                        "221770000000",
                                    "id":
                                        "wamid.TEST123",
                                    "type":
                                        "text",
                                    "text": {
                                        "body":
                                            "Météo à Dakar"
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
        ],
    }

    response = client.post(
        "/api/v1/whatsapp/webhook",
        json=payload,
    )

    assert response.status_code == 200
    assert len(captured) == 1

    assert (
        captured[0].sender
        == "221770000000"
    )

    assert (
        captured[0].text
        == "Météo à Dakar"
    )

def test_send_whatsapp_text_message(
    monkeypatch,
):
    import json
    import httpx

    from backend.app.services import (
        whatsapp_service,
    )

    settings = SimpleNamespace(
        enable_whatsapp=True,
        whatsapp_access_token="fake-access-token",
        whatsapp_phone_number_id="123456789",
        whatsapp_api_version="v23.0",
    )

    monkeypatch.setattr(
        whatsapp_service,
        "get_settings",
        lambda: settings,
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:

        assert (
            str(request.url)
            == (
                "https://graph.facebook.com/"
                "v23.0/123456789/messages"
            )
        )

        assert (
            request.headers["Authorization"]
            == "Bearer fake-access-token"
        )

        payload = json.loads(
            request.content
        )

        assert (
            payload["messaging_product"]
            == "whatsapp"
        )

        assert (
            payload["to"]
            == "221770000000"
        )

        assert (
            payload["type"]
            == "text"
        )

        assert (
            payload["text"]["body"]
            == "Voici la météo à Dakar."
        )

        return httpx.Response(
            status_code=200,
            json={
                "messaging_product":
                    "whatsapp",
                "messages": [
                    {
                        "id":
                            "wamid.RESPONSE123"
                    }
                ],
            },
        )

    transport = httpx.MockTransport(
        handler
    )

    with httpx.Client(
        transport=transport
    ) as client:

        result = (
            whatsapp_service
            .send_whatsapp_text_message(
                recipient="221770000000",
                text=(
                    "Voici la météo à Dakar."
                ),
                http_client=client,
            )
        )

    assert (
        result["messages"][0]["id"]
        == "wamid.RESPONSE123"
    )

def test_get_whatsapp_media_metadata(
    monkeypatch,
):
    import httpx

    from backend.app.services import (
        whatsapp_service,
    )

    settings = SimpleNamespace(
        enable_whatsapp=True,
        whatsapp_access_token="fake-access-token",
        whatsapp_api_version="v25.0",
    )

    monkeypatch.setattr(
        whatsapp_service,
        "get_settings",
        lambda: settings,
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:

        assert request.method == "GET"

        assert (
            str(request.url)
            == (
                "https://graph.facebook.com/"
                "v25.0/media-audio-123"
            )
        )

        assert (
            request.headers["Authorization"]
            == "Bearer fake-access-token"
        )

        return httpx.Response(
            status_code=200,
            json={
                "url": (
                    "https://lookaside.example/"
                    "media-audio-123"
                ),
                "mime_type":
                    "audio/ogg; codecs=opus",
                "sha256":
                    "fake-sha256",
                "file_size":
                    12345,
                "id":
                    "media-audio-123",
                "messaging_product":
                    "whatsapp",
            },
        )

    transport = httpx.MockTransport(
        handler
    )

    with httpx.Client(
        transport=transport
    ) as client:

        result = (
            whatsapp_service
            .get_whatsapp_media_metadata(
                media_id="media-audio-123",
                http_client=client,
            )
        )

    assert (
        result["id"]
        == "media-audio-123"
    )

    assert (
        result["mime_type"]
        == "audio/ogg; codecs=opus"
    )

    assert result["file_size"] == 12345

    assert (
        result["url"]
        == (
            "https://lookaside.example/"
            "media-audio-123"
        )
    )

def test_download_whatsapp_media(
    monkeypatch,
):
    import httpx

    from backend.app.services import (
        whatsapp_service,
    )

    settings = SimpleNamespace(
        enable_whatsapp=True,
        whatsapp_access_token="fake-access-token",
    )

    monkeypatch.setattr(
        whatsapp_service,
        "get_settings",
        lambda: settings,
    )

    expected_content = (
        b"fake-whatsapp-audio-content"
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:

        assert request.method == "GET"

        assert (
            str(request.url)
            == (
                "https://lookaside.example/"
                "media-audio-123"
            )
        )

        assert (
            request.headers["Authorization"]
            == "Bearer fake-access-token"
        )

        return httpx.Response(
            status_code=200,
            content=expected_content,
            headers={
                "Content-Type":
                    "audio/ogg",
            },
        )

    transport = httpx.MockTransport(
        handler
    )

    with httpx.Client(
        transport=transport
    ) as client:

        result = (
            whatsapp_service
            .download_whatsapp_media(
                media_url=(
                    "https://lookaside.example/"
                    "media-audio-123"
                ),
                http_client=client,
            )
        )

    assert result == expected_content

def test_process_whatsapp_audio_message(
    monkeypatch,
):
    from pathlib import Path

    from backend.app.schemas.whatsapp import (
        WhatsAppAudioMessage,
    )

    from backend.app.services import (
        whatsapp_service,
    )

    message = WhatsAppAudioMessage(
        sender="221770000000",
        message_id="wamid.AUDIO123",
        media_id="media-audio-123",
        mime_type="audio/ogg; codecs=opus",
    )

    monkeypatch.setattr(
        whatsapp_service,
        "get_whatsapp_media_metadata",
        lambda *,
        media_id,
        http_client=None: {
            "id": media_id,
            "url": (
                "https://lookaside.example/"
                "media-audio-123"
            ),
            "mime_type":
                "audio/ogg; codecs=opus",
        },
    )

    monkeypatch.setattr(
        whatsapp_service,
        "download_whatsapp_media",
        lambda *,
        media_url,
        http_client=None: (
            b"fake-audio-content"
        ),
    )

    captured = {}

    def fake_process_audio_chat(
        *,
        audio_path,
        output_mode="text",
        thread_id=None,
        user_preferences=None,
        generation_client=None,
        speech_client=None,
        audio_output_path=None,
    ):
        audio_path = Path(
            audio_path
        )

        audio_output_path = Path(
            audio_output_path
        )

        assert audio_path.exists()

        captured["input_path"] = (
            audio_path
        )

        captured["input_suffix"] = (
            audio_path.suffix
        )

        captured["output_mode"] = (
            output_mode
        )

        captured["thread_id"] = (
            thread_id
        )

        captured["wav_path"] = (
            audio_output_path
        )

        captured["wav_suffix"] = (
            audio_output_path.suffix
        )

        audio_output_path.write_bytes(
            b"fake-wav-content"
        )

        return SimpleNamespace(
            success=True,
            answer=(
                "Reponse meteo audio de test"
            ),
            audio_available=True,
        )

    monkeypatch.setattr(
        whatsapp_service.audio_service,
        "process_audio_chat",
        fake_process_audio_chat,
    )

    def fake_convert(
        *,
        input_path,
        output_path,
    ):
        input_path = Path(
            input_path
        )

        output_path = Path(
            output_path
        )

        assert input_path.exists()

        assert (
            input_path.read_bytes()
            == b"fake-wav-content"
        )

        captured["ogg_path"] = (
            output_path
        )

        captured["ogg_suffix"] = (
            output_path.suffix
        )

        output_path.write_bytes(
            b"fake-ogg-opus-content"
        )

        return output_path

    monkeypatch.setattr(
        whatsapp_service,
        "convert_wav_to_whatsapp_ogg",
        fake_convert,
    )

    def fake_upload(
        *,
        media_path,
        mime_type="audio/ogg",
        http_client=None,
    ):
        media_path = Path(
            media_path
        )

        assert media_path.exists()

        assert (
            media_path.read_bytes()
            == b"fake-ogg-opus-content"
        )

        captured["upload_mime_type"] = (
            mime_type
        )

        return "MEDIA_ID_RESPONSE"

    monkeypatch.setattr(
        whatsapp_service,
        "upload_whatsapp_media",
        fake_upload,
    )

    sent = {}

    def fake_send_audio(
        *,
        recipient,
        media_id,
        voice=True,
        http_client=None,
    ):
        sent["recipient"] = (
            recipient
        )

        sent["media_id"] = (
            media_id
        )

        sent["voice"] = (
            voice
        )

        return {
            "messages": [
                {
                    "id":
                        "wamid.RESPONSE"
                }
            ]
        }

    monkeypatch.setattr(
        whatsapp_service,
        "send_whatsapp_audio_message",
        fake_send_audio,
    )

    def fail_text_send(
        **kwargs,
    ):
        raise AssertionError(
            "Le fallback texte ne doit pas "
            "etre utilise dans ce test."
        )

    monkeypatch.setattr(
        whatsapp_service,
        "send_whatsapp_text_message",
        fail_text_send,
    )

    result = (
        whatsapp_service
        .process_whatsapp_audio_message(
            message
        )
    )

    assert result.success is True

    assert (
        captured["input_suffix"]
        == ".ogg"
    )

    assert (
        captured["output_mode"]
        == "audio"
    )

    assert (
        captured["thread_id"]
        == "221770000000"
    )

    assert (
        captured["wav_suffix"]
        == ".wav"
    )

    assert (
        captured["ogg_suffix"]
        == ".ogg"
    )

    assert (
        captured["upload_mime_type"]
        == "audio/ogg"
    )

    assert (
        sent["recipient"]
        == "221770000000"
    )

    assert (
        sent["media_id"]
        == "MEDIA_ID_RESPONSE"
    )

    assert sent["voice"] is True

    assert (
        captured["input_path"].exists()
        is False
    )

    assert (
        captured["wav_path"].exists()
        is False
    )

    assert (
        captured["ogg_path"].exists()
        is False
    )


def test_whatsapp_webhook_schedules_audio_processing(
    monkeypatch,
):
    settings = SimpleNamespace(
        enable_whatsapp=True,
        whatsapp_verify_token="test-token",
    )

    monkeypatch.setattr(
        whatsapp_route,
        "get_settings",
        lambda: settings,
    )

    captured = []

    def fake_process_audio_message(
        message,
    ):
        captured.append(
            message
        )

    monkeypatch.setattr(
        whatsapp_route,
        "process_whatsapp_audio_message",
        fake_process_audio_message,
    )

    payload = {
        "object":
            "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from":
                                        "221770000000",
                                    "id":
                                        "wamid.AUDIO123",
                                    "type":
                                        "audio",
                                    "audio": {
                                        "id":
                                            "media-audio-123",
                                        "mime_type":
                                            "audio/ogg; codecs=opus",
                                        "voice":
                                            True,
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
        ],
    }

    response = client.post(
        "/api/v1/whatsapp/webhook",
        json=payload,
    )

    assert response.status_code == 200

    assert response.json() == {
        "status": "received",
        "messages_received": 1,
    }

    assert len(captured) == 1

    assert (
        captured[0].sender
        == "221770000000"
    )

    assert (
        captured[0].message_id
        == "wamid.AUDIO123"
    )

    assert (
        captured[0].media_id
        == "media-audio-123"
    )

    assert (
        captured[0].mime_type
        == "audio/ogg; codecs=opus"
    )

def test_whatsapp_audio_flow_end_to_end(
    monkeypatch,
):
    from pathlib import Path

    from backend.app.services import (
        whatsapp_service,
    )

    settings = SimpleNamespace(
        enable_whatsapp=True,
        whatsapp_verify_token="test-token",
    )

    monkeypatch.setattr(
        whatsapp_route,
        "get_settings",
        lambda: settings,
    )

    monkeypatch.setattr(
        whatsapp_service,
        "get_whatsapp_media_metadata",
        lambda *,
        media_id,
        http_client=None: {
            "id": media_id,
            "url": (
                "https://lookaside.example/"
                "media-audio-123"
            ),
            "mime_type":
                "audio/ogg; codecs=opus",
        },
    )

    monkeypatch.setattr(
        whatsapp_service,
        "download_whatsapp_media",
        lambda *,
        media_url,
        http_client=None: (
            b"fake-whatsapp-audio"
        ),
    )

    captured = {}

    def fake_process_audio_chat(
        *,
        audio_path,
        output_mode="text",
        thread_id=None,
        user_preferences=None,
        generation_client=None,
        speech_client=None,
        audio_output_path=None,
    ):
        audio_path = Path(
            audio_path
        )

        audio_output_path = Path(
            audio_output_path
        )

        assert audio_path.exists()

        captured["input_path"] = (
            audio_path
        )

        captured["input_suffix"] = (
            audio_path.suffix
        )

        captured["thread_id"] = (
            thread_id
        )

        captured["output_mode"] = (
            output_mode
        )

        captured["wav_path"] = (
            audio_output_path
        )

        audio_output_path.write_bytes(
            b"fake-generated-wav"
        )

        return SimpleNamespace(
            success=True,
            answer=(
                "Reponse audio WhatsApp de test"
            ),
            audio_available=True,
        )

    monkeypatch.setattr(
        whatsapp_service.audio_service,
        "process_audio_chat",
        fake_process_audio_chat,
    )

    def fake_convert(
        *,
        input_path,
        output_path,
    ):
        input_path = Path(
            input_path
        )

        output_path = Path(
            output_path
        )

        assert input_path.exists()

        assert (
            input_path.read_bytes()
            == b"fake-generated-wav"
        )

        captured["ogg_path"] = (
            output_path
        )

        output_path.write_bytes(
            b"fake-generated-ogg"
        )

        return output_path

    monkeypatch.setattr(
        whatsapp_service,
        "convert_wav_to_whatsapp_ogg",
        fake_convert,
    )

    def fake_upload(
        *,
        media_path,
        mime_type="audio/ogg",
        http_client=None,
    ):
        media_path = Path(
            media_path
        )

        assert media_path.exists()

        assert (
            media_path.read_bytes()
            == b"fake-generated-ogg"
        )

        captured["upload_mime_type"] = (
            mime_type
        )

        return "MEDIA_ID_E2E"

    monkeypatch.setattr(
        whatsapp_service,
        "upload_whatsapp_media",
        fake_upload,
    )

    sent = {}

    def fake_send_audio(
        *,
        recipient,
        media_id,
        voice=True,
        http_client=None,
    ):
        sent["recipient"] = (
            recipient
        )

        sent["media_id"] = (
            media_id
        )

        sent["voice"] = (
            voice
        )

        return {
            "messages": [
                {
                    "id":
                        "wamid.RESPONSE"
                }
            ]
        }

    monkeypatch.setattr(
        whatsapp_service,
        "send_whatsapp_audio_message",
        fake_send_audio,
    )

    def fail_text_send(
        **kwargs,
    ):
        raise AssertionError(
            "Le fallback texte ne doit pas "
            "etre utilise dans ce test."
        )

    monkeypatch.setattr(
        whatsapp_service,
        "send_whatsapp_text_message",
        fail_text_send,
    )

    payload = {
        "object":
            "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from":
                                        "221770000000",
                                    "id":
                                        "wamid.AUDIO123",
                                    "type":
                                        "audio",
                                    "audio": {
                                        "id":
                                            "media-audio-123",
                                        "mime_type":
                                            "audio/ogg; codecs=opus",
                                        "voice":
                                            True,
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
        ],
    }

    response = client.post(
        "/api/v1/whatsapp/webhook",
        json=payload,
    )

    assert response.status_code == 200

    assert response.json() == {
        "status": "received",
        "messages_received": 1,
    }

    assert (
        captured["thread_id"]
        == "221770000000"
    )

    assert (
        captured["output_mode"]
        == "audio"
    )

    assert (
        captured["input_suffix"]
        == ".ogg"
    )

    assert (
        captured["upload_mime_type"]
        == "audio/ogg"
    )

    assert (
        sent["recipient"]
        == "221770000000"
    )

    assert (
        sent["media_id"]
        == "MEDIA_ID_E2E"
    )

    assert sent["voice"] is True

    assert (
        captured["input_path"].exists()
        is False
    )

    assert (
        captured["wav_path"].exists()
        is False
    )

    assert (
        captured["ogg_path"].exists()
        is False
    )




def test_convert_wav_to_whatsapp_ogg(
    monkeypatch,
    tmp_path,
):
    from backend.app.services import (
        whatsapp_service,
    )

    input_path = (
        tmp_path
        / "input.wav"
    )

    output_path = (
        tmp_path
        / "output.ogg"
    )

    input_path.write_bytes(
        b"fake-wav-content"
    )

    captured = {}

    def fake_run(
        command,
        check,
        capture_output,
        text,
    ):
        captured["command"] = command

        output_path.write_bytes(
            b"fake-ogg-opus-content"
        )

        return SimpleNamespace(
            returncode=0
        )

    monkeypatch.setattr(
        whatsapp_service.subprocess,
        "run",
        fake_run,
    )

    result = (
        whatsapp_service
        .convert_wav_to_whatsapp_ogg(
            input_path=input_path,
            output_path=output_path,
        )
    )

    assert result == output_path

    assert output_path.exists()

    assert (
        output_path.read_bytes()
        == b"fake-ogg-opus-content"
    )

    command = captured["command"]

    assert "libopus" in command
    assert "48000" in command
    assert "ogg" in command

    assert (
        str(input_path)
        in command
    )

    assert (
        str(output_path)
        in command
    )

def test_upload_whatsapp_media(
    monkeypatch,
    tmp_path,
):
    from types import SimpleNamespace

    import httpx

    from backend.app.services import (
        whatsapp_service,
    )

    media_path = (
        tmp_path
        / "response.ogg"
    )

    media_path.write_bytes(
        b"fake-ogg-opus-content"
    )

    monkeypatch.setattr(
        whatsapp_service,
        "get_settings",
        lambda: SimpleNamespace(
            enable_whatsapp=True,
            whatsapp_access_token="test-token",
            whatsapp_phone_number_id="123456789",
            whatsapp_api_version="v25.0",
        ),
    )

    captured = {}

    def handler(
        request: httpx.Request,
    ):
        captured["method"] = (
            request.method
        )

        captured["url"] = str(
            request.url
        )

        captured["authorization"] = (
            request.headers.get(
                "Authorization"
            )
        )

        captured["content_type"] = (
            request.headers.get(
                "Content-Type"
            )
        )

        captured["body"] = (
            request.content
        )

        return httpx.Response(
            200,
            json={
                "id": "MEDIA_ID_123"
            },
        )

    transport = (
        httpx.MockTransport(
            handler
        )
    )

    with httpx.Client(
        transport=transport
    ) as client:

        media_id = (
            whatsapp_service
            .upload_whatsapp_media(
                media_path=media_path,
                mime_type="audio/ogg",
                http_client=client,
            )
        )

    assert (
        media_id
        == "MEDIA_ID_123"
    )

    assert (
        captured["method"]
        == "POST"
    )

    assert captured["url"] == (
        "https://graph.facebook.com/"
        "v25.0/"
        "123456789/media"
    )

    assert (
        captured["authorization"]
        == "Bearer test-token"
    )

    assert (
        "multipart/form-data"
        in captured["content_type"]
    )

    assert (
        b"messaging_product"
        in captured["body"]
    )

    assert (
        b"whatsapp"
        in captured["body"]
    )

    assert (
        b"response.ogg"
        in captured["body"]
    )

    assert (
        b"audio/ogg"
        in captured["body"]
    )

    assert (
        b"fake-ogg-opus-content"
        in captured["body"]
    )

def test_send_whatsapp_audio_message(
    monkeypatch,
):
    from types import SimpleNamespace

    import httpx

    from backend.app.services import (
        whatsapp_service,
    )

    monkeypatch.setattr(
        whatsapp_service,
        "get_settings",
        lambda: SimpleNamespace(
            enable_whatsapp=True,
            whatsapp_access_token="test-token",
            whatsapp_phone_number_id="123456789",
            whatsapp_api_version="v25.0",
        ),
    )

    captured = {}

    def handler(
        request: httpx.Request,
    ):
        captured["method"] = (
            request.method
        )

        captured["url"] = str(
            request.url
        )

        captured["authorization"] = (
            request.headers.get(
                "Authorization"
            )
        )

        captured["body"] = (
            request.content
        )

        return httpx.Response(
            200,
            json={
                "messages": [
                    {
                        "id":
                            "wamid.TEST"
                    }
                ]
            },
        )

    transport = (
        httpx.MockTransport(
            handler
        )
    )

    with httpx.Client(
        transport=transport
    ) as client:

        result = (
            whatsapp_service
            .send_whatsapp_audio_message(
                recipient="221700000000",
                media_id="MEDIA_ID_123",
                voice=True,
                http_client=client,
            )
        )

    assert (
        captured["method"]
        == "POST"
    )

    assert captured["url"] == (
        "https://graph.facebook.com/"
        "v25.0/"
        "123456789/messages"
    )

    assert (
        captured["authorization"]
        == "Bearer test-token"
    )

    body = (
        captured["body"]
        .decode("utf-8")
    )

    assert (
        '"type":"audio"'
        in body
    )

    assert (
        '"id":"MEDIA_ID_123"'
        in body
    )

    assert (
        '"voice":true'
        in body
    )

    assert (
        result["messages"][0]["id"]
        == "wamid.TEST"
    )

def test_process_whatsapp_audio_message_fallback_text(
    monkeypatch,
):
    from pathlib import Path

    from backend.app.schemas.whatsapp import (
        WhatsAppAudioMessage,
    )

    from backend.app.services import (
        whatsapp_service,
    )

    message = WhatsAppAudioMessage(
        sender="221770000000",
        message_id="wamid.AUDIO123",
        media_id="media-audio-123",
        mime_type="audio/ogg; codecs=opus",
    )

    monkeypatch.setattr(
        whatsapp_service,
        "get_whatsapp_media_metadata",
        lambda *,
        media_id,
        http_client=None: {
            "id": media_id,
            "url": (
                "https://lookaside.example/"
                "media-audio-123"
            ),
            "mime_type":
                "audio/ogg; codecs=opus",
        },
    )

    monkeypatch.setattr(
        whatsapp_service,
        "download_whatsapp_media",
        lambda *,
        media_url,
        http_client=None: (
            b"fake-audio-content"
        ),
    )

    captured = {}

    def fake_process_audio_chat(
        *,
        audio_path,
        output_mode="text",
        thread_id=None,
        user_preferences=None,
        generation_client=None,
        speech_client=None,
        audio_output_path=None,
    ):
        audio_path = Path(
            audio_path
        )

        audio_output_path = Path(
            audio_output_path
        )

        assert audio_path.exists()

        captured["input_path"] = (
            audio_path
        )

        captured["wav_path"] = (
            audio_output_path
        )

        audio_output_path.write_bytes(
            b"fake-wav-content"
        )

        return SimpleNamespace(
            success=True,
            answer=(
                "Reponse texte de secours"
            ),
            audio_available=True,
        )

    monkeypatch.setattr(
        whatsapp_service.audio_service,
        "process_audio_chat",
        fake_process_audio_chat,
    )

    def fake_convert(
        *,
        input_path,
        output_path,
    ):
        raise RuntimeError(
            "Conversion audio echouee"
        )

    monkeypatch.setattr(
        whatsapp_service,
        "convert_wav_to_whatsapp_ogg",
        fake_convert,
    )

    sent = {}

    def fake_send_text(
        *,
        recipient,
        text,
        http_client=None,
    ):
        sent["recipient"] = (
            recipient
        )

        sent["text"] = (
            text
        )

        return {
            "messages": [
                {
                    "id":
                        "wamid.TEXT_FALLBACK"
                }
            ]
        }

    monkeypatch.setattr(
        whatsapp_service,
        "send_whatsapp_text_message",
        fake_send_text,
    )

    def fail_audio_send(
        **kwargs,
    ):
        raise AssertionError(
            "L'envoi audio ne doit pas etre "
            "appele si la conversion echoue."
        )

    monkeypatch.setattr(
        whatsapp_service,
        "send_whatsapp_audio_message",
        fail_audio_send,
    )

    result = (
        whatsapp_service
        .process_whatsapp_audio_message(
            message
        )
    )

    assert result.success is True

    assert (
        sent["recipient"]
        == "221770000000"
    )

    assert (
        sent["text"]
        == "Reponse texte de secours"
    )

    assert (
        captured["input_path"].exists()
        is False
    )

    assert (
        captured["wav_path"].exists()
        is False
    )