"""Route Plan endpoints."""

from __future__ import annotations

from collections import defaultdict
from enum import Enum
from typing import Sequence
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from geoalchemy2 import WKTElement
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from backend.app.api.routes.stores import StoreResponse
from backend.app.api.utils.geography import extract_point_coordinates
from backend.app.dependencies import get_db
from backend.app.models import OptimizationMode, PlanSelectedStore, RoutePlan, ShoppingList, Store

router = APIRouter()


class RoutePlanResponse(BaseModel):
    """Response model for route plan."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    list_id: UUID | None = None
    selected_stores: list[StoreResponse] = Field(default_factory=list)
    status: str
    opt_mode: OptimizationMode
    lowest_unit_price: bool
    max_stores: int
    user_longitude: float | None = None
    user_latitude: float | None = None
    total_price: float | None
    total_distance_m: int | None
    total_travel_sec: int | None

    @classmethod
    def from_model(
        cls,
        plan: RoutePlan,
        user_geography_geojson: str | None,
        store_payloads: Sequence[tuple[Store, str | None]],
    ) -> "RoutePlanResponse":
        """Instantiate a response from a RoutePlan and related geography."""

        base_data = plan.model_dump(
            include={
                "id",
                "list_id",
                "status",
                "opt_mode",
                "lowest_unit_price",
                "max_stores",
                "total_price",
                "total_distance_m",
                "total_travel_sec",
            }
        )

        coords = extract_point_coordinates(user_geography_geojson)
        if coords is not None:
            base_data.update({"user_longitude": coords[0], "user_latitude": coords[1]})

        base_data["selected_stores"] = [
            StoreResponse.from_model(store, geography_geojson) for store, geography_geojson in store_payloads
        ]

        return cls(**base_data)


class RoutePlanStatus(str, Enum):
    """Allowed status values for route plans."""

    DRAFT = "draft"
    MATCHED = "matched"
    OPTIMIZED = "optimized"
    COMPLETE = "complete"


class RoutePlanCreate(BaseModel):
    """Payload for creating a route plan."""

    model_config = ConfigDict(extra="forbid")

    client_id: str | None = None
    status: RoutePlanStatus = RoutePlanStatus.DRAFT
    opt_mode: OptimizationMode = OptimizationMode.BALANCED
    lowest_unit_price: bool = False
    max_stores: int = Field(default=3, ge=1)
    user_longitude: float | None = None
    user_latitude: float | None = None
    selected_store_ids: list[UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_location(self) -> "RoutePlanCreate":
        lon_set = self.user_longitude is not None
        lat_set = self.user_latitude is not None
        if lon_set ^ lat_set:
            raise ValueError("user_longitude and user_latitude must be provided together")
        return self


class RoutePlanUpdate(BaseModel):
    """Payload for updating a route plan."""

    model_config = ConfigDict(extra="forbid")

    status: RoutePlanStatus | None = None
    opt_mode: OptimizationMode | None = None
    lowest_unit_price: bool | None = None
    max_stores: int | None = Field(default=None, ge=1)
    user_longitude: float | None = None
    user_latitude: float | None = None
    total_price: float | None = None
    total_distance_m: int | None = None
    total_travel_sec: int | None = None

    @model_validator(mode="after")
    def validate_location(self) -> "RoutePlanUpdate":
        update_fields = self.model_dump(exclude_unset=True)
        lon_present = "user_longitude" in update_fields
        lat_present = "user_latitude" in update_fields
        if lon_present ^ lat_present:
            raise ValueError("user_longitude and user_latitude must be provided together when updating location")
        return self


class SelectedStoreCreate(BaseModel):
    """Payload for adding a store selection to a plan."""

    model_config = ConfigDict(extra="forbid")

    store_id: UUID


def _build_route_plan_responses(
    session: Session,
    plans: Sequence[RoutePlan],
) -> list[RoutePlanResponse]:
    """Return serialized responses with related geography in batch."""

    if not plans:
        return []

    plan_ids = [plan.id for plan in plans]

    user_geo_map: dict[UUID, str | None] = {
        plan_id: geojson
        for plan_id, geojson in session.exec(
            select(RoutePlan.id, func.ST_AsGeoJSON(RoutePlan.user_geography)).where(RoutePlan.id.in_(plan_ids))
        )
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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Store already selected for this plan"
        ) from exc

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
