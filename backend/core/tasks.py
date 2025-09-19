"""Helpers for coordinating Celery task submission and status inspection."""

from __future__ import annotations

from typing import Any

from celery.result import AsyncResult

from backend.core.config import settings
from backend.workers.celery_app import celery_app

OPTIMIZATION_TASK = settings.celery_route_task


def enqueue_optimization_job(payload: Any) -> str:
    """Submit an optimization job to Celery and return the task identifier."""

    if hasattr(payload, "model_dump"):
        payload = payload.model_dump()

    async_result = celery_app.send_task(OPTIMIZATION_TASK, kwargs={"payload": payload})
    return async_result.id


def get_task_status(task_id: str) -> dict[str, Any]:
    """Return basic status information for a Celery task."""

    async_result = AsyncResult(task_id, app=celery_app)

    return {
        "id": task_id,
        "status": async_result.status,
        "ready": async_result.ready(),
        "successful": async_result.successful(),
        "result": async_result.result if async_result.ready() else None,
    }
