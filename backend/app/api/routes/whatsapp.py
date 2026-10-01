from fastapi import (
    APIRouter,
    BackgroundTasks,
    HTTPException,
    Query,
    Request,
    status,
)
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

    Les messages texte valides sont extraits puis transmis
    au pipeline conversationnel en tâche d'arrière-plan.
    """

    settings = get_settings()

    if not settings.enable_whatsapp:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le service WhatsApp est désactivé.",
        )

    try:
        payload = await request.json()

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload WhatsApp invalide.",
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload WhatsApp invalide.",
        )

    text_messages = extract_text_messages(
        payload
    )

    audio_messages = extract_audio_messages(
        payload
    )

    for message in text_messages:
        background_tasks.add_task(
            process_whatsapp_text_message,
            message,
        )

    for message in audio_messages:
        background_tasks.add_task(
            process_whatsapp_audio_message,
            message,
        )

    return WhatsAppWebhookResponse(
        status="received",
        messages_received=(
            len(text_messages)
            + len(audio_messages)
        ),
    )