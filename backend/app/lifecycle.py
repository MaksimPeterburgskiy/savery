"""Application lifecycle hooks."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app.config import settings
from backend.app.db import create_db_and_tables
from backend.app.migrations import upgrade_to_head

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown events for the FastAPI app."""

    logger.info("Starting %s", app.title)

    if settings.verify_schema_on_startup:
        try:
            upgrade_to_head()
        except Exception as exc:  # pragma: no cover - guard rails for misconfigured DB
            logger.error("Database migration failed: %s", exc)
            raise

    # Insert startup initialization (DB, caches, etc.) here.
    yield
    # Insert graceful shutdown logic here.
    logger.info("Stopping %s", app.title)
