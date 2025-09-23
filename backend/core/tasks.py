"""Helpers for coordinating Celery task submission and status inspection."""

from __future__ import annotations

from typing import Any

from celery import chain
from celery.result import AsyncResult

from backend.core.config import settings
from backend.workers.celery_app import celery_app

MATCHING_TASK = settings.celery_matching_task
PRICING_TASK = settings.celery_pricing_task
OPTIMIZATION_TASK = settings.celery_route_task


def _build_workflow(payload: dict[str, Any]):
    """Return the Celery canvas representing the optimization pipeline."""

    match_signature = celery_app.signature(MATCHING_TASK, kwargs={"payload": payload})
    price_signature = celery_app.signature(PRICING_TASK)
    route_signature = celery_app.signature(OPTIMIZATION_TASK)

    return chain(match_signature, price_signature, route_signature)


def enqueue_optimization_job(payload: Any) -> str:
    """Submit an optimization job to Celery and return the task identifier."""

    if hasattr(payload, "model_dump"):
        payload = payload.model_dump()

    workflow = _build_workflow(payload)
    async_result = workflow.apply_async()
    return async_result.id


def get_task_status(task_id: str) -> dict[str, Any]:
    """Return basic status information for a Celery task."""

    async_result = AsyncResult(task_id, app=celery_app)

    status_payload = {
        "id": task_id,
        "status": async_result.status,
        "ready": async_result.ready(),
        "successful": async_result.successful(),
        "result": async_result.result if async_result.ready() else None,
        "pipeline": [
            {"name": MATCHING_TASK},
            {"name": PRICING_TASK},
            {"name": OPTIMIZATION_TASK},
        ],
    }

    return status_payload
