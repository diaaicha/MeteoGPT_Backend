from typing import Any

from backend.app.schemas.whatsapp import (
    WhatsAppTextMessage,
)

from backend.app.services.chat_service import (
    process_chat,
)

import httpx

from backend.app.core.config import (
    get_settings,
)

def extract_text_messages(
    payload: dict[str, Any],
) -> list[WhatsAppTextMessage]:
    """
    Extrait les messages texte d'un webhook WhatsApp Cloud API.

    Les événements non textuels ou incomplets sont ignorés.
    """

    extracted_messages = []

    entries = payload.get(
        "entry",
        [],
    )

    if not isinstance(
        entries,
        list,
    ):
        return []

    for entry in entries:

        if not isinstance(
            entry,
            dict,
        ):
            continue

        changes = entry.get(
            "changes",
            [],
        )

        if not isinstance(
            changes,
            list,
        ):
            continue

        for change in changes:

            if not isinstance(
                change,
                dict,
            ):
                continue

            value = change.get(
                "value",
                {},
            )

            if not isinstance(
                value,
                dict,
            ):
                continue

            messages = value.get(
                "messages",
                [],
            )

            if not isinstance(
                messages,
                list,
            ):
                continue

            for message in messages:

                if not isinstance(
                    message,
                    dict,
                ):
                    continue

                if message.get(
                    "type"
                ) != "text":
                    continue

                sender = str(
                    message.get(
                        "from",
                        "",
                    )
                ).strip()

                message_id = str(
                    message.get(
                        "id",
                        "",
                    )
                ).strip()

                text_data = message.get(
                    "text",
                    {},
                )

                if not isinstance(
                    text_data,
                    dict,
                ):
                    continue

                text = str(
                    text_data.get(
                        "body",
                        "",
                    )
                ).strip()

                if not (
                    sender
                    and message_id
                    and text
                ):
                    continue

                extracted_messages.append(
                    WhatsAppTextMessage(
                        sender=sender,
                        message_id=message_id,
                        text=text,
                    )
                )

    return extracted_messages


def send_whatsapp_text_message(
    *,
    recipient: str,
    text: str,
    http_client: httpx.Client | None = None,
) -> dict[str, Any]:
    """
    Envoie un message texte avec WhatsApp Cloud API.
    """

    settings = get_settings()

    if not settings.enable_whatsapp:
        raise RuntimeError(
            "Le service WhatsApp est désactivé."
        )

    if not settings.whatsapp_access_token:
        raise RuntimeError(
            "WHATSAPP_ACCESS_TOKEN n'est pas configuré."
        )

    if not settings.whatsapp_phone_number_id:
        raise RuntimeError(
            "WHATSAPP_PHONE_NUMBER_ID n'est pas configuré."
        )

    recipient = str(
        recipient
    ).strip()

    text = str(
        text
    ).strip()

    if not recipient:
        raise ValueError(
            "Le destinataire WhatsApp est vide."
        )

    if not text:
        raise ValueError(
            "Le message WhatsApp est vide."
        )

    url = (
        "https://graph.facebook.com/"
        f"{settings.whatsapp_api_version}/"
        f"{settings.whatsapp_phone_number_id}/messages"
    )

    headers = {
        "Authorization": (
            f"Bearer {settings.whatsapp_access_token}"
        ),
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": text,
        },
    }

    client_owned = False

    if http_client is None:
        http_client = httpx.Client(
            timeout=15.0
        )
        client_owned = True

    try:
        response = http_client.post(
            url,
            headers=headers,
            json=payload,
        )

        response.raise_for_status()

        data = response.json()

        if not isinstance(
            data,
            dict,
        ):
            raise RuntimeError(
                "Réponse WhatsApp Cloud API invalide."
            )

        return data

    finally:
        if client_owned:
            http_client.close()


def process_whatsapp_text_message(
    message: WhatsAppTextMessage,
):
    """
    Traite une question WhatsApp puis renvoie
    la réponse générée à l'utilisateur.
    """

    chat_response = process_chat(
        query=message.text,
        thread_id=message.sender,
    )

    if (
        chat_response.success
        and chat_response.answer
    ):
        send_whatsapp_text_message(
            recipient=message.sender,
            text=chat_response.answer,
        )

    return chat_response
