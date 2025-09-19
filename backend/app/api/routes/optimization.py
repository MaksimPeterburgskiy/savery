"""Route handlers for submitting optimization requests."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, status

from backend.app.dependencies import get_db
from backend.app.models import OptimizationRequest, OptimizationResponse
from backend.core.config import settings
from backend.core.tasks import enqueue_optimization_job

router = APIRouter()


@router.post(
    "/optimize",
    response_model=OptimizationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue a shopping route optimization job",
)
async def request_optimization(
    payload: OptimizationRequest,
    db_session: Any = Depends(get_db),
) -> OptimizationResponse:
    """Accept an optimization request, enqueue it, and return a task identifier."""

    # The DB session is reserved for later persistence once the storage layer is active.
    _ = db_session

    task_id = enqueue_optimization_job(payload)

    base_url = settings.task_status_base_url
    if base_url:
        status_url = f"{base_url.rstrip('/')}/{task_id}"
    else:
        status_url = f"{settings.api_prefix}/tasks/{task_id}"

    return OptimizationResponse(task_id=task_id, status_url=status_url)
