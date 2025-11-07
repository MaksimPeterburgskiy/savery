"""Health and readiness endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlmodel import Session

from backend.app.config import settings
from backend.app.dependencies import get_db
from backend.app.models import Job, JobStage
from backend.app.tasks import enqueue_job, get_job_status


router = APIRouter()


class JobStatusResponse(BaseModel):
    """Payload returned when reporting the progress of a job."""

    model_config = ConfigDict(from_attributes=False)

    id: UUID
    plan_id: UUID
    stage: str
    status: str
    progress_current: int | None = None
    progress_total: int | None = None
    task_id: str | None = None
    message: str | None = None


class DemoTaskRequest(BaseModel):
    """Request body for triggering the demo health task."""

    job_id: UUID


@router.get("/health", summary="Service health check")
def health_check() -> dict[str, str]:
    """Return a simple payload confirming the service is up."""

    return {
        "status": "ok",
        "environment": settings.environment,
        "version": settings.version,
    }


@router.post(
    "/health/demo-task",
    response_model=JobStatusResponse,
    summary="Kick off the demo health Celery task",
)
def trigger_demo_task(
    payload: DemoTaskRequest,
    session: Session = Depends(get_db),
) -> JobStatusResponse:
    """Force the provided job into the health stage and enqueue the worker task."""

    job = session.get(Job, payload.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    job.stage = JobStage.HEALTHCHECK
    session.add(job)
    session.commit()

    enqueue_job(job.id)
    status_payload = get_job_status(job.id)
    return JobStatusResponse(**status_payload)


@router.get(
    "/health/demo-task/{job_id}",
    response_model=JobStatusResponse,
    summary="Retrieve the latest status for a demo health task",
)
def get_demo_task_status(job_id: UUID) -> JobStatusResponse:
    """Return the persisted job state if it exists."""

    try:
        status_payload = get_job_status(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return JobStatusResponse(**status_payload)
