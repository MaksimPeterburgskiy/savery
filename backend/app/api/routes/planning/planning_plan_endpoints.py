"""Planning endpoints for route plans, selections, visits, and items."""

from __future__ import annotations

from typing import Sequence
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from geoalchemy2 import WKTElement
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from backend.app.api.routes.catalog.catalog_schemas import StoreResponse
from backend.app.dependencies import get_db
from backend.app.models import PlanSelectedStore, PlanStoreVisit, RoutePlan, ShoppingList, Store, utcnow

from .planning_helpers import (
    _build_route_plan_responses,
    _fetch_plan_items_by_visit,
    _get_plan_item_or_404,
    _get_plan_store_visit_or_404,
    _get_route_plan_or_404,
    _serialize_plan_items,
)
from .planning_schemas import PlanItemResponse, PlanItemUpdate, PlanStoreVisitResponse, RoutePlanCreate, RoutePlanResponse, RoutePlanUpdate, SelectedStoreCreate

router = APIRouter()


@router.post(
    "/shopping-lists/{shopping_list_id}/route-plans",
    response_model=RoutePlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a route plan for a shopping list",
)
def create_route_plan_for_list(
    shopping_list_id: UUID,
    payload: RoutePlanCreate,
    session: Session = Depends(get_db),
) -> RoutePlanResponse:
    """Create a route plan for a given shopping list."""

    shopping_list = session.get(ShoppingList, shopping_list_id)
    if shopping_list is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shopping list not found")

    client_id = payload.client_id or shopping_list.client_id
    if client_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="client_id is required when the shopping list has no client identifier",
        )

    route_plan = RoutePlan(
        list_id=shopping_list_id,
        client_id=client_id,
        status=payload.status.value,
        opt_mode=payload.opt_mode,
        lowest_unit_price=payload.lowest_unit_price,
        max_stores=payload.max_stores,
        total_price=None,
        total_distance_m=None,
        total_travel_sec=None,
    )

    if payload.user_longitude is not None and payload.user_latitude is not None:
        route_plan.user_geography = WKTElement(
            f"POINT({payload.user_longitude} {payload.user_latitude})",
            srid=4326,
        )

    session.add(route_plan)

    if payload.selected_store_ids:
        stores = session.exec(select(Store.id).where(Store.id.in_(payload.selected_store_ids))).all()
        existing_store_ids = set(stores)
        missing = set(payload.selected_store_ids) - existing_store_ids
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"message": "Store(s) not found", "missing_store_ids": [str(sid) for sid in missing]},
            )
        seen: set[UUID] = set()
        for store_id in payload.selected_store_ids:
            if store_id in seen:
                continue
            seen.add(store_id)
            session.add(PlanSelectedStore(plan=route_plan, store_id=store_id))

    session.commit()
    session.refresh(route_plan)

    responses = _build_route_plan_responses(session, [route_plan])
    return responses[0]


@router.get(
    "/shopping-lists/{shopping_list_id}/route-plans",
    response_model=list[RoutePlanResponse],
    summary="Get route plans for a shopping list",
)
def get_routes_for_list(
    shopping_list_id: UUID,
    session: Session = Depends(get_db),
) -> list[RoutePlanResponse]:
    """Return all route plans associated with a shopping list."""

    plans = session.exec(select(RoutePlan).where(RoutePlan.list_id == shopping_list_id)).all()
    return _build_route_plan_responses(session, plans)


@router.get(
    "/route-plans/{route_plan_id}",
    response_model=RoutePlanResponse,
    summary="Get a route plan by ID",
)
def get_route_plan_by_id(
    route_plan_id: UUID,
    session: Session = Depends(get_db),
) -> RoutePlanResponse:
    """Return a single route plan by ID."""

    route_plan = session.get(RoutePlan, route_plan_id)
    if route_plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route plan not found")

    responses = _build_route_plan_responses(session, [route_plan])
    return responses[0]


@router.patch(
    "/route-plans/{route_plan_id}",
    response_model=RoutePlanResponse,
    summary="Update a route plan",
)
def update_route_plan(
    route_plan_id: UUID,
    payload: RoutePlanUpdate,
    session: Session = Depends(get_db),
) -> RoutePlanResponse:
    """Update mutable fields on a route plan."""

    route_plan = session.get(RoutePlan, route_plan_id)
    if route_plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route plan not found")

    updates = payload.model_dump(exclude_unset=True)

    if "status" in updates:
        route_plan.status = updates["status"].value
    if updates.get("opt_mode") is not None:
        route_plan.opt_mode = updates["opt_mode"]
    if "lowest_unit_price" in updates:
        route_plan.lowest_unit_price = updates["lowest_unit_price"]
    if updates.get("max_stores") is not None:
        route_plan.max_stores = updates["max_stores"]
    if "total_price" in updates:
        route_plan.total_price = updates["total_price"]
    if "total_distance_m" in updates:
        route_plan.total_distance_m = updates["total_distance_m"]
    if "total_travel_sec" in updates:
        route_plan.total_travel_sec = updates["total_travel_sec"]

    if "user_longitude" in updates or "user_latitude" in updates:
        lon = updates.get("user_longitude")
        lat = updates.get("user_latitude")
        if lon is None and lat is None:
            route_plan.user_geography = None
        elif lon is not None and lat is not None:
            route_plan.user_geography = WKTElement(f"POINT({lon} {lat})", srid=4326)

    session.add(route_plan)
    session.commit()
    session.refresh(route_plan)

    responses = _build_route_plan_responses(session, [route_plan])
    return responses[0]


@router.delete(
    "/route-plans/{route_plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Delete a route plan",
)
def delete_route_plan(
    route_plan_id: UUID,
    session: Session = Depends(get_db),
) -> None:
    """Delete a route plan and its dependent selections."""

    route_plan = session.get(RoutePlan, route_plan_id)
    if route_plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route plan not found")

    session.delete(route_plan)
    session.commit()


@router.post(
    "/route-plans/{route_plan_id}/selected-stores",
    response_model=RoutePlanResponse,
    summary="Add a selected store to a route plan",
)
def add_selected_store(
    route_plan_id: UUID,
    payload: SelectedStoreCreate,
    session: Session = Depends(get_db),
) -> RoutePlanResponse:
    """Attach a store to the selected stores collection."""

    route_plan = session.get(RoutePlan, route_plan_id)
    if route_plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route plan not found")

    store = session.get(Store, payload.store_id)
    if store is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")

    selection = PlanSelectedStore(plan_id=route_plan.id, store_id=store.id)
    session.add(selection)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Store already selected for this plan") from exc

    session.refresh(route_plan)
    responses = _build_route_plan_responses(session, [route_plan])
    return responses[0]


@router.delete(
    "/route-plans/{route_plan_id}/selected-stores/{store_id}",
    response_model=RoutePlanResponse,
    summary="Remove a selected store from a route plan",
)
def remove_selected_store(
    route_plan_id: UUID,
    store_id: UUID,
    session: Session = Depends(get_db),
) -> RoutePlanResponse:
    """Detach a store from a route plan's selections."""

    route_plan = session.get(RoutePlan, route_plan_id)
    if route_plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route plan not found")

    selection = session.exec(
        select(PlanSelectedStore).where(
            PlanSelectedStore.plan_id == route_plan.id,
            PlanSelectedStore.store_id == store_id,
        )
    ).first()
    if selection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Selected store not found for this plan")

    session.delete(selection)
    session.commit()
    session.refresh(route_plan)

    responses = _build_route_plan_responses(session, [route_plan])
    return responses[0]


@router.get(
    "/route-plans/{route_plan_id}/plan-store-visits",
    response_model=Sequence[PlanStoreVisitResponse],
    summary="List plan store visits for a route plan",
)
def list_plan_store_visits(
    route_plan_id: UUID,
    db: Session = Depends(get_db),
) -> Sequence[PlanStoreVisitResponse]:
    _get_route_plan_or_404(db, route_plan_id)

    statement = (
        select(
            PlanStoreVisit,
            Store,
            func.ST_AsGeoJSON(Store.geography).label("geography_geojson"),
        )
        .join(Store, PlanStoreVisit.store_id == Store.id)
        .where(PlanStoreVisit.plan_id == route_plan_id)
        .order_by(PlanStoreVisit.sequence.asc())
    )
    rows = db.exec(statement).all()
    visit_ids = [visit.id for visit, _, _ in rows]
    plan_items_map = _fetch_plan_items_by_visit(db, visit_ids)

    responses: list[PlanStoreVisitResponse] = []
    for visit, store, geography_geojson in rows:
        responses.append(
            PlanStoreVisitResponse(
                id=visit.id,
                plan_id=visit.plan_id,
                store=StoreResponse.from_model(store, geography_geojson),
                sequence=visit.sequence,
                travel_sec_from_prev=visit.travel_sec_from_prev,
                distance_m_from_prev=visit.distance_m_from_prev,
                subtotal_price=float(visit.subtotal_price) if visit.subtotal_price is not None else None,
                plan_items=_serialize_plan_items(plan_items_map.get(visit.id, [])),
            )
        )

    return responses


@router.get(
    "/route-plans/{route_plan_id}/plan-store-visits/{plan_store_visit_id}/plan-items",
    response_model=Sequence[PlanItemResponse],
    summary="List plan items for a store visit",
)
def list_plan_items_for_visit(
    route_plan_id: UUID,
    plan_store_visit_id: UUID,
    db: Session = Depends(get_db),
) -> Sequence[PlanItemResponse]:
    _get_plan_store_visit_or_404(db, route_plan_id, plan_store_visit_id)

    plan_items_map = _fetch_plan_items_by_visit(db, [plan_store_visit_id])
    return _serialize_plan_items(plan_items_map.get(plan_store_visit_id, []))


@router.patch(
    "/route-plans/{route_plan_id}/plan-items/{plan_item_id}",
    response_model=PlanItemResponse,
    summary="Update plan item checklist status",
)
def update_plan_item_checked_status(
    route_plan_id: UUID,
    plan_item_id: UUID,
    payload: PlanItemUpdate,
    db: Session = Depends(get_db),
) -> PlanItemResponse:
    plan_item = _get_plan_item_or_404(db, route_plan_id, plan_item_id)

    plan_item.is_checked = payload.is_checked
    plan_item.checked_at = utcnow() if payload.is_checked else None
    db.add(plan_item)
    db.commit()

    updated_plan_item = _get_plan_item_or_404(db, route_plan_id, plan_item_id)
    return PlanItemResponse.model_validate(updated_plan_item)


__all__ = ["router"]
