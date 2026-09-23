from fastapi import FastAPI

from backend.app.api.routes.health import router as health_router
from backend.app.core.config import get_settings
from backend.app.api.routes.chat import router as chat_router

from backend.app.core.logging import (
    configure_logging,
)

from backend.app.middleware.request_logging import (
    request_logging_middleware,
)

from backend.app.api.routes.admin_update import (
    router as admin_update_router,
)

from backend.app.api.routes.audio import (
    router as audio_router,
)


def create_app() -> FastAPI:
    """
    Crée et configure l'application FastAPI MeteoGPT.
    """

    settings = get_settings()

    configure_logging()

    application = FastAPI(
        title=settings.app_name,
        description=(
            "Backend applicatif de MeteoGPT."
        ),
        version="0.1.0",
        debug=settings.debug,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    application.middleware("http")(
        request_logging_middleware
    )

    application.include_router(
        health_router
    )

    application.include_router(
        chat_router,
        prefix=settings.api_v1_prefix,
    )


    application.include_router(
        audio_router,
        prefix=settings.api_v1_prefix,
    )

    application.include_router(
        admin_update_router,
        prefix=settings.api_v1_prefix,
    )

    return application


app = create_app()