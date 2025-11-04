from __future__ import annotations

import time
from uuid import UUID

from celery import shared_task

from backend.app.config import settings
from backend.app.db import session_scope
from backend.app.models import Job, OptimizationMode
from backend.app.tasks import (
    get_job_status,
    mark_job_failed,
    mark_job_running,
    mark_job_success,
    record_job_progress,
)


@shared_task(
    bind=True, name="workers.optimization.run_optimization", track_started=True
)
def run_optimization(self, job_id: str | UUID) -> dict[str, str | int]:
    """Run an optimization task, updating job progress as it proceeds."""

    delay_seconds = max(settings.celery_optimization_task_delay_seconds, 0)
    steps = [0, 25, 50, 75, 100]
    with session_scope() as session:
        job_uuid = UUID(str(job_id))
        job = session.get(Job, job_uuid)
        if job is None:
            raise ValueError(f"Job with ID {job_id} does not exist")

    match job.plan.opt_mode:
        case OptimizationMode.PRICE:
            for list_item in job.plan.list.list_items:
                list_item.qty_value
                list_item.item_matches.sort(
                    key=lambda im: im.chosen_price_entry.price * im.chosen_store_product.product.
                )
                # need 6 cucumbers, im comes in 
        case OptimizationMode.SPEED:
            pass
        case OptimizationMode.BALANCED:
            pass
        case _:
            raise ValueError(f"Unknown optimization mode: {job.plan.opt_mode}")

    try:
        # Mark the job as running and initialise the progress bar.
        mark_job_running(job_id, total=100, message="Optimization task started")
        self.update_state(state="STARTED", meta=get_job_status(job_id))

        for percent in steps:
            if percent:
                # Simulate a bit of work before reporting the next milestone.
                if delay_seconds:
                    time.sleep(delay_seconds)
            record_job_progress(
                job_id,
                current=percent,
                message=f"Optimization reached {percent}% complete",
            )
            self.update_state(state="PROGRESS", meta=get_job_status(job_id))

        mark_job_success(job_id, message="Optimization task finished successfully")
        self.update_state(state="SUCCESS", meta=get_job_status(job_id))
        return {"job_id": str(job_id), "progress": 100}
    except Exception as exc:  # noqa: BLE001 - surface the failure after recording it
        mark_job_failed(job_id, message=str(exc))
        self.update_state(state="FAILURE", meta=get_job_status(job_id))
        raise
