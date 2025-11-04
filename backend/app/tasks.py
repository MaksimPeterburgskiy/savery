"""Minimal helpers for enqueuing Celery jobs and tracking their progress."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlmodel import Session

from backend.app.config import settings
from backend.app.db import session_scope
from backend.app.models import Job, JobStage, JobStatus
from backend.workers.celery_app import celery_app


def _as_uuid(value: str | UUID) -> UUID:
    """Normalize string or UUID inputs so we can work with a consistent type."""

    return value if isinstance(value, UUID) else UUID(str(value))


def _get_job(session: Session, job_id: UUID) -> Job:
    """Fetch the job row or raise a ValueError if it does not exist."""

    job = session.get(Job, job_id)
    if job is None:
        raise ValueError(f"Job {job_id} was not found")
    return job


def _task_name_for_stage(stage: JobStage) -> str:
    """Translate a stage enum to the Celery task name configured for it."""

    stage_map: dict[JobStage, str] = {
        JobStage.HEALTHCHECK: settings.celery_health_task,
    }
    task_name = stage_map.get(stage)
    if not task_name:
        raise ValueError(f"Job stage {stage} does not map to a Celery task")
    return task_name


def enqueue_job(job_id: str | UUID) -> str:
    """Send the Celery task for the job and store the generated task identifier."""

    job_uuid = _as_uuid(job_id)

    with session_scope() as session:
        job = _get_job(session, job_uuid)
        task_name = _task_name_for_stage(job.stage)
        task = celery_app.tasks.get(task_name)
        if task is None:
            celery_app.autodiscover_tasks(["backend.workers"], force=True)
            task = celery_app.tasks.get(task_name)
        if task is None:
            raise ValueError(f"Celery task {task_name} is not registered")

        job.status = JobStatus.PENDING
        job.progress_current = 0
        job.message = None
        session.add(job)
        session.flush()

        async_result = task.delay(job_id=str(job_uuid))

        job.task_id = async_result.id
        session.add(job)

    return async_result.id


def mark_job_running(job_id: str | UUID, *, total: int | None = None, message: str | None = None) -> None:
    """Set the job state to RUNNING and optionally record the total units of work."""

    job_uuid = _as_uuid(job_id)

    with session_scope() as session:
        job = _get_job(session, job_uuid)
        job.status = JobStatus.RUNNING
        job.progress_total = total
        job.progress_current = 0 if total is not None else job.progress_current
        job.message = message
        session.add(job)


def record_job_progress(
    job_id: str | UUID,
    *,
    current: int | None = None,
    total: int | None = None,
    message: str | None = None,
) -> None:
    """Update the current progress counters for the job."""

    job_uuid = _as_uuid(job_id)

    with session_scope() as session:
        job = _get_job(session, job_uuid)
        if total is not None:
            job.progress_total = total
        if current is not None:
            job.progress_current = current
        if message is not None:
            job.message = message
        session.add(job)


def mark_job_success(job_id: str | UUID, *, message: str | None = None) -> None:
    """Mark the job as successful and optionally attach a completion message."""

    job_uuid = _as_uuid(job_id)

    with session_scope() as session:
        job = _get_job(session, job_uuid)
        job.status = JobStatus.SUCCESS
        if job.progress_total is not None:
            job.progress_current = job.progress_total
        if message is not None:
            job.message = message
        session.add(job)


def mark_job_failed(job_id: str | UUID, *, message: str | None = None) -> None:
    """Mark the job as failed and capture the error details."""

    job_uuid = _as_uuid(job_id)

    with session_scope() as session:
        job = _get_job(session, job_uuid)
        job.status = JobStatus.FAILED
        if message is not None:
            job.message = message
        session.add(job)


def get_job_status(job_id: str | UUID) -> dict[str, Any]:
    """Return a dictionary of the current job fields for API responses."""

    job_uuid = _as_uuid(job_id)

    with session_scope() as session:
        job = _get_job(session, job_uuid)
        payload = serialize_job(job)

    return payload


def serialize_job(job: Job) -> dict[str, Any]:
    """Convert a job instance to a JSON-friendly payload."""

    return {
        "id": str(job.id),
        "plan_id": str(job.plan_id),
        "stage": job.stage.value if isinstance(job.stage, JobStage) else job.stage,
        "status": job.status.value if isinstance(job.status, JobStatus) else job.status,
        "progress_current": job.progress_current,
        "progress_total": job.progress_total,
        "task_id": job.task_id,
        "message": job.message,
    }
