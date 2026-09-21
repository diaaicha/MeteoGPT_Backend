from fastapi import (
    APIRouter,
    HTTPException,
    status,
)

from backend.app.schemas.update import (
    UpdateRequest,
    UpdateResponse,
)

from backend.app.services import (
    update_service,
)


router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
)


@router.post(
    "/update",
    response_model=UpdateResponse,
    summary="Actualiser le corpus ANACIM",
)
def update_anacim_corpus(
    payload: UpdateRequest,
) -> UpdateResponse:
    """
    Déclenche le pipeline d'actualisation des données ANACIM.

    Par défaut, l'appel est effectué en mode dry-run.
    """

    result = update_service.run_anacim_update(
        dry_run=payload.dry_run,
    )

    if result.get("status") == "disabled":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="L'actualisation ANACIM est désactivée.",
        )

    if result.get("status") == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Une erreur interne est survenue pendant "
                "l'actualisation du corpus ANACIM."
            ),
        )

    return UpdateResponse(**result)
