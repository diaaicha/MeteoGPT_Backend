from fastapi import FastAPI

from backend.app.api.routes.health import router as health_router
from backend.app.core.config import get_settings


def create_app() -> FastAPI:
    """
    Crée et configure l'application FastAPI MeteoGPT.
    """

    settings = get_settings()

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

    application.include_router(
        health_router
    )

    return application


app = create_app()