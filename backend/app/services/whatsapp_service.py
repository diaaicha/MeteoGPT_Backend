import subprocess
from typing import Any

from pathlib import Path
from tempfile import NamedTemporaryFile

from backend.app.services import audio_service

from backend.app.schemas.whatsapp import (
    WhatsAppAudioMessage,
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

def _get_audio_suffix(
    mime_type: str | None,
) -> str:
    """
    Détermine une extension de fichier adaptée
    au type MIME audio reçu depuis WhatsApp.
    """

    normalized = (
        str(mime_type or "")
        .split(";", 1)[0]
        .strip()
        .lower()
    )

    suffixes = {
        "audio/ogg": ".ogg",
        "audio/opus": ".opus",
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/mp4": ".m4a",
        "audio/aac": ".aac",
        "audio/amr": ".amr",
    }

    return suffixes.get(
        normalized,
        ".ogg",
    )

def extract_audio_messages(
    payload: dict[str, Any],
) -> list[WhatsAppAudioMessage]:
    """
    Extrait les messages audio d'un webhook WhatsApp Cloud API.

    Les événements non audio ou incomplets sont ignorés.
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
                ) != "audio":
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

                audio_data = message.get(
                    "audio",
                    {},
                )

                if not isinstance(
                    audio_data,
                    dict,
                ):
                    continue

                media_id = str(
                    audio_data.get(
                        "id",
                        "",
                    )
                ).strip()

                raw_mime_type = audio_data.get(
                    "mime_type"
                )

                mime_type = (
                    str(raw_mime_type).strip()
                    if raw_mime_type
                    else None
                )

                if not (
                    sender
                    and message_id
                    and media_id
                ):
                    continue

                extracted_messages.append(
                    WhatsAppAudioMessage(
                        sender=sender,
                        message_id=message_id,
                        media_id=media_id,
                        mime_type=mime_type,
                    )
                )

    return extracted_messages

def convert_wav_to_whatsapp_ogg(
    *,
    input_path: Path,
    output_path: Path,
) -> Path:
    """
    Convertit un fichier WAV en OGG/Opus
    compatible avec un message vocal WhatsApp.
    """

    input_path = Path(
        input_path
    )

    output_path = Path(
        output_path
    )

    if not input_path.exists():
        raise FileNotFoundError(
            f"Fichier audio introuvable : {input_path}"
        )

    if not input_path.is_file():
        raise ValueError(
            "Le chemin audio source n'est pas un fichier."
        )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-c:a",
        "libopus",
        "-b:a",
        "32k",
        "-ar",
        "48000",
        "-ac",
        "1",
        "-application",
        "voip",
        "-f",
        "ogg",
        str(output_path),
    ]

    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )

    except FileNotFoundError as exc:
        raise RuntimeError(
            "FFmpeg n'est pas disponible."
        ) from exc

    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "La conversion audio FFmpeg a échoué."
        ) from exc

    if (
        not output_path.exists()
        or output_path.stat().st_size == 0
    ):
        raise RuntimeError(
            "Le fichier OGG généré est vide ou absent."
        )

    return output_path

def upload_whatsapp_media(
    *,
    media_path: Path,
    mime_type: str = "audio/ogg",
    http_client: httpx.Client | None = None,
) -> str:
    """
    Téléverse un fichier média vers WhatsApp Cloud API
    et retourne son identifiant Meta.
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

    media_path = Path(
        media_path
    )

    if not media_path.exists():
        raise FileNotFoundError(
            f"Fichier média introuvable : {media_path}"
        )

    if not media_path.is_file():
        raise ValueError(
            "Le chemin média ne correspond pas à un fichier."
        )

    if media_path.stat().st_size == 0:
        raise ValueError(
            "Le fichier média est vide."
        )

    mime_type = str(
        mime_type or ""
    ).strip()

    if not mime_type:
        raise ValueError(
            "Le type MIME du média est obligatoire."
        )

    url = (
        "https://graph.facebook.com/"
        f"{settings.whatsapp_api_version}/"
        f"{settings.whatsapp_phone_number_id}/media"
    )

    headers = {
        "Authorization": (
            f"Bearer {settings.whatsapp_access_token}"
        ),
    }

    owns_client = (
        http_client is None
    )

    client = (
        http_client
        or httpx.Client(
            timeout=30.0
        )
    )

    try:
        with media_path.open(
            "rb"
        ) as media_file:

            response = client.post(
                url,
                headers=headers,
                data={
                    "messaging_product":
                        "whatsapp",
                },
                files={
                    "file": (
                        media_path.name,
                        media_file,
                        mime_type,
                    ),
                },
            )

        response.raise_for_status()

        data = response.json()

        if not isinstance(
            data,
            dict,
        ):
            raise RuntimeError(
                "Réponse Meta invalide lors "
                "du téléversement du média."
            )

        media_id = str(
            data.get("id")
            or ""
        ).strip()

        if not media_id:
            raise RuntimeError(
                "Meta n'a retourné aucun media_id."
            )

        return media_id

    finally:
        if owns_client:
            client.close()
def send_whatsapp_audio_message(
    *,
    recipient: str,
    media_id: str,
    voice: bool = True,
    http_client: httpx.Client | None = None,
) -> dict[str, Any]:
    """
    Envoie un média audio WhatsApp déjà téléversé.
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
        recipient or ""
    ).strip()

    media_id = str(
        media_id or ""
    ).strip()

    if not recipient:
        raise ValueError(
            "Le destinataire WhatsApp est obligatoire."
        )

    if not media_id:
        raise ValueError(
            "Le media_id WhatsApp est obligatoire."
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
        "Content-Type":
            "application/json",
    }

    payload = {
        "messaging_product":
            "whatsapp",
        "recipient_type":
            "individual",
        "to":
            recipient,
        "type":
            "audio",
        "audio": {
            "id":
                media_id,
            "voice":
                voice,
        },
    }

    owns_client = (
        http_client is None
    )

    client = (
        http_client
        or httpx.Client(
            timeout=30.0
        )
    )

    try:
        response = client.post(
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
                "Réponse Meta invalide lors "
                "de l'envoi audio."
            )

        return data

    finally:
        if owns_client:
            client.close()

def process_whatsapp_audio_message(
    message: WhatsAppAudioMessage,
):
    """
    Traite un message audio WhatsApp.

    Flux :
    media Meta
        -> telechargement
        -> fichier audio entrant temporaire
        -> pipeline audio B7
        -> TTS WAV
        -> conversion OGG/Opus
        -> upload Meta
        -> reponse vocale WhatsApp

    Si la generation ou l'envoi vocal n'est pas disponible,
    la reponse texte est envoyee en fallback.
    """

    metadata = get_whatsapp_media_metadata(
        media_id=message.media_id,
    )

    media_url = str(
        metadata.get(
            "url",
            "",
        )
    ).strip()

    if not media_url:
        raise RuntimeError(
            "URL du media WhatsApp absente."
        )

    mime_type = (
        metadata.get("mime_type")
        or message.mime_type
    )

    audio_content = download_whatsapp_media(
        media_url=media_url,
    )

    suffix = _get_audio_suffix(
        mime_type
    )

    input_path = None
    wav_path = None
    ogg_path = None

    try:
        # -----------------------------------------------------
        # 1. Audio entrant temporaire
        # -----------------------------------------------------

        with NamedTemporaryFile(
            mode="wb",
            suffix=suffix,
            delete=False,
        ) as input_file:
            input_file.write(
                audio_content
            )

            input_path = Path(
                input_file.name
            )

        # -----------------------------------------------------
        # 2. Fichier WAV temporaire produit par B7
        # -----------------------------------------------------

        with NamedTemporaryFile(
            suffix=".wav",
            delete=False,
        ) as wav_file:
            wav_path = Path(
                wav_file.name
            )

        # -----------------------------------------------------
        # 3. Fichier OGG/Opus temporaire pour WhatsApp
        # -----------------------------------------------------

        with NamedTemporaryFile(
            suffix=".ogg",
            delete=False,
        ) as ogg_file:
            ogg_path = Path(
                ogg_file.name
            )

        # -----------------------------------------------------
        # 4. STT -> pipeline conversationnel -> TTS
        # -----------------------------------------------------

        audio_response = (
            audio_service.process_audio_chat(
                audio_path=input_path,
                output_mode="audio",
                thread_id=message.sender,
                audio_output_path=wav_path,
            )
        )

        # -----------------------------------------------------
        # 5. Reponse vocale
        # -----------------------------------------------------

        if (
            audio_response.success
            and audio_response.audio_available
            and wav_path.exists()
            and wav_path.stat().st_size > 0
        ):
            try:
                converted_path = (
                    convert_wav_to_whatsapp_ogg(
                        input_path=wav_path,
                        output_path=ogg_path,
                    )
                )

                media_id = (
                    upload_whatsapp_media(
                        media_path=converted_path,
                        mime_type="audio/ogg",
                    )
                )

                send_whatsapp_audio_message(
                    recipient=message.sender,
                    media_id=media_id,
                    voice=True,
                )

                return audio_response

            except Exception:
                # Le pipeline B7 a produit une reponse texte.
                # Si la chaine audio sortante echoue,
                # WhatsApp recoit au minimum cette reponse.
                if audio_response.answer:
                    send_whatsapp_text_message(
                        recipient=message.sender,
                        text=audio_response.answer,
                    )

                return audio_response

        # -----------------------------------------------------
        # 6. Fallback texte
        # -----------------------------------------------------

        if (
            audio_response.success
            and audio_response.answer
        ):
            send_whatsapp_text_message(
                recipient=message.sender,
                text=audio_response.answer,
            )

        return audio_response

    finally:
        for temp_path in (
            input_path,
            wav_path,
            ogg_path,
        ):
            if (
                temp_path is not None
                and temp_path.exists()
            ):
                try:
                    temp_path.unlink()
                except OSError:
                    pass

def get_whatsapp_media_metadata(
    *,
    media_id: str,
    http_client: httpx.Client | None = None,
) -> dict[str, Any]:
    """
    Récupère les métadonnées d'un média WhatsApp
    à partir de son identifiant Meta.
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

    media_id = str(
        media_id
    ).strip()

    if not media_id:
        raise ValueError(
            "L'identifiant du média WhatsApp est vide."
        )

    url = (
        "https://graph.facebook.com/"
        f"{settings.whatsapp_api_version}/"
        f"{media_id}"
    )

    headers = {
        "Authorization": (
            f"Bearer {settings.whatsapp_access_token}"
        ),
    }

    client_owned = False

    if http_client is None:
        http_client = httpx.Client(
            timeout=15.0
        )
        client_owned = True

    try:
        response = http_client.get(
            url,
            headers=headers,
        )

        response.raise_for_status()

        data = response.json()

        if not isinstance(
            data,
            dict,
        ):
            raise RuntimeError(
                "Réponse de métadonnées WhatsApp invalide."
            )

        media_url = str(
            data.get(
                "url",
                "",
            )
        ).strip()

        if not media_url:
            raise RuntimeError(
                "URL du média WhatsApp absente."
            )

        return data

    finally:
        if client_owned:
            http_client.close()

def download_whatsapp_media(
    *,
    media_url: str,
    http_client: httpx.Client | None = None,
) -> bytes:
    """
    Télécharge le contenu binaire d'un média WhatsApp.
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

    media_url = str(
        media_url
    ).strip()

    if not media_url:
        raise ValueError(
            "L'URL du média WhatsApp est vide."
        )

    if not media_url.startswith(
        "https://"
    ):
        raise ValueError(
            "L'URL du média WhatsApp doit utiliser HTTPS."
        )

    headers = {
        "Authorization": (
            f"Bearer {settings.whatsapp_access_token}"
        ),
    }

    client_owned = False

    if http_client is None:
        http_client = httpx.Client(
            timeout=30.0
        )
        client_owned = True

    try:
        response = http_client.get(
            media_url,
            headers=headers,
        )

        response.raise_for_status()

        content = response.content

        if not content:
            raise RuntimeError(
                "Le média WhatsApp téléchargé est vide."
            )

        return content

    finally:
        if client_owned:
            http_client.close()

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
