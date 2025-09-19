"""Health and readiness endpoints."""

from fastapi import APIRouter

from backend.core.config import settings

router = APIRouter()


@router.get("/health", summary="Service health check")
async def health_check() -> dict[str, str]:
    """Return a simple payload confirming the service is up."""

    return {
        "status": "ok",
        "environment": settings.environment,
        "version": settings.version,
    }
