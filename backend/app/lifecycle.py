"""Application lifecycle hooks."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.core.db import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown events for the FastAPI app."""

    logger.info("Starting %s", app.title)

    try:
        init_db()
    except RuntimeError as exc:  # pragma: no cover - only hit without SQLAlchemy installed
        logger.warning("Skipping database initialization: %s", exc)

    # Insert startup initialization (DB, caches, etc.) here.
    yield
    # Insert graceful shutdown logic here.
    logger.info("Stopping %s", app.title)
