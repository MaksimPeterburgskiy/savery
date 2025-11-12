"""Minimal helpers for enqueuing Celery jobs and tracking their progress."""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from sqlmodel import Session

from backend.app.config import settings
from backend.app.db import session_scope
from backend.app.models import Job, JobStage, JobStatus, utcnow
from backend.workers.celery_app import celery_app


class TaskStateReporter(Protocol):
    """Minimal interface shared by bound Celery tasks we care about."""

    def update_state(self, state: str | None = None, meta: dict[str, Any] | None = None) -> None:
        """Publish state changes back to the Celery result backend."""


def _build_task_meta(job: Job, include_status: bool, extra_meta: dict[str, Any] | None) -> dict[str, Any]:
    """Return the payload that should be sent back to Celery."""

    base = serialize_job(job) if include_status else {"job_id": str(job.id)}
    if extra_meta:
        base = {**base, **extra_meta}
    return base


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
        JobStage.MATCH: settings.celery_match_task,
        JobStage.HEALTHCHECK: settings.celery_health_task,
        JobStage.FANOUT: settings.celery_fanout_task,
        
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
        job.started_at = None
        job.completed_at = None
        session.add(job)
        session.flush()

        async_result = task.delay(job_id=str(job_uuid))

        job.task_id = async_result.id
        session.add(job)

    return async_result.id


def mark_job_running(
    job_id: str | UUID,
    *,
    total: int | None = None,
    message: str | None = None,
    task: TaskStateReporter,
    include_status: bool = False,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Set the job state to RUNNING and optionally notify Celery of the update."""

    job_uuid = _as_uuid(job_id)

    with session_scope() as session:
        job = _get_job(session, job_uuid)
        job.status = JobStatus.RUNNING
        job.progress_total = total
        job.progress_current = 0 if total is not None else job.progress_current
        job.message = message
        job.started_at = utcnow()
        job.completed_at = None
        session.add(job)

        meta_payload = _build_task_meta(job, include_status, extra_meta)
        task.update_state(state="STARTED", meta=meta_payload)

    return meta_payload


def record_job_progress(
    job_id: str | UUID,
    *,
    current: int | None = None,
    total: int | None = None,
    message: str | None = None,
    task: TaskStateReporter,
    include_status: bool = False,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
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

        meta_payload = _build_task_meta(job, include_status, extra_meta)
        task.update_state(state="PROGRESS", meta=meta_payload)

    return meta_payload


def mark_job_success(
    job_id: str | UUID,
    *,
    message: str | None = None,
    task: TaskStateReporter,
    include_status: bool = False,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Mark the job as successful and optionally attach a completion message."""

    job_uuid = _as_uuid(job_id)

    with session_scope() as session:
        job = _get_job(session, job_uuid)
        job.status = JobStatus.SUCCESS
        if job.progress_total is not None:
            job.progress_current = job.progress_total
        if message is not None:
            job.message = message
        job.completed_at = utcnow()
        session.add(job)

        meta_payload = _build_task_meta(job, include_status, extra_meta)
        task.update_state(state="SUCCESS", meta=meta_payload)

    return meta_payload


def mark_job_failed(
    job_id: str | UUID,
    *,
    message: str | None = None,
    task: TaskStateReporter,
    include_status: bool = False,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Mark the job as failed and capture the error details."""

    job_uuid = _as_uuid(job_id)

    with session_scope() as session:
        job = _get_job(session, job_uuid)
        job.status = JobStatus.FAILED
        if message is not None:
            job.message = message
        job.completed_at = utcnow()
        session.add(job)

        meta_payload = _build_task_meta(job, include_status, extra_meta)
        task.update_state(state="FAILURE", meta=meta_payload)

    return meta_payload


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
        "started_at": job.started_at,
        "completed_at": job.completed_at,
    }
