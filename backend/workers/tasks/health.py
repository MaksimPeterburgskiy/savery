"""Celery task that exercises the job bookkeeping end to end."""

from __future__ import annotations

import time
from uuid import UUID

from celery import shared_task

from backend.app.config import settings
from backend.app.tasks import mark_job_failed, mark_job_running, mark_job_success, record_job_progress


@shared_task(bind=True, name="workers.health.run_demo", track_started=True)
def run_demo(self, job_id: str | UUID) -> dict[str, str | int]:
    """Increment the job progress every few seconds until completion."""

    delay_seconds = max(settings.celery_demo_task_delay_seconds, 0)
    steps = [0, 20, 40, 60, 80, 100]

    try:
        # Mark the job as running and initialise the progress bar.
        mark_job_running(
            job_id,
            total=100,
            message="Health demo task started",
            task=self,
            include_status=True,
        )

        for percent in steps:
            if percent:
                # Simulate a bit of work before reporting the next milestone.
                if delay_seconds:
                    time.sleep(delay_seconds)
            record_job_progress(
                job_id,
                current=percent,
                message=f"Reached {percent}% complete",
                task=self,
                include_status=True,
            )

        mark_job_success(
            job_id,
            message="Health demo task finished",
            task=self,
            include_status=True,
        )
        return {"job_id": str(job_id), "progress": 100}
    except Exception as exc:  # noqa: BLE001 - surface the failure after recording it
        mark_job_failed(
            job_id,
            message=str(exc),
            task=self,
            include_status=True,
            extra_meta={"error": str(exc)},
        )
        raise
