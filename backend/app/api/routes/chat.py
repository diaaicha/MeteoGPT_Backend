from fastapi import (
    APIRouter,
    HTTPException,
    status,
)

from backend.app.schemas.chat import (
    ChatRequest,
    ChatResponse,
)

from backend.app.services import (
    chat_service,
)


router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post(
    "",
    response_model=ChatResponse,
    summary="Envoyer un message à MeteoGPT",
)
def chat(
    payload: ChatRequest
) -> ChatResponse:
    """
    Traite une requête textuelle MeteoGPT.

    L'endpoint transmet la requête au pipeline RAG
    puis retourne une réponse publique simplifiée.
    """

    try:

        return chat_service.process_chat(
            query=payload.query,
            thread_id=payload.thread_id,
            user_preferences=
                payload.user_preferences,
        )

    except Exception as exc:

        raise HTTPException(
            status_code=
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Une erreur interne est survenue "
                "pendant le traitement de la requête."
            ),
        ) from exc