"""Application entrypoint."""

from fastapi import FastAPI

from backend.core.config import settings

from .api import api_router
from .lifecycle import lifespan


def create_app() -> FastAPI:
    """Construct the FastAPI application instance."""

    app = FastAPI(
        title=settings.project_name,
        version=settings.version,
        debug=settings.debug,
        docs_url=settings.docs_url,
        redoc_url=settings.redoc_url,
        openapi_url=settings.openapi_url,
        lifespan=lifespan,
    )

    app.include_router(api_router, prefix=settings.api_prefix)

    return app


app = create_app()
