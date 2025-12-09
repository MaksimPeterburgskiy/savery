from __future__ import annotations

import math
import time
from uuid import UUID

from celery import shared_task
from haversine import haversine

from backend.app.api.utils.geography import extract_point_coordinates
from backend.app.config import settings
from backend.app.db import session_scope
from backend.app.models import (
    ItemMatch,
    Job,
    OptimizationMode,
    PlanSelectedStore,
    PlanStoreVisit,
    Store,
)
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

        item_matches: list[ItemMatch] = []
        stores: list[Store] = []
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
                user_loc = extract_point_coordinates(job.plan.user_geography)
                def store_distance(s: Store) -> float:
                    store_loc = extract_point_coordinates(s.geography)
                    # We are using (long, lat) order in geography, but haversine expects (lat, long)
                    return haversine(
                        (user_loc[1], user_loc[0]), (store_loc[1], store_loc[0])
                    )
                stores = list(set(im.store for im in item_matches))
                stores.sort(key=store_distance)

            case OptimizationMode.SPEED:
                user_loc = extract_point_coordinates(job.plan.user_geography)
                def store_distance(pss: PlanSelectedStore) -> float:
                    store_loc = extract_point_coordinates(pss.store.geography)
                    # We are using (long, lat) order in geography, but haversine expects (lat, long)
                    return haversine(
                        (user_loc[1], user_loc[0]), (store_loc[1], store_loc[0])
                    )
                job.plan.selected_stores.sort(key=store_distance)
                stores = [sp.store for sp in job.plan.selected_stores]
                for list_item in job.plan.list.list_items:
                    list_item.item_matches.sort(
                        key=lambda im: stores.index(
                            im.store_product.store
                        )
                    )
                    item_matches.append(list_item.item_matches[0])

            case OptimizationMode.BALANCED:
                pass

            case _:
                raise ValueError(f"Unknown optimization mode: {job.plan.opt_mode}")

        job.plan.store_visits = [PlanStoreVisit(sequence=i, store=s) for (s, i) in stores]
        session.commit()
