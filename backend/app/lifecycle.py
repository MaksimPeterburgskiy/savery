"""Application lifecycle hooks."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis

from backend.app.config import settings
from backend.app.db import create_db_and_tables
from backend.app.migrations import upgrade_to_head
from backend.app.task_status import job_status_manager

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

    if settings.celery_result_backend.startswith(("redis://", "rediss://")):
        try:
            async with Redis.from_url(settings.celery_result_backend) as redis_client:
                await redis_client.ping()
        except Exception as exc:
            logger.error("Failed to connect to Redis result backend: %s", exc)
            raise

    await job_status_manager.start()

    try:
        yield
    finally:
        await job_status_manager.stop()
    logger.info("Stopping %s", app.title)
