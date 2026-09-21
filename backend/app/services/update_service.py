from typing import Any, Dict

import retriever

from backend.app.core.config import (
    PROJECT_ROOT,
    get_settings,
)
from backend.app.core.logging import get_logger
from src.meteogpt_update_api_pipeline import (
    update_api_pipeline,
)


logger = get_logger("update")


def run_anacim_update(
    *,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Exécute le pipeline d'actualisation ANACIM
    puis synchronise l'index BM25 du Retriever
    lorsque le corpus a effectivement été modifié.
    """

    settings = get_settings()

    if not settings.enable_admin_update:
        return {
            "status": "disabled",
            "dry_run": dry_run,
            "update": None,
            "bm25_refresh": None,
            "error": "admin_update_disabled",
        }

    logger.info(
        "ANACIM update started | dry_run=%s",
        dry_run,
    )

    qdrant_client = None

    if not dry_run:
        qdrant_client = (
            retriever.obtenir_client_qdrant_actif()
        )

    try:

        update_result = update_api_pipeline(
            root_dir=str(PROJECT_ROOT),
            api_url=settings.anacim_api_url,
            collection_name=settings.qdrant_collection,
            dry_run=dry_run,
            qdrant_client=qdrant_client,
        )

        status = update_result.get(
            "status"
        )

        bm25_refresh = None

        if status == "success":

            bm25_refresh = (
                retriever.refresh_bm25_index()
            )

        logger.info(
            "ANACIM update completed | "
            "status=%s | "
            "dry_run=%s | "
            "bulletins_api=%s | "
            "bulletins_a_traiter=%s | "
            "new_chunks=%s",
            status,
            dry_run,
            update_result
            .get("counts", {})
            .get("bulletins_api"),
            update_result
            .get("counts", {})
            .get("bulletins_a_traiter"),
            update_result
            .get("counts", {})
            .get("new_chunks"),
        )

        return {
            "status": status,
            "dry_run": dry_run,
            "update": update_result,
            "bm25_refresh": bm25_refresh,
            "error": None,
        }

    except Exception as exc:

        logger.exception(
            "ANACIM update service failed"
        )

        return {
            "status": "error",
            "dry_run": dry_run,
            "update": None,
            "bm25_refresh": None,
            "error": str(exc),
        }