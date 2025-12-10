from __future__ import annotations

import math
import time
from decimal import Decimal
from uuid import UUID

from celery import shared_task
from haversine import haversine
from sqlalchemy import func
from sqlmodel import delete, select

from backend.app.api.utils.geography import extract_point_coordinates
from backend.app.config import settings
from backend.app.db import session_scope
from backend.app.models import (
    ItemMatch,
    Job,
    ListItem,
    OptimizationMode,
    PlanItem,
    PlanSelectedStore,
    PlanStoreVisit,
    PriceEntry,
    RoutePlan,
    Store,
    StoreProduct,
)
from backend.app.tasks import (
    mark_job_failed,
    mark_job_running,
    mark_job_success,
    record_job_progress,
)


def get_current_price(store_product: StoreProduct | None, session) -> PriceEntry | None:
    """Get the current price entry for a store product.

    Tries is_current=True first, falls back to latest by fetched_at.
    """
    if not store_product:
        return None

    # Try is_current=True first
    for entry in store_product.price_entries:
        if entry.is_current:
            return entry

    # Fallback: latest by fetched_at
    if store_product.price_entries:
        return max(store_product.price_entries, key=lambda e: e.fetched_at)

    return None


def get_item_cost(
    im: ItemMatch,
    list_item: ListItem,
    use_unit_price: bool,
    session,
) -> float:
    """Calculate cost for an item match, handling missing data gracefully.

    Returns float('inf') for items without valid prices (pushes them to end of sort).
    """
    price_entry = get_current_price(im.store_product, session)
    if not price_entry:
        return float("inf")

    # Use unit price if requested and available
    if use_unit_price and price_entry.unit_price:
        return float(price_entry.unit_price)

    # Calculate total cost based on quantity needed
    product = im.store_product.product if im.store_product else None
    base_price = float(price_entry.price)

    if product and product.base_qty_value and list_item.qty_value:
        qty_needed = math.ceil(list_item.qty_value / product.base_qty_value)
        return base_price * qty_needed

    return base_price


@shared_task(
    bind=True, name="workers.optimization.run_optimization", track_started=True
)
def run_optimization(self, job_id: str | UUID) -> dict[str, str | int]:
    """Run an optimization task, updating job progress as it proceeds."""
    
    delay_seconds = max(settings.celery_optimization_task_delay_seconds, 0)
    try:
        mark_job_running(
            job_id,
            total=100,
            message="Optimization task started",
            task=self,
            include_status=True,
        )
        
        with session_scope() as session:
            job_uuid = UUID(str(job_id))
            job = session.get(Job, job_uuid)
            if job is None:
                raise ValueError(f"Job with ID {job_id} does not exist")

            # --- Early Validation ---
            if not job.plan:
                raise ValueError(f"Job {job_id} has no associated route plan")

            if not job.plan.list or not job.plan.list.list_items:
                raise ValueError(f"Route plan {job.plan.id} has no list items to optimize")

            if not job.plan.selected_stores:
                raise ValueError(f"Route plan {job.plan.id} has no selected stores")

            # Query user_geography as GeoJSON
            user_geo_result = session.exec(
                select(func.ST_AsGeoJSON(RoutePlan.user_geography)).where(
                    RoutePlan.id == job.plan_id
                )
            ).first()
            user_loc = extract_point_coordinates(user_geo_result)

            # Validate user geography upfront
            if user_loc is None:
                raise ValueError(
                    "Route plan is missing user location geography - cannot calculate distances"
                )

            # --- Cleanup existing optimization data ---
            record_job_progress(
                job_id,
                current=5,
                message="Cleaning up previous optimization data",
                task=self,
                include_status=True,
            )

            # Delete plan items first to satisfy FK constraints, then store visits
            session.exec(
                delete(PlanItem)
                .where(
                    PlanItem.plan_store_visit_id.in_(
                        select(PlanStoreVisit.id).where(
                            PlanStoreVisit.plan_id == job.plan.id
                        )
                    )
                )
                .execution_options(synchronize_session=False)
            )

            session.exec(
                delete(PlanStoreVisit)
                .where(PlanStoreVisit.plan_id == job.plan.id)
                .execution_options(synchronize_session=False)
            )

            # Reset route plan totals
            job.plan.total_price = None
            job.plan.total_distance_m = None
            job.plan.total_travel_sec = None
            session.flush()

            if delay_seconds:
                time.sleep(delay_seconds)
            record_job_progress(
                job_id,
                current=10,
                message="Loaded job and initializing optimization",
                task=self,
                include_status=True,
            )

            item_matches: list[ItemMatch] = []
            stores: list[Store] = []

            # Pre-load store geographies as GeoJSON for distance calculations
            store_geo_rows = session.exec(
                select(Store.id, func.ST_AsGeoJSON(Store.geography))
            ).all()
            store_geo_map: dict[UUID, tuple[float, float] | None] = {
                store_id: extract_point_coordinates(geo_json)
                for store_id, geo_json in store_geo_rows
            }

            def get_store_distance(store_id: UUID) -> float:
                """Calculate distance from user to store in km."""
                store_loc = store_geo_map.get(store_id)
                if store_loc is None:
                    return float("inf")
                # We are using (long, lat) order in geography, but haversine expects (lat, long)
                return haversine((user_loc[1], user_loc[0]), (store_loc[1], store_loc[0]))

            match job.plan.opt_mode:
                case OptimizationMode.PRICE:
                    record_job_progress(
                        job_id,
                        current=15,
                        message="Evaluating PRICE mode - finding cheapest options",
                        task=self,
                        include_status=True,
                    )

                    for list_item in job.plan.list.list_items:
                        if not list_item.item_matches:
                            continue  # Will be handled as unmatched item

                        # Filter to item matches with available prices
                        valid_matches = [
                            im
                            for im in list_item.item_matches
                            if im.store_product
                            and get_current_price(im.store_product, session)
                        ]

                        if not valid_matches:
                            # No priced matches - use first available match
                            if list_item.item_matches:
                                item_matches.append(list_item.item_matches[0])
                            continue

                        # Sort by price (cheapest first), tie-break by store distance
                        valid_matches.sort(
                            key=lambda im, li=list_item: (
                                get_item_cost(im, li, job.plan.lowest_unit_price, session),
                                get_store_distance(im.store_id)
                                if im.store_id in store_geo_map
                                else float("inf"),
                            )
                        )
                        item_matches.append(valid_matches[0])

                    # Collect unique stores from selected matches
                    seen_store_ids: set[UUID] = set()
                    stores = []
                    for im in item_matches:
                        if im.store and im.store_id not in seen_store_ids:
                            stores.append(im.store)
                            seen_store_ids.add(im.store_id)

                    # Sort stores by distance from user for visit ordering
                    stores.sort(key=lambda s: get_store_distance(s.id))

                case OptimizationMode.SPEED:
                    record_job_progress(
                        job_id,
                        current=15,
                        message="Evaluating SPEED mode - prioritizing closest stores",
                        task=self,
                        include_status=True,
                    )

                    # Sort selected stores by distance (closest first)
                    sorted_stores = sorted(
                        job.plan.selected_stores,
                        key=lambda pss: get_store_distance(pss.store_id),
                    )
                    store_order = {
                        pss.store_id: idx for idx, pss in enumerate(sorted_stores)
                    }

                    for list_item in job.plan.list.list_items:
                        if not list_item.item_matches:
                            continue

                        # Filter to matches at selected stores only
                        valid_matches = [
                            im
                            for im in list_item.item_matches
                            if im.store_id in store_order
                        ]

                        if not valid_matches:
                            # Fallback: use any available match
                            if list_item.item_matches:
                                item_matches.append(list_item.item_matches[0])
                            continue

                        # Sort by store distance order (closest store first)
                        # Tie-break by price if available
                        valid_matches.sort(
                            key=lambda im, li=list_item: (
                                store_order.get(im.store_id, 999),
                                get_item_cost(im, li, False, session),
                            )
                        )
                        item_matches.append(valid_matches[0])

                    # Stores are those with selected items, in distance order
                    used_store_ids = {im.store_id for im in item_matches}
                    stores = [
                        pss.store
                        for pss in sorted_stores
                        if pss.store_id in used_store_ids
                    ]

                case OptimizationMode.BALANCED:
                    record_job_progress(
                        job_id,
                        current=15,
                        message="Evaluating BALANCED mode - optimizing price and distance",
                        task=self,
                        include_status=True,
                    )

                    # Calculate distance for each selected store
                    store_distances = {
                        pss.store_id: get_store_distance(pss.store_id)
                        for pss in job.plan.selected_stores
                    }
                    max_distance = max(store_distances.values()) if store_distances else 1

                    for list_item in job.plan.list.list_items:
                        valid_matches = [
                            im
                            for im in list_item.item_matches
                            if im.store_product and im.store_id in store_distances
                        ]

                        if not valid_matches:
                            if list_item.item_matches:
                                item_matches.append(list_item.item_matches[0])
                            continue

                        # Get price range for normalization
                        prices = [
                            get_item_cost(im, list_item, False, session)
                            for im in valid_matches
                        ]
                        prices = [p for p in prices if p != float("inf")]

                        if not prices:
                            item_matches.append(valid_matches[0])
                            continue

                        min_price = min(prices)
                        max_price = max(prices)
                        price_range = max_price - min_price if max_price > min_price else 1

                        def balanced_score(
                            im: ItemMatch,
                            li: ListItem = list_item,
                            min_p: float = min_price,
                            pr: float = price_range,
                            max_d: float = max_distance,
                            sd: dict = store_distances,
                        ) -> float:
                            """Calculate balanced score: 50% price + 50% distance."""
                            price = get_item_cost(im, li, False, session)
                            norm_price = (price - min_p) / pr if price != float("inf") else 1.0
                            norm_distance = sd.get(im.store_id, max_d) / max_d
                            return 0.5 * norm_price + 0.5 * norm_distance

                        valid_matches.sort(key=balanced_score)
                        item_matches.append(valid_matches[0])

                    # Collect unique stores from selected matches
                    seen_store_ids: set[UUID] = set()
                    stores = []
                    for im in item_matches:
                        if im.store and im.store_id not in seen_store_ids:
                            stores.append(im.store)
                            seen_store_ids.add(im.store_id)
                    stores.sort(key=lambda s: get_store_distance(s.id))

                case _:
                    raise ValueError(f"Unknown optimization mode: {job.plan.opt_mode}")

            # --- Enforce max_stores constraint ---
            record_job_progress(
                job_id,
                current=30,
                message="Enforcing max_stores constraint",
                task=self,
                include_status=True,
            )

            max_stores = job.plan.max_stores or 3
            if len(stores) > max_stores:
                # Keep only the first N stores (already sorted by distance)
                allowed_stores = set(s.id for s in stores[:max_stores])

                # Re-select item matches - ALWAYS fulfill all items by reassigning to allowed stores
                final_matches = []
                for im in item_matches:
                    if im.store_id in allowed_stores:
                        final_matches.append(im)
                    else:
                        # Must find alternative at allowed store (fulfilling all items is priority)
                        list_item = im.list_item
                        alt = next(
                            (
                                m
                                for m in list_item.item_matches
                                if m.store_id in allowed_stores and m.store_product
                            ),
                            None,
                        )
                        if alt:
                            final_matches.append(alt)
                        else:
                            # No alternative found - keep original (expands store list)
                            # This ensures we never drop items
                            final_matches.append(im)
                            allowed_stores.add(im.store_id)

                item_matches = final_matches
                # Rebuild stores list from what we actually need
                stores = [s for s in stores if s.id in allowed_stores]

            if delay_seconds:
                time.sleep(delay_seconds)

            # --- Create PlanStoreVisit and PlanItem records ---
            record_job_progress(
                job_id,
                current=50,
                message="Building store visits and plan items",
                task=self,
                include_status=True,
            )

            # Create store visits with sequence and travel metrics
            store_to_visit: dict[UUID, PlanStoreVisit] = {}
            prev_loc = user_loc
            total_distance = 0
            total_time = 0

            for idx, store in enumerate(stores, start=1):
                store_loc = store_geo_map.get(store.id)
                distance_m = 0
                travel_sec = 0

                if prev_loc and store_loc:
                    # Calculate distance in meters (haversine returns km)
                    dist_km = haversine(
                        (prev_loc[1], prev_loc[0]), (store_loc[1], store_loc[0])
                    )
                    distance_m = int(dist_km * 1000)
                    # Estimate travel time: ~40 km/h average speed
                    travel_sec = int((dist_km / 40) * 3600)

                visit = PlanStoreVisit(
                    plan_id=job.plan_id,
                    store_id=store.id,
                    sequence=idx,
                    distance_m_from_prev=distance_m,
                    travel_sec_from_prev=travel_sec,
                )
                session.add(visit)
                store_to_visit[store.id] = visit

                total_distance += distance_m
                total_time += travel_sec
                prev_loc = store_loc

            session.flush()  # Get visit IDs

            record_job_progress(
                job_id,
                current=70,
                message="Creating plan items with prices",
                task=self,
                include_status=True,
            )

            # Create plan items
            total_price = Decimal("0")
            for im in item_matches:
                visit = store_to_visit.get(im.store_id)
                if not visit:
                    continue

                price_entry = get_current_price(im.store_product, session)
                list_item = im.list_item
                qty = 1
                per_qty_price = (
                    Decimal(price_entry.price) if price_entry else None
                )
                extended_price = (
                    per_qty_price * qty if per_qty_price is not None else None
                )

                plan_item = PlanItem(
                    plan_store_visit_id=visit.id,
                    list_item_id=im.list_item_id,
                    store_product_id=im.store_product_id,
                    price_entry_id=price_entry.id if price_entry else None,
                    qty=qty,
                    per_qty_price=per_qty_price,
                    extended_price=extended_price,
                )
                session.add(plan_item)

                if extended_price is not None:
                    total_price += extended_price

            session.flush()

            record_job_progress(
                job_id,
                current=85,
                message="Calculating subtotals and updating route plan",
                task=self,
                include_status=True,
            )

            # Calculate subtotals per visit
            for visit in store_to_visit.values():
                session.refresh(visit)  # Reload to get plan_items relationship
                subtotal = sum(
                    Decimal(pi.extended_price)
                    if pi.extended_price is not None
                    else Decimal("0")
                    for pi in visit.plan_items
                )
                visit.subtotal_price = subtotal

            # Update route plan totals and status
            job.plan.total_price = total_price
            job.plan.total_distance_m = total_distance
            job.plan.total_travel_sec = total_time
            job.plan.status = "optimized"

            session.commit()

        if delay_seconds:
            time.sleep(delay_seconds)
        record_job_progress(
            job_id,
            current=100,
            message="Optimization task completed",
            task=self,
            include_status=True,
        )

        mark_job_success(
            job_id,
            message="Optimization task finished",
            task=self,
            include_status=True,
        )
        return {"job_id": str(job_id), "progress": 100}
    except Exception as exc:
        mark_job_failed(
            job_id,
            message=str(exc),
            task=self,
            include_status=True,
            extra_meta={"error": str(exc)},
            exc=exc,
        )
        raise
