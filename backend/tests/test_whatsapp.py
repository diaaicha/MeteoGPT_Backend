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

