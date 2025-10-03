"""Application lifecycle hooks."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.core.config import settings
from backend.core.migrations import ensure_database_revision

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown events for the FastAPI app."""

    logger.info("Starting %s", app.title)

    if settings.verify_schema_on_startup:
        try:
            ensure_database_revision()
        except Exception as exc:  # pragma: no cover - guard rails for misconfigured DB
            logger.error("Database schema check failed: %s", exc)
            raise

    # Insert startup initialization (DB, caches, etc.) here.
    yield
    # Insert graceful shutdown logic here.
    logger.info("Stopping %s", app.title)
