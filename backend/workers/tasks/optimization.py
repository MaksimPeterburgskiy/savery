from __future__ import annotations

import math
import time
from uuid import UUID

from celery import shared_task

from backend.app.config import settings
from backend.app.db import session_scope
from backend.app.models import ItemMatch, Job, OptimizationMode, PlanStoreVisit
from backend.app.tasks import (
    get_job_status,
    mark_job_failed,
    mark_job_running,
    mark_job_success,
    record_job_progress,
)
from backend.app.api.utils.geography import extract_point_coordinates


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

        item_matches: list[ItemMatch] = []
        match job.plan.opt_mode:
            case OptimizationMode.PRICE:
                for list_item in job.plan.list.list_items:
                    list_item.item_matches.sort(
                        key=lambda im: (
                            im.chosen_price_entry.unit_price
                            if job.plan.lowest_unit_price
                            else im.chosen_price_entry.price
                            * math.ceil(
                                list_item.qty_value
                                / im.chosen_store_product.product.base_qty_value
                            )
                        )
                    )
                    item_matches.append(list_item.item_matches[0])

            case OptimizationMode.SPEED:
                # TODO: order selected stores by distance from user (need lat and long for proper calc)
                user_loc = extract_point_coordinates(job.plan.user_geography)
                # TODO: sort stores by distance from user location, using haversine formula. need to extract point coords from each store geography
                job.plan.selected_stores.sort(
                    key=lambda sp: math.abs(user_loc[0] - sp.store.geography)
                )
                stores = [sp.store for sp in job.plan.selected_stores]
                for list_item in job.plan.list.list_items:
                    list_item.item_matches.sort(
                        key=lambda im: job.plan.selected_stores.index(
                            im.chosen_store_product.store
                        )
                    )
                    item_matches.append(list_item.item_matches[0])
                pass

            case OptimizationMode.BALANCED:
                pass

            case _:
                raise ValueError(f"Unknown optimization mode: {job.plan.opt_mode}")

        # TODO: optimize stores visit order; for now, just make sure all stores are included
        # need to rework a lot; need to ensure all items for each store are assoc., probably use dict[store_id, PlanStoreVisit]
        job.plan.store_visits = list(
            set(
                [
                    PlanStoreVisit(sequence=i, store=im.store)
                    for i, im in enumerate(item_matches)
                ]
            )
        )
        session.commit()
