"""Schemas for planning-related endpoints."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Sequence
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.api.routes.catalog.catalog_schemas import StoreResponse
from backend.app.api.routes.lists.lists_schemas import ListItemResponse
from backend.app.api.utils.geography import extract_point_coordinates
from backend.app.models import OptimizationMode, RoutePlan, Store


class PriceEntryResponse(BaseModel):
    """Response model for a price entry associated with a store product."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID

    currency_code: str
    price: float
    unit_price: float | None = None
    unit_price_unit: str | None = None
    source: str
    fetched_at: datetime
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    is_current: bool


class ProductResponse(BaseModel):
    """Response model for a standardized product."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    brand: str
    name: str
    upc: str | None = None
    size_text: str | None = None
    pkg_qty_value: float | None = None
    pkg_qty_unit: str | None = None
    base_qty_value: float | None = None
    base_qty_unit: str | None = None
    image_url: str | None = None


class StoreProductResponse(BaseModel):
    """Response model for a product available at a specific store."""

    model_config = ConfigDict(from_attributes=True)
    id: UUID

    product: ProductResponse
    external_sku: str
    aisle: str | None = None
    shelf_code: str | None = None
    product_url: str | None = None
    is_active: bool


class PlanItemResponse(BaseModel):
    """Response model for an item within a plan store visit."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plan_store_visit_id: UUID
    list_item: ListItemResponse
    store_product: StoreProductResponse | None = None
    price_entry: PriceEntryResponse | None = None
    qty: int
    per_qty_price: float | None = None
    extended_price: float | None = None
    is_checked: bool
    checked_at: datetime | None = None


class PlanItemUpdate(BaseModel):
    """Payload for updating plan item state."""

    model_config = ConfigDict(extra="forbid")

    is_checked: bool


class PlanStoreVisitResponse(BaseModel):
    """Response model for a store visit within a route plan."""

    model_config = ConfigDict(from_attributes=True)
    id: UUID

    plan_id: UUID
    store: StoreResponse
    sequence: int
    travel_sec_from_prev: int | None = None
    distance_m_from_prev: int | None = None
    subtotal_price: float | None = None
    plan_items: list[PlanItemResponse]


class RoutePlanResponse(BaseModel):
    """Response model for route plan."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    list_id: UUID
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


class JobResponse(BaseModel):
    """Response for background job state."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plan_id: UUID
    status: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    progress_current: int | None = None
    progress_total: int | None = None
    message: str | None = None


class ItemMatchCandidateResponse(BaseModel):
    """Response for item match candidate state."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plan_id: UUID
    list_item: ListItemResponse
    product: ProductResponse
    score: float
    rejected_by_user: bool


class ItemMatchCandidateUpdate(BaseModel):
    """Payload for updating candidate rejection state."""

    model_config = ConfigDict(extra="forbid")

    rejected_by_user: bool


__all__ = [
    "ItemMatchCandidateResponse",
    "ItemMatchCandidateUpdate",
    "JobResponse",
    "PlanItemResponse",
    "PlanItemUpdate",
    "PlanStoreVisitResponse",
    "PriceEntryResponse",
    "ProductResponse",
    "RoutePlanCreate",
    "RoutePlanResponse",
    "RoutePlanStatus",
    "RoutePlanUpdate",
    "SelectedStoreCreate",
    "StoreProductResponse",
]
