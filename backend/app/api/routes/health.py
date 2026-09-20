from fastapi import APIRouter

from backend.app.core.config import get_settings


router = APIRouter(
    tags=["Health"],
)


@router.get(
    "/health",
    summary="Vérifier l'état du backend",
)
def health_check():
    """
    Vérification légère de disponibilité du backend.

    Cet endpoint ne teste pas encore :
    - Gemini ;
    - Qdrant ;
    - le Retriever ;
    - WhatsApp ;
    - l'API ANACIM.

    Il vérifie uniquement que l'application FastAPI
    fonctionne correctement.
    """

    settings = get_settings()

    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
    }