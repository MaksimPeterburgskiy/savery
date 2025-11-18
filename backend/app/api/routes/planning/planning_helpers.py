"""Shared helpers for planning routes."""

from __future__ import annotations

from collections import defaultdict
from typing import Sequence
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from backend.app.models import PlanItem, PlanSelectedStore, PlanStoreVisit, RoutePlan, Store, StoreProduct

from .planning_schemas import PlanItemResponse, RoutePlanResponse


def _get_route_plan_or_404(session: Session, route_plan_id: UUID) -> RoutePlan:
    route_plan = session.get(RoutePlan, route_plan_id)
    if route_plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route Plan not found")
    return route_plan


def _get_plan_store_visit_or_404(session: Session, route_plan_id: UUID, plan_store_visit_id: UUID) -> PlanStoreVisit:
    """Return a plan store visit or raise 404 when it is missing or not part of the route plan."""

    plan_store_visit = session.get(PlanStoreVisit, plan_store_visit_id)
    if plan_store_visit is None or plan_store_visit.plan_id != route_plan_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan store visit not found")
    return plan_store_visit


def _get_plan_item_or_404(session: Session, route_plan_id: UUID, plan_item_id: UUID) -> PlanItem:
    """Return a plan item scoped to a route plan or raise a 404."""

    statement = (
        select(PlanItem)
        .join(PlanStoreVisit, PlanItem.plan_store_visit_id == PlanStoreVisit.id)
        .where(
            PlanItem.id == plan_item_id,
            PlanStoreVisit.plan_id == route_plan_id,
        )
        .options(
            selectinload(PlanItem.list_item),
            selectinload(PlanItem.store_product).selectinload(StoreProduct.product),
            selectinload(PlanItem.price_entry),
        )
    )
    plan_item = session.exec(statement).first()
    if plan_item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan item not found")
    return plan_item


def _fetch_plan_items_by_visit(session: Session, plan_store_visit_ids: Sequence[UUID]) -> dict[UUID, list[PlanItem]]:
    """Load plan items, grouped by plan store visit ID."""

    if not plan_store_visit_ids:
        return {}

    statement = (
        select(PlanItem)
        .where(PlanItem.plan_store_visit_id.in_(plan_store_visit_ids))
        .options(
            selectinload(PlanItem.list_item),
            selectinload(PlanItem.store_product).selectinload(StoreProduct.product),
            selectinload(PlanItem.price_entry),
        )
    )
    plan_items = session.exec(statement).all()

    grouped: dict[UUID, list[PlanItem]] = defaultdict(list)
    for plan_item in plan_items:
        grouped[plan_item.plan_store_visit_id].append(plan_item)
    return grouped


def _serialize_plan_items(plan_items: Sequence[PlanItem]) -> list[PlanItemResponse]:
    """Convert PlanItem models into API responses sorted by list position."""

    sorted_items = sorted(
        plan_items,
        key=lambda item: (
            item.list_item.position if item.list_item is not None else 0,
            item.created_at,
        ),
    )
    return [PlanItemResponse.model_validate(plan_item) for plan_item in sorted_items]


def _build_route_plan_responses(
    session: Session,
    plans: Sequence[RoutePlan],
) -> list[RoutePlanResponse]:
    """Return serialized responses with related geography in batch."""

    if not plans:
        return []

    plan_ids = [plan.id for plan in plans]

    user_geo_map: dict[UUID, str | None] = {
        plan_id: geojson for plan_id, geojson in session.exec(select(RoutePlan.id, func.ST_AsGeoJSON(RoutePlan.user_geography)).where(RoutePlan.id.in_(plan_ids)))
    }

    store_map: dict[UUID, list[tuple[Store, str | None]]] = defaultdict(list)
    selected_rows = session.exec(
        select(
            PlanSelectedStore.plan_id,
            Store,
            func.ST_AsGeoJSON(Store.geography).label("geography_geojson"),
        )
        .join(Store, PlanSelectedStore.store_id == Store.id)
        .where(PlanSelectedStore.plan_id.in_(plan_ids))
    )
    for plan_id, store, geojson in selected_rows:
        store_map[plan_id].append((store, geojson))

    return [
        RoutePlanResponse.from_model(
            plan,
            user_geo_map.get(plan.id),
            store_map.get(plan.id, []),
        )
        for plan in plans
    ]


__all__ = [
    "_build_route_plan_responses",
    "_fetch_plan_items_by_visit",
    "_get_plan_item_or_404",
    "_get_plan_store_visit_or_404",
    "_get_route_plan_or_404",
    "_serialize_plan_items",
]
