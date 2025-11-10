"""Celery task that performs item matching for a route plan job."""

from __future__ import annotations

from uuid import UUID

from celery import shared_task

from backend.app.tasks import mark_job_failed, mark_job_running, mark_job_success


@shared_task(bind=True, name="workers.item_matches.run_job", track_started=True)
def run_item_match_job(self, job_id: str | UUID) -> dict[str, str]:
    """Entry point for the item match worker job.

    The heavy lifting for generating match candidates will live here. For now the
    task marks the job as running and immediately succeeds to ensure the API can
    enqueue work and the progress plumbing stays exercised end to end.
    """

    try:
        mark_job_running(job_id, message="Item matching task started", task=self)

        mark_job_success(job_id, message="Item matching task completed", task=self)
        return {"job_id": str(job_id)}
    except Exception as exc:  # noqa: BLE001 - propagate after recording failure
        mark_job_failed(
            job_id,
            message=str(exc),
            task=self,
            extra_meta={"error": str(exc)},
        )
        raise
