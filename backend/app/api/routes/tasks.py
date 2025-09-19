"""Endpoints for querying background task state."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.models import TaskStatusResponse
from backend.core.tasks import get_task_status

router = APIRouter()


@router.get(
    "/tasks/{task_id}",
    response_model=TaskStatusResponse,
    summary="Inspect a background task",
)
async def read_task_status(task_id: str) -> TaskStatusResponse:
    """Return the current status for a Celery task identifier."""

    status_payload = get_task_status(task_id)
    return TaskStatusResponse(**status_payload)
