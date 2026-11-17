import json
from fastapi import (
    APIRouter,
    BackgroundTasks,
    HTTPException,
    Query,
    Request,
    status,
)

import hmac
from pathlib import Path
from dotenv import dotenv_values
from fastapi.responses import PlainTextResponse

from backend.app.core.config import get_settings

from backend.app.schemas.whatsapp import (
    WhatsAppWebhookResponse,
)

from backend.app.services.whatsapp_service import (
    extract_audio_messages,
    extract_text_messages,
    process_whatsapp_audio_message,
    process_whatsapp_text_message,
    mark_whatsapp_message_if_new,
    verify_whatsapp_webhook_signature,
)


router = APIRouter(
    prefix="/whatsapp",
    tags=["WhatsApp"],
)


# ============================================================
# WEBHOOK VERIFICATION
# ============================================================

@router.get(
    "/webhook",
    response_class=PlainTextResponse,
    summary="Vérifier le webhook WhatsApp",
)
def verify_whatsapp_webhook(
    hub_mode: str | None = Query(
        default=None,
        alias="hub.mode",
    ),
    hub_verify_token: str | None = Query(
        default=None,
        alias="hub.verify_token",
    ),
    hub_challenge: str | None = Query(
        default=None,
        alias="hub.challenge",
    ),
) -> PlainTextResponse:
    """
    Vérifie le webhook utilisé par WhatsApp Cloud API.

    Meta envoie :
    - hub.mode ;
    - hub.verify_token ;
    - hub.challenge.

    Si le token reçu correspond au token configuré,
    le challenge est retourné tel quel.
    """

    settings = get_settings()

    if not settings.enable_whatsapp:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le service WhatsApp est désactivé.",
        )

    if not settings.whatsapp_verify_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Le token de vérification WhatsApp "
                "n'est pas configuré."
            ),
        )

    valid_request = (
        hub_mode == "subscribe"
        and hub_verify_token
        == settings.whatsapp_verify_token
        and bool(hub_challenge)
    )

    if not valid_request:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Échec de la vérification "
                "du webhook WhatsApp."
            ),
        )

    return PlainTextResponse(
        content=hub_challenge,
        status_code=status.HTTP_200_OK,
    )


# ============================================================
# WEBHOOK RECEIVER
# ============================================================


# ============================================================
# WEBHOOK RECEIVER
# ============================================================

@router.post(
    "/webhook",
    response_model=WhatsAppWebhookResponse,
    summary="Recevoir un webhook WhatsApp",
)
async def receive_whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> WhatsAppWebhookResponse:
    """
    Reçoit les événements envoyés par WhatsApp Cloud API.

    Vérifie obligatoirement la signature Meta avant
    de traiter les messages.

    Les messages valides sont transmis au pipeline
    conversationnel en tâche d'arrière-plan.
    """

    settings = get_settings()

    # ========================================================
    # 1. VÉRIFIER QUE WHATSAPP EST ACTIVÉ
    # ========================================================

    if not settings.enable_whatsapp:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le service WhatsApp est désactivé.",
        )

    # ========================================================
    # 2. LIRE LE CORPS BRUT DE LA REQUÊTE
    # ========================================================

    raw_payload = await request.body()

    # ========================================================
    # 3. VÉRIFIER LA CONFIGURATION META
    # ========================================================

    app_secret = str(
        getattr(
            settings,
            "whatsapp_app_secret",
            "",
        )
        or ""
    ).strip()

    if not app_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "La clé secrète de l'application Meta "
                "n'est pas configurée."
            ),
        )

        
    # ========================================================
    # DIAGNOSTIC TEMPORAIRE DE CONFIGURATION
    # ========================================================

    valeur_env = dotenv_values(
        Path.cwd() / ".env"
    ).get("WHATSAPP_APP_SECRET")

    secret_fichier = str(valeur_env or "").strip()

    print(
        "APP SECRET FASTAPI IDENTIQUE AU .ENV :",
        bool(secret_fichier)
        and hmac.compare_digest(
            app_secret,
            secret_fichier,
        ),
        flush=True,
    )

    print(
        "ENCODAGE HTTP :",
        request.headers.get(
            "content-encoding",
            "aucun",
        ),
        flush=True,
    )


    # ========================================================
    # 4. VÉRIFIER OBLIGATOIREMENT LA SIGNATURE
    # ========================================================

    signature = request.headers.get(
        "X-Hub-Signature-256"
    )


    print(
        "SIGNATURE META PRESENTE :",
        bool(signature),
        flush=True,
    )

    print(
        "FORMAT SIGNATURE CORRECT :",
        bool(
            signature
            and signature.startswith("sha256=")
            and len(signature) == 71
        ),
        flush=True,
    )

    if not verify_whatsapp_webhook_signature(
        payload=raw_payload,
        signature=signature,
        app_secret=app_secret,
    ):
        from datetime import datetime, timezone

        try:
            diagnostic = json.loads(raw_payload)
            dates = []
            champs = []

            for entry in diagnostic.get("entry", []):
                for change in entry.get("changes", []):
                    champs.append(change.get("field"))

                    value = change.get("value", {})

                    for categorie in ("messages", "statuses"):
                        for element in value.get(categorie, []):
                            timestamp = element.get("timestamp")

                            if timestamp:
                                dates.append(
                                    datetime.fromtimestamp(
                                        int(timestamp),
                                        tz=timezone.utc,
                                    ).isoformat()
                                )

            print("CHAMPS WEBHOOK REJETE :", champs[:5], flush=True)
            print("DATES EVENEMENTS UTC :", dates[:5], flush=True)

        except (ValueError, TypeError, AttributeError, OverflowError):
            print("DIAGNOSTIC EVENEMENT INDISPONIBLE", flush=True)

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Signature webhook WhatsApp invalide.",
        )

    # ========================================================
    # 5. DÉCODER LE JSON APRÈS AUTHENTIFICATION
    # ========================================================

    try:
        payload = json.loads(
            raw_payload
        )

    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload WhatsApp invalide.",
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload WhatsApp invalide.",
        )

    # ========================================================
    # 6. EXTRAIRE LES MESSAGES
    # ========================================================

    text_messages = extract_text_messages(
        payload
    )

    audio_messages = extract_audio_messages(
        payload
    )

    # ========================================================
    # 7. TRAITER LES MESSAGES TEXTE
    # ========================================================

    for message in text_messages:

        if not mark_whatsapp_message_if_new(
            message.message_id
        ):
            continue

        background_tasks.add_task(
            process_whatsapp_text_message,
            message,
        )

    # ========================================================
    # 8. TRAITER LES MESSAGES AUDIO
    # ========================================================

    for message in audio_messages:

        if not mark_whatsapp_message_if_new(
            message.message_id
        ):
            continue

        background_tasks.add_task(
            process_whatsapp_audio_message,
            message,
        )

    # ========================================================
    # 9. CONFIRMER LA RÉCEPTION À META
    # ========================================================

    return WhatsAppWebhookResponse(
        status="received",
        messages_received=(
            len(text_messages)
            + len(audio_messages)
        ),
    )
