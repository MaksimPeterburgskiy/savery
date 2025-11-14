"""Route Plan endpoints."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from enum import Enum
from typing import Sequence
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from geoalchemy2 import WKTElement
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from backend.app.api.routes.item_matches import JobResponse, _get_route_plan_or_404
from backend.app.api.routes.shopping_lists import ListItemResponse
from backend.app.api.routes.stores import StoreResponse
from backend.app.api.utils.geography import extract_point_coordinates
from backend.app.dependencies import get_db
from backend.app.models import (
    Job,
    JobStage,
    JobStatus,
    OptimizationMode,
    PlanItem,
    PlanSelectedStore,
    PlanStoreVisit,
    RoutePlan,
    ShoppingList,
    Store,
    StoreProduct,
    utcnow,
)
from backend.app.tasks import enqueue_job
from backend.workers.celery_app import celery_app

router = APIRouter()


class PriceEntryResponse(BaseModel):
    """Response model for a price entry associated with a store product."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID

    currency_code: str
    price: float
    unit_price: float
    unit_price_unit: str
    source: str
    fetched_at: datetime
    valid_from: datetime
    valid_to: datetime
    is_current: bool


class ProductResponse(BaseModel):
    """Response model for a standardized product."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    brand: str
    name: str
    upc: str
    size_text: str
    pkg_qty_value: float
    pkg_qty_unit: str
    base_qty_value: float
    base_qty_unit: str
    image_url: str


class StoreProductResponse(BaseModel):
    """Response model for a product available at a specific store."""

    model_config = ConfigDict(from_attributes=True)
    id: UUID

    product: ProductResponse
    external_sku: str
    aisle: str
    shelf_code: str
    product_url: str
    is_active: bool


class PlanItemResponse(BaseModel):
    """Response model for an item within a plan store visit."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plan_store_visit_id: UUID
    list_item: ListItemResponse
    store_product: StoreProductResponse
    price_entry: PriceEntryResponse
    qty: int
    per_qty_price: float
    extended_price: float
    is_checked: bool
    checked_at: datetime


class PlanItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_checked: bool


class PlanStoreVisitResponse(BaseModel):
    """Response model for a store visit within a route plan."""

    id: UUID
    model_config = ConfigDict(from_attributes=True)

    plan_id: UUID
    store: StoreResponse
    sequence: int
    travel_sec_from_prev: int
    distance_m_from_prev: int
    subtotal_price: float
    plan_items: list[PlanItemResponse]


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

        base_data["selected_stores"] = [StoreResponse.from_model(store, geography_geojson) for store, geography_geojson in store_payloads]

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

    @field_validator("user_longitude")
    @classmethod
    def validate_longitude(cls, v: float | None) -> float | None:
        """Validate longitude is within valid range [-180, 180]."""
        if v is not None and (v < -180.0 or v > 180.0):
            raise ValueError("user_longitude must be between -180 and 180 degrees")
        return v

    @field_validator("user_latitude")
    @classmethod
    def validate_latitude(cls, v: float | None) -> float | None:
        """Validate latitude is within valid range [-90, 90]."""
        if v is not None and (v < -90.0 or v > 90.0):
            raise ValueError("user_latitude must be between -90 and 90 degrees")
        return v

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

    @field_validator("user_longitude")
    @classmethod
    def validate_longitude(cls, v: float | None) -> float | None:
        """Validate longitude is within valid range [-180, 180]."""
        if v is not None and (v < -180.0 or v > 180.0):
            raise ValueError("user_longitude must be between -180 and 180 degrees")
        return v

    @field_validator("user_latitude")
    @classmethod
    def validate_latitude(cls, v: float | None) -> float | None:
        """Validate latitude is within valid range [-90, 90]."""
        if v is not None and (v < -90.0 or v > 90.0):
            raise ValueError("user_latitude must be between -90 and 90 degrees")
        return v

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


# start route planning task
# should only allow one active task at a time per route plan
# POST /route-plans/{route_plan_id}/item-match-jobs
@router.post(
    "/route-plans/{route_plan_id}/plan-route-jobs",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or restart the route plan job for a route plan",
)
def create_plan_route_job(
    route_plan_id: UUID,
    db: Session = Depends(get_db),
) -> JobResponse:
    _get_route_plan_or_404(db, route_plan_id)

    active_statement = (
        select(Job)
        .where(
            Job.plan_id == route_plan_id,
            Job.stage == JobStage.OPTIMIZE,
            Job.status.in_((JobStatus.PENDING, JobStatus.RUNNING)),
        )
        .order_by(Job.updated_at.desc())
    )
    active_job = db.exec(active_statement).first()
    if active_job is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An item match job is already running for this route plan",
        )

    job_statement = select(Job).where(Job.plan_id == route_plan_id, Job.stage == JobStage.OPTIMIZE)
    job = db.exec(job_statement).first()
    if job is None:
        job = Job(
            plan_id=route_plan_id,
            stage=JobStage.OPTIMIZE,
            status=JobStatus.PENDING,
            task_id="",
        )
    else:
        job.status = JobStatus.PENDING
        job.progress_current = 0
        job.progress_total = None
        job.message = None
        job.started_at = None
        job.completed_at = None
        if job.task_id is None:
            job.task_id = ""

    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        enqueue_job(job.id)
    except ValueError as exc:
        job.status = JobStatus.FAILED
        job.message = f"Failed to enqueue job: {exc}"
        job.completed_at = utcnow()
        db.add(job)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        job.status = JobStatus.FAILED
        job.message = "Failed to enqueue job: Celery unavailable"
        job.completed_at = utcnow()
        db.add(job)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to enqueue item match job",
        ) from exc

    return JobResponse.model_validate(job)


# cancel active route planning task, only works if its running or pending
# DELETE /route-plans/{route_plan_id}/item-match-jobs/{job_id}
@router.delete(
    "/route-plans/{route_plan_id}/plan-route-jobs/{job_id}",
    response_model=JobResponse,
    summary="Cancel the active route planning task for a route plan",
)
def cancel_plan_route_job(
    route_plan_id: UUID,
    job_id: UUID,
    db: Session = Depends(get_db),
) -> JobResponse:
    _get_route_plan_or_404(db, route_plan_id)

    job = db.get(Job, job_id)
    if job is None or job.plan_id != route_plan_id or job.stage != JobStage.OPTIMIZE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route plan job not found")

    if job.status not in (JobStatus.PENDING, JobStatus.RUNNING):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending or running route planning jobs can be cancelled",
        )

    # Revoke the Celery task to prevent it from continuing execution
    if job.task_id:
        celery_app.control.revoke(job.task_id, terminate=True)

    job.status = JobStatus.FAILED
    if job.message:
        job.message = f"{job.message}; Cancelled by user"
    else:
        job.message = "Cancelled by user"
    job.completed_at = utcnow()
    db.add(job)
    db.commit()
    db.refresh(job)

    return JobResponse.model_validate(job)


# Return job history for the plan
# query params so clients can list just the active task or the full history
# GET /route-plans/{route_plan_id}/plan-route-jobs
@router.get(
    "/route-plans/{route_plan_id}/plan-route-jobs",
    response_model=Sequence[JobResponse],
    summary="List plan route jobs for a route plan",
)
def list_plan_route_jobs(
    route_plan_id: UUID,
    active_only: bool = Query(
        default=False,
        description="Return only pending or running jobs for the route plan",
    ),
    db: Session = Depends(get_db),
) -> Sequence[JobResponse]:
    _get_route_plan_or_404(db, route_plan_id)

    statement = select(Job).where(Job.plan_id == route_plan_id, Job.stage == JobStage.OPTIMIZE)
    if active_only:
        statement = statement.where(Job.status.in_((JobStatus.PENDING, JobStatus.RUNNING)))

    statement = statement.order_by(Job.created_at.desc())

    results = db.exec(statement).all()
    return results


@router.get(
    "/route-plans/{route_plan_id}/plan-route-jobs/{job_id}",
    response_model=JobResponse,
    summary="Get plan route job by ID",
)
def get_plan_route_job_by_id(
    route_plan_id: UUID,
    job_id: UUID,
    db: Session = Depends(get_db),
) -> JobResponse:

    _get_route_plan_or_404(db, route_plan_id)

    statement = (
        select(Job)
        .where(
            Job.plan_id == route_plan_id,
            Job.id == job_id,
            Job.stage == JobStage.OPTIMIZE,
        )
        .order_by(Job.updated_at.desc())
    )
    result = db.exec(statement).first()
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route plan job not found")

    return JobResponse.model_validate(result)


@router.get(
    "/route-plans/{route_plan_id}/plan-route-jobs/active",
    response_model=JobResponse,
    summary="Get plan route job thats active for the route plan",
)
def get_plan_route_job_active(
    route_plan_id: UUID,
    db: Session = Depends(get_db),
) -> JobResponse:

    _get_route_plan_or_404(db, route_plan_id)

    # Only consider matcher jobs that are still running or waiting to start.
    statement = (
        select(Job)
        .where(
            Job.plan_id == route_plan_id,
            Job.stage == JobStage.OPTIMIZE,
            Job.status.in_((JobStatus.PENDING, JobStatus.RUNNING)),
        )
        .order_by(Job.updated_at.desc())
    )

    result = db.exec(statement).first()
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active plan route job found")
    return JobResponse.model_validate(result)



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
