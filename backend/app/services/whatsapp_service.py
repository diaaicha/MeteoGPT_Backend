import subprocess
from typing import Any
import hashlib
import hmac
import logging
from threading import Lock
from time import monotonic
from urllib.parse import urlsplit

from backend.app.services.personalization_service import (
    PersonalizationService,
)

import unicodedata

from backend.app.schemas.chat import (
    ChatResponse,
)

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

from functools import lru_cache

from backend.app.services.user_profile_service import (
    UserProfileStore,
)

_WHATSAPP_MESSAGE_TTL_SECONDS = 3600.0

_processed_whatsapp_message_ids: dict[str, float] = {}

_processed_whatsapp_message_ids_lock = Lock()


def mark_whatsapp_message_if_new(
    message_id: str,
) -> bool:
    """
    Enregistre un message WhatsApp s'il n'a pas deja ete vu.

    Les identifiants expirent automatiquement afin d'eviter
    une croissance illimitee du registre en memoire.
    """

    message_id = str(
        message_id
    ).strip()

    if not message_id:
        return False

    now = monotonic()

    with _processed_whatsapp_message_ids_lock:

        expired_ids = [
            stored_message_id
            for stored_message_id, expires_at
            in _processed_whatsapp_message_ids.items()
            if expires_at <= now
        ]

        for expired_id in expired_ids:
            _processed_whatsapp_message_ids.pop(
                expired_id,
                None,
            )

        if (
            message_id
            in _processed_whatsapp_message_ids
        ):
            return False

        _processed_whatsapp_message_ids[
            message_id
        ] = (
            now
            + _WHATSAPP_MESSAGE_TTL_SECONDS
        )

        return True

def verify_whatsapp_webhook_signature(
    *,
    payload: bytes,
    signature: str | None,
    app_secret: str,
) -> bool:
    """
    Vérifie la signature HMAC-SHA256 d'un webhook Meta.
    """

    if not payload:
        return False

    signature = str(
        signature or ""
    ).strip()

    app_secret = str(
        app_secret or ""
    ).strip()

    if (
        not signature
        or not app_secret
        or not signature.startswith("sha256=")
    ):
        return False

    received_signature = signature[
        len("sha256="):
    ]

    expected_signature = hmac.new(
        app_secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(
        expected_signature,
        received_signature,
    )

def extract_text_messages(
    payload: dict[str, Any],
) -> list[WhatsAppTextMessage]:

    """
    Extrait les messages textuels et les réponses
    aux boutons de personnalisation depuis un webhook
    WhatsApp Cloud API.

    Les boutons reconnus sont convertis en commandes
    textuelles compatibles avec l'agent conversationnel.

    Les événements incomplets ou non pris en charge
    sont ignorés.
    """

    extracted_messages = []

    # ========================================================
    # 1. COMMANDES ASSOCIÉES AUX BOUTONS
    # ========================================================

    button_commands = {

        "open_personalization":
            "Personnaliser mon experience",

        "skip_personalization":
            "Continuer sans personnalisation",
    }

    # ========================================================
    # 2. EXTRACTION DES ENTRÉES
    # ========================================================

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

                # ============================================
                # 3. TYPE DU MESSAGE
                # ============================================

                message_type = message.get(
                    "type"
                )

                if message_type not in (
                    "text",
                    "interactive",
                ):
                    continue

                # ============================================
                # 4. IDENTIFICATION DE L'EXPÉDITEUR
                # ============================================

                sender = message.get(
                    "from"
                )

                message_id = message.get(
                    "id"
                )

                if not isinstance(
                    sender,
                    str,
                ):
                    continue

                if not isinstance(
                    message_id,
                    str,
                ):
                    continue

                sender = sender.strip()

                message_id = message_id.strip()

                if not sender or not message_id:

                    continue

                # ============================================
                # 5. MESSAGE TEXTE CLASSIQUE
                # ============================================

                if message_type == "text":

                    text_data = message.get(
                        "text",
                        {},
                    )

                    if not isinstance(
                        text_data,
                        dict,
                    ):
                        continue

                    text = text_data.get(
                        "body"
                    )

                    if not isinstance(
                        text,
                        str,
                    ):
                        continue

                    text = text.strip()

                # ============================================
                # 6. MESSAGE INTERACTIF
                # ============================================

                else:

                    interactive_data = message.get(
                        "interactive",
                        {},
                    )

                    if not isinstance(
                        interactive_data,
                        dict,
                    ):
                        continue

                    # Seuls les boutons de réponse
                    # sont pris en charge.

                    if interactive_data.get(
                        "type"
                    ) != "button_reply":

                        continue

                    button_reply = interactive_data.get(
                        "button_reply",
                        {},
                    )

                    if not isinstance(
                        button_reply,
                        dict,
                    ):
                        continue

                    button_id = button_reply.get(
                        "id"
                    )

                    if not isinstance(
                        button_id,
                        str,
                    ):
                        continue

                    # Conversion de l'identifiant technique
                    # en commande reconnue par l'agent.

                    text = button_commands.get(
                        button_id
                    )

                    if text is None:

                        continue

                # ============================================
                # 7. VALIDATION DU CONTENU
                # ============================================

                if not text:

                    continue

                # ============================================
                # 8. MESSAGE NORMALISÉ
                # ============================================

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

        # Chargement du profil utilisateur permanent.
        user_preferences = (
            charger_preferences_whatsapp(
                message.sender
            )
        )

        audio_response = (
            audio_service.process_audio_chat(
                audio_path=input_path,
                output_mode="audio",
                thread_id=message.sender,
                user_preferences=user_preferences,
                audio_output_path=wav_path,
            )
        )


        # -----------------------------------------------------
        # Traitement des actions de personnalisation
        # -----------------------------------------------------

        instruction_collecte = (
            traiter_action_personnalisation(
                recipient=message.sender,
                response=audio_response,
            )
        )

        if instruction_collecte is not None:

            # Le démarrage de la collecte est confirmé
            # par un message texte contenant les instructions.

            audio_response.answer = (
                instruction_collecte
            )

            audio_response.audio_available = False

            audio_response.audio_url = None

            send_whatsapp_text_message(
                recipient=message.sender,
                text=instruction_collecte,
            )

            return audio_response

        # -----------------------------------------------------
        # 5. Réponse vocale
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

            except Exception:

                # Si la chaîne audio sortante échoue,
                # envoyer la réponse texte de secours.

                if audio_response.answer:

                    send_whatsapp_text_message(
                        recipient=message.sender,
                        text=audio_response.answer,
                    )

                else:

                    return audio_response

            # -------------------------------------------------
            # Proposition après envoi vocal ou fallback texte
            # -------------------------------------------------

            envoyer_proposition_si_necessaire(
                recipient=message.sender,
                response=audio_response,
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

            envoyer_proposition_si_necessaire(
                recipient=message.sender,
                response=audio_response,
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

# ============================================================
# GESTION DU PROFIL UTILISATEUR WHATSAPP
# ============================================================

@lru_cache(maxsize=1)
def get_user_profile_store():
    """
    Retourne le service de stockage des profils.

    La base SQLite est initialisée uniquement
    lorsqu'elle est réellement nécessaire.
    """

    return UserProfileStore()



# ============================================================
# ENVOI DE LA PROPOSITION DE PERSONNALISATION
# ============================================================

def send_whatsapp_personalization_offer(
    *,
    recipient: str,
    http_client: httpx.Client | None = None,
) -> dict[str, Any]:

    """
    Envoie la proposition facultative de personnalisation
    avec deux boutons interactifs WhatsApp.

    Actions :
    - open_personalization
    - skip_personalization

    Retourne la réponse de WhatsApp Cloud API.
    """

    # ========================================================
    # 1. CONFIGURATION WHATSAPP
    # ========================================================

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

    # ========================================================
    # 2. VALIDATION DU DESTINATAIRE
    # ========================================================

    if not isinstance(recipient, str):

        raise TypeError(
            "Le destinataire doit être une chaîne."
        )

    recipient = recipient.strip()

    if not recipient:

        raise ValueError(
            "Le destinataire WhatsApp est vide."
        )

    # ========================================================
    # 3. CONFIGURATION DE LA REQUÊTE HTTP
    # ========================================================

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

    # ========================================================
    # 4. MESSAGE INTERACTIF
    # ========================================================

    payload = {

        "messaging_product":
            "whatsapp",

        "recipient_type":
            "individual",

        "to":
            recipient,

        "type":
            "interactive",

        "interactive": {

            "type":
                "button",

            "header": {

                "type":
                    "text",

                "text":
                    "Personnalisez votre expérience ✨",
            },

            "body": {

                "text": (
                    "Souhaitez-vous renseigner votre prénom "
                    "et votre nom pour profiter d'échanges "
                    "plus personnalisés ?\n\n"
                    "Cette étape est facultative."
                ),
            },

            "action": {

                "buttons": [

                    {

                        "type":
                            "reply",

                        "reply": {

                            "id":
                                "open_personalization",

                            "title":
                                "Personnaliser",
                        },
                    },

                    {

                        "type":
                            "reply",

                        "reply": {

                            "id":
                                "skip_personalization",

                            "title":
                                "Continuer sans",
                        },
                    },
                ],
            },
        },
    }

    # ========================================================
    # 5. CLIENT HTTP
    # ========================================================

    client_owned = False

    if http_client is None:

        http_client = httpx.Client(
            timeout=15.0
        )

        client_owned = True

    # ========================================================
    # 6. ENVOI DU MESSAGE
    # ========================================================

    try:

        response = http_client.post(
            url,
            headers=headers,
            json=payload,
        )

        response.raise_for_status()

        data = response.json()

        if not isinstance(data, dict):

            raise RuntimeError(
                "Réponse WhatsApp Cloud API invalide."
            )

        # ----------------------------------------------------
        # Vérification de l'acceptation du message par Meta
        # ----------------------------------------------------

        messages = data.get(
            "messages"
        )

        if (
            not isinstance(messages, list)
            or not messages
            or not isinstance(messages[0], dict)
            or not messages[0].get("id")
        ):

            raise RuntimeError(
                "WhatsApp Cloud API n'a retourné "
                "aucun identifiant de message."
            )

        return data

    finally:

        if client_owned:

            http_client.close()


# ============================================================
# ENVOI DU FORMULAIRE WHATSAPP FLOW
# ============================================================

def send_whatsapp_personalization_flow(
    *,
    recipient: str,
    flow_token: str,
    http_client: httpx.Client | None = None,
) -> dict[str, Any]:

    """
    Envoie le formulaire natif de personnalisation.

    Première personnalisation :
        - prénom et nom vides ;
        - bouton de validation.

    Modification :
        - prénom et nom préremplis ;
        - bouton de modification.

    Cette fonction ne modifie pas le profil utilisateur.
    """

    # ========================================================
    # 1. CONFIGURATION
    # ========================================================

    settings = get_settings()

    if not settings.enable_whatsapp:

        raise RuntimeError(
            "Le service WhatsApp est désactivé."
        )

    if not settings.whatsapp_access_token:

        raise RuntimeError(
            "WHATSAPP_ACCESS_TOKEN non configuré."
        )

    if not settings.whatsapp_phone_number_id:

        raise RuntimeError(
            "WHATSAPP_PHONE_NUMBER_ID non configuré."
        )

    flow_id = (
        settings.whatsapp_personalization_flow_id
    )

    flow_mode = (
        settings.whatsapp_personalization_flow_mode
    )

    if not flow_id:

        raise RuntimeError(
            "WHATSAPP_PERSONALIZATION_FLOW_ID "
            "non configuré."
        )

    if flow_mode not in (
        "draft",
        "published",
    ):

        raise ValueError(
            "Mode WhatsApp Flow invalide."
        )

    # ========================================================
    # 2. VALIDATION DES PARAMÈTRES
    # ========================================================

    if not isinstance(
        recipient,
        str
    ) or not recipient.strip():

        raise ValueError(
            "Destinataire WhatsApp invalide."
        )

    if not isinstance(
        flow_token,
        str
    ) or not flow_token.strip():

        raise ValueError(
            "Flow token invalide."
        )

    recipient = recipient.strip()

    # ========================================================
    # 3. CHARGEMENT DU PROFIL EXISTANT
    # ========================================================

    store = get_user_profile_store()

    profil = store.charger_profil(
        recipient
    )

    first_name = (
        profil["first_name"]
        or ""
    )

    last_name = (
        profil["last_name"]
        or ""
    )

    modification = (
        profil["personalization_status"]
        == "accepted"
    )

    # ========================================================
    # 4. ADAPTATION DU FORMULAIRE
    # ========================================================

    if modification:

        heading = (
            "Modifier mes informations"
        )

        description = (
            "Modifiez votre prénom et votre nom, "
            "puis enregistrez vos changements."
        )

        button_label = (
            "Modifier mes informations"
        )

        flow_cta = (
            "Modifier mon profil"
        )

        body = (
            f"Bien sûr, {first_name} ! 😊\n\n"
            "Vous pouvez modifier vos informations "
            "personnelles en ouvrant le formulaire "
            "ci-dessous."
        )

    else:

        heading = (
            "Personnalisez votre expérience"
        )

        description = (
            "Renseignez votre prénom et votre nom "
            "pour profiter d'échanges personnalisés "
            "avec XamMeteo."
        )

        button_label = (
            "Valider mes informations"
        )

        flow_cta = (
            "Ouvrir le formulaire"
        )

        body = (
            "Avec plaisir ! ✨\n\n"
            "Renseignez vos informations personnelles "
            "en ouvrant le formulaire ci-dessous."
        )

    # ========================================================
    # 5. CONSTRUCTION DU PAYLOAD
    # ========================================================

    payload = {

        "messaging_product":
            "whatsapp",

        "recipient_type":
            "individual",

        "to":
            recipient,

        "type":
            "interactive",

        "interactive": {

            "type":
                "flow",

            "body": {

                "text":
                    body,
            },

            "action": {

                "name":
                    "flow",

                "parameters": {

                    "flow_message_version":
                        "3",

                    "flow_id":
                        flow_id,

                    "flow_token":
                        flow_token,

                    "mode":
                        flow_mode,

                    "flow_cta":
                        flow_cta,

                    "flow_action":
                        "navigate",

                    "flow_action_payload": {

                        "screen":
                            "PERSONALIZATION",

                        "data": {

                            "first_name":
                                first_name,

                            "last_name":
                                last_name,

                            "heading":
                                heading,

                            "description":
                                description,

                            "button_label":
                                button_label,
                        },
                    },
                },
            },
        },
    }

    # ========================================================
    # 6. CONFIGURATION DE LA REQUÊTE HTTP
    # ========================================================

    url = (
        "https://graph.facebook.com/"
        f"{settings.whatsapp_api_version}/"
        f"{settings.whatsapp_phone_number_id}/"
        "messages"
    )

    headers = {

        "Authorization": (
            f"Bearer {settings.whatsapp_access_token}"
        ),

        "Content-Type":
            "application/json",
    }

    client_owned = False

    if http_client is None:

        http_client = httpx.Client(
            timeout=15.0
        )

        client_owned = True

    # ========================================================
    # 7. ENVOI DU FORMULAIRE
    # ========================================================

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
            dict
        ):

            raise RuntimeError(
                "Réponse WhatsApp Flow invalide."
            )

        messages = data.get(
            "messages"
        )

        if (
            not isinstance(messages, list)
            or not messages
            or not isinstance(messages[0], dict)
            or not messages[0].get("id")
        ):

            raise RuntimeError(
                "WhatsApp Cloud API n'a retourné "
                "aucun identifiant de message."
            )

        return data

    finally:

        if client_owned:

            http_client.close()




def charger_preferences_whatsapp(
    sender: str
):
    """
    Charge les informations personnelles associées
    à l'identifiant WhatsApp de l'utilisateur.

    Seules les informations nécessaires à la
    personnalisation sont transmises au pipeline.
    """

    store = get_user_profile_store()

    profil = store.charger_profil(
        sender
    )

    return {

        "first_name":
            profil["first_name"],

        "last_name":
            profil["last_name"],

        "personalization_offer_seen":
            profil["personalization_offer_seen"],
    }

# ============================================================
# GESTION DE LA PROPOSITION DE PERSONNALISATION
# ============================================================

def envoyer_proposition_si_necessaire(
    *,
    recipient: str,
    response,
) -> bool:

    """
    Envoie la proposition facultative de personnalisation
    lorsque l'agent l'a demandée.

    La proposition est enregistrée dans SQLite uniquement
    après acceptation de l'envoi par WhatsApp Cloud API.

    Retourne True si la proposition a été envoyée
    et enregistrée, False sinon.
    """

    # ========================================================
    # 1. VÉRIFICATION DE LA RÉPONSE
    # ========================================================

    if not response.success:

        return False

    if not response.answer:

        return False

    if not getattr(
        response,
        "offer_personalization",
        False
    ):

        return False

    if getattr(
        response,
        "personalization_action",
        None
    ):

        return False

    # ========================================================
    # 2. VÉRIFICATION DU PROFIL PERMANENT
    # ========================================================

    store = get_user_profile_store()

    profil = store.charger_profil(
        recipient
    )

    if (
        profil["personalization_status"]
        != "new"
    ):

        return False

    # Ne pas proposer une personnalisation
    # lorsqu'une collecte est déjà active.

    if store.charger_collecte(
        recipient
    ) is not None:

        return False

    # ========================================================
    # 3. ENVOI DE LA PROPOSITION
    # ========================================================

    try:

        send_whatsapp_personalization_offer(
            recipient=recipient
        )

    except Exception as exc:

        logging.getLogger(__name__).warning(
            "Echec envoi proposition personnalisation | "
            "error_type=%s",
            type(exc).__name__,
        )

        # La réponse principale a déjà été envoyée.
        # Ne pas interrompre la conversation.
        # Le statut SQLite reste 'new'.

        return False

    # ========================================================
    # 4. ENREGISTREMENT DE L'ENVOI
    # ========================================================

    try:

        store.marquer_proposition_envoyee(
            recipient
        )

    except Exception as exc:

        logging.getLogger(__name__).error(
            "Echec enregistrement proposition personnalisation | "
            "error_type=%s",
            type(exc).__name__,
        )

        return False

    return True



# ============================================================
# INSTRUCTIONS DE COLLECTE
# ============================================================

def construire_instruction_collecte(
    collecte: dict,
) -> str:

    """
    Construit le message correspondant à l'étape
    actuelle de la collecte.
    """

    if collecte["stage"] == "waiting_first_name":

        return (
            "Avec plaisir ! ✨\n\n"
            "Quel est votre prénom ?\n\n"
            "Répondez par exemple : "
            "Prénom : Mariam\n\n"
            "Vous pouvez continuer à me poser vos "
            "questions météorologiques ou écrire "
            "« Annuler la personnalisation »."
        )

    if collecte["stage"] == "waiting_last_name":

        first_name = collecte["first_name"]

        return (
            f"Merci {first_name} ! 😊\n\n"
            "Quel est votre nom de famille ?\n\n"
            "Répondez par exemple : "
            "Nom : Ndiaye\n\n"
            "Vous pouvez également écrire "
            "« Annuler la personnalisation »."
        )

    raise RuntimeError(
        "Étape de collecte inconnue."
    )



# ============================================================
# CONSTRUCTION DU FORMULAIRE WEB DE PERSONNALISATION
# ============================================================

def construire_message_formulaire_web(
    *,
    recipient: str,
) -> str:

    """
    Génère un lien sécurisé de personnalisation.

    Le même formulaire permet :
        - la création d'un profil ;
        - la modification d'un profil existant.

    Aucun changement du profil n'est effectué
    avant la validation du formulaire.
    """

    # ========================================================
    # 1. CONFIGURATION DE L'ADRESSE PUBLIQUE
    # ========================================================

    settings = get_settings()

    base_url = (
        settings.personalization_public_base_url
        or ""
    ).strip().rstrip("/")

    if not base_url:

        raise ValueError(
            "PERSONALIZATION_PUBLIC_BASE_URL "
            "non configurée."
        )

    adresse = urlsplit(base_url)

    if (
        adresse.scheme != "https"
        or not adresse.hostname
        or adresse.username is not None
        or adresse.password is not None
        or adresse.query
        or adresse.fragment
        or adresse.path
        or any(
            caractere.isspace()
            for caractere in base_url
        )
    ):

        raise ValueError(
            "L'adresse publique du formulaire "
            "doit être une URL HTTPS valide."
        )

    # ========================================================
    # 2. CHARGEMENT DU PROFIL
    # ========================================================

    store = get_user_profile_store()

    profil = store.charger_profil(
        recipient
    )

    service = PersonalizationService(
        profile_store=store
    )

    # ========================================================
    # 3. ANCIENNE COLLECTE
    # ========================================================

    # Abandonner une éventuelle ancienne collecte
    # par messages, sans toucher au profil définitif.

    store.annuler_collecte(
        recipient
    )

    # ========================================================
    # 4. GENERATION DU LIEN SECURISE
    # ========================================================

    token = service.generer_token(
        recipient
    )

    lien = (
        base_url
        + "/api/v1/personnalisation#"
        + token
    )

    # ========================================================
    # 5. FORMULAIRE DE MODIFICATION
    # ========================================================

    if (
        profil["personalization_status"]
        == "accepted"
    ):

        prenom = profil["first_name"]

        return (

            f"Bien sûr, {prenom} ! 😊\n\n"

            "Vous pouvez modifier vos informations "
            "personnelles en ouvrant le formulaire "
            "ci-dessous :\n\n"

            f"{lien}\n\n"

            "Vos informations actuelles sont "
            "déjà renseignées.\n\n"

            "Ce lien est valable pendant 15 minutes. "
            "Vos modifications ne seront enregistrées "
            "qu'après validation du formulaire."
        )

    # ========================================================
    # 6. PREMIERE PERSONNALISATION
    # ========================================================

    return (

        "Avec plaisir ! ✨\n\n"

        "Renseignez votre prénom et votre nom "
        "pour profiter d'échanges personnalisés "
        "avec XamMeteo.\n\n"

        "Ouvrez votre formulaire sécurisé :\n\n"

        f"{lien}\n\n"

        "Ce lien est valable pendant 15 minutes. "
        "Vous pouvez annuler à tout moment."
    )



# ============================================================
# TRAITEMENT DES ACTIONS DE PERSONNALISATION
# ============================================================


def traiter_action_personnalisation(
    *,
    recipient,
    response,
) -> str | None:

    """
    Traite une action de personnalisation détectée
    par l'agent.

    Actions :
        - open_personalization ;
        - skip_personalization.

    Le formulaire web est utilisé lorsque son
    adresse publique est configurée.
    """

    if not response.success:

        return None

    action = getattr(

        response,

        "personalization_action",

        None,
    )

    if action not in (

        "open_personalization",

        "skip_personalization",
    ):

        return None

    settings = get_settings()

    formulaire_web_actif = bool(

        getattr(

            settings,

            "personalization_public_base_url",

            None,
        )
    )

    store = get_user_profile_store()

    # ========================================================
    # 1. REFUS DE PERSONNALISATION
    # ========================================================

    if action == "skip_personalization":

        if formulaire_web_actif:

            service = PersonalizationService(

                profile_store=store
            )

            service.invalider_tokens_utilisateur(

                recipient
            )

        store.enregistrer_refus(
            recipient
        )

        store.annuler_collecte(
            recipient
        )

        return None

    # ========================================================
    # 2. OUVERTURE DU FORMULAIRE WEB
    # ========================================================

    if formulaire_web_actif:

        return construire_message_formulaire_web(

            recipient=recipient
        )

    # ========================================================
    # 3. ANCIEN PARCOURS DE SECOURS
    # ========================================================

    collecte = store.demarrer_collecte(

        recipient
    )

    return construire_instruction_collecte(

        collecte
    )


# ============================================================
# VALIDATION DES INFORMATIONS DE COLLECTE
# ============================================================

def valider_nom_collecte(
    valeur: str,
) -> str:

    """
    Valide une information personnelle explicitement
    fournie dans le cadre de la collecte.

    Les accents, espaces, apostrophes et traits
    d'union sont autorisés.
    """

    if not isinstance(
        valeur,
        str
    ):

        raise ValueError(
            "Information personnelle invalide."
        )

    valeur = unicodedata.normalize(
        "NFC",
        valeur
    )

    valeur = " ".join(
        valeur.split()
    )

    if not valeur:

        raise ValueError(
            "Le champ ne peut pas être vide."
        )

    if len(valeur) > 100:

        raise ValueError(
            "Le champ ne peut pas dépasser "
            "100 caractères."
        )

    # Au moins une lettre doit être présente.

    if not any(
        caractere.isalpha()
        for caractere in valeur
    ):

        raise ValueError(
            "Le champ doit contenir des lettres."
        )

    # Vérification des caractères autorisés.

    for caractere in valeur:

        if (
            caractere.isalpha()

            or unicodedata.category(
                caractere
            ).startswith("M")

            or caractere in (
                " ",
                "-",
                "'",
                "’",
            )
        ):

            continue

        raise ValueError(
            "Caractère non autorisé dans "
            "une information personnelle."
        )

    return valeur



# ============================================================
# TRAITEMENT DES MESSAGES DE COLLECTE
# ============================================================

def traiter_message_collecte(
    *,
    recipient: str,
    text: str,
) -> str | None:

    """
    Traite les messages explicitement destinés
    à la collecte du prénom et du nom.

    Retourne une réponse textuelle si le message
    concerne la collecte.

    Retourne None si le message doit être transmis
    au pipeline conversationnel habituel.
    """

    texte = text.strip()

    texte_normalise = unicodedata.normalize(
        "NFC",
        texte
    ).casefold()

    # ========================================================
    # 1. IDENTIFICATION DU MESSAGE
    # ========================================================

    champ, separateur, valeur = (
        texte.partition(":")
    )

    champ = unicodedata.normalize(
        "NFC",
        champ.strip()
    ).casefold()

    champ_prenom = champ in (
        "prénom",
        "prenom",
    )

    champ_nom = champ == "nom"

    demande_annulation = (
        texte_normalise in (
            "annuler la personnalisation",
            "annuler personnalisation",
        )
    )

    saisie_identite = (
        bool(separateur)
        and (
            champ_prenom
            or champ_nom
        )
    )

    # Un message ordinaire continue directement
    # vers le pipeline météorologique.

    if (
        not saisie_identite
        and not demande_annulation
    ):

        return None

    # ========================================================
    # 2. CHARGEMENT DE LA COLLECTE
    # ========================================================

    store = get_user_profile_store()

    collecte = store.charger_collecte(
        recipient
    )

    # ========================================================
    # 3. ANNULATION
    # ========================================================

    if demande_annulation:

        if collecte is None:

            return (
                "Aucune personnalisation "
                "n'est actuellement en cours. 😊\n\n"
                "Vous pouvez continuer à me poser "
                "vos questions météorologiques."
            )

        store.annuler_collecte(
            recipient
        )

        # Enregistrer le choix de ne pas poursuivre.
        # Un profil déjà accepté reste conservé.

        store.enregistrer_refus(
            recipient
        )

        return (
            "La personnalisation en cours "
            "a été annulée. 😊\n\n"
            "Vous pouvez continuer à me poser "
            "vos questions météorologiques."
        )

    # ========================================================
    # 4. AUCUNE COLLECTE ACTIVE
    # ========================================================

    if collecte is None:

        return (
            "Pour renseigner ou modifier vos "
            "informations personnelles, écrivez "
            "« Modifier mes informations »."
        )

    # ========================================================
    # 5. VALIDATION DE L'ÉTAPE
    # ========================================================

    stage = collecte["stage"]

    if (
        stage == "waiting_first_name"
        and not champ_prenom
    ):

        return (
            "Commençons par votre prénom. 😊\n\n"
            "Répondez par exemple : "
            "Prénom : Mariam"
        )

    if (
        stage == "waiting_last_name"
        and not champ_nom
    ):

        return (
            "Votre prénom est déjà renseigné. 😊\n\n"
            "Indiquez maintenant votre nom "
            "de famille.\n\n"
            "Par exemple : Nom : Ndiaye"
        )

    # ========================================================
    # 6. VALIDATION DE LA VALEUR
    # ========================================================

    try:

        valeur = valider_nom_collecte(
            valeur
        )

    except ValueError:

        if stage == "waiting_first_name":

            return (
                "Ce prénom semble invalide.\n\n"
                "Réessayez sous la forme : "
                "Prénom : Mariam"
            )

        return (
            "Ce nom semble invalide.\n\n"
            "Réessayez sous la forme : "
            "Nom : Ndiaye"
        )

    # ========================================================
    # 7. ENREGISTREMENT TEMPORAIRE DU PRÉNOM
    # ========================================================

    if stage == "waiting_first_name":

        collecte = (
            store.enregistrer_prenom_collecte(
                user_id=recipient,
                first_name=valeur
            )
        )

        return construire_instruction_collecte(
            collecte
        )

    # ========================================================
    # 8. ENREGISTREMENT DÉFINITIF
    # ========================================================

    if stage == "waiting_last_name":

        profil = store.finaliser_collecte(
            user_id=recipient,
            last_name=valeur
        )

        first_name = profil["first_name"]

        last_name = profil["last_name"]

        return (
            f"C'est noté, "
            f"{first_name} {last_name} ! ✨\n\n"
            "Votre expérience est désormais "
            "personnalisée.\n\n"
            "Vous pouvez me poser toutes vos "
            "questions météorologiques."
        )

    raise RuntimeError(
        "Étape de collecte inconnue."
    )



# ============================================================
# TRAITEMENT DES MESSAGES TEXTE WHATSAPP
# ============================================================

def process_whatsapp_text_message(
    message: WhatsAppTextMessage,
):

    """
    Traite un message texte WhatsApp.

    Le message est d'abord vérifié pour déterminer
    s'il concerne une collecte de personnalisation.

    Les autres messages sont transmis au pipeline
    conversationnel existant.
    """

    # ========================================================
    # 1. TRAITEMENT PRIORITAIRE DE LA COLLECTE
    # ========================================================

    reponse_collecte = traiter_message_collecte(
        recipient=message.sender,
        text=message.text,
    )

    if reponse_collecte is not None:

        chat_response = ChatResponse(

            success=True,

            thread_id=message.sender,

            answer=reponse_collecte,

            route="static",

            intent="personalization",

            offer_personalization=False,

            personalization_action=None,

            generation_mode="static",

            grounded=False,

            retrieval_executed=False,

            use_multimodal=False,

            sources=[],

            latency_ms=None,

            error=None,
        )

        send_whatsapp_text_message(
            recipient=message.sender,
            text=chat_response.answer,
        )

        return chat_response

    # ========================================================
    # 2. CHARGEMENT DU PROFIL UTILISATEUR
    # ========================================================

    user_preferences = (
        charger_preferences_whatsapp(
            message.sender
        )
    )

    # ========================================================
    # 3. TRAITEMENT CONVERSATIONNEL
    # ========================================================

    chat_response = process_chat(
        query=message.text,
        thread_id=message.sender,
        user_preferences=user_preferences,
    )

    # ========================================================
    # 4. ACTIONS DE PERSONNALISATION
    # ========================================================

    instruction_collecte = (
        traiter_action_personnalisation(
            recipient=message.sender,
            response=chat_response,
        )
    )

    if instruction_collecte is not None:

        chat_response.answer = (
            instruction_collecte
        )

    # ========================================================
    # 5. ENVOI DE LA RÉPONSE
    # ========================================================

    if (
        chat_response.success
        and chat_response.answer
    ):

        send_whatsapp_text_message(
            recipient=message.sender,
            text=chat_response.answer,
        )

        envoyer_proposition_si_necessaire(
            recipient=message.sender,
            response=chat_response,
        )

    return chat_response