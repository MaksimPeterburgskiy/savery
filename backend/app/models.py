"""Pydantic request and response models for the FastAPI layer."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ShoppingListItem(BaseModel):
    """Single item supplied by the user."""

    name: str = Field(..., description="User provided item name, e.g. '2% milk'.")
    quantity: float | None = Field(
        default=None,
        ge=0,
        description="Optional numeric quantity associated with the item.",
    )
    unit: str | None = Field(
        default=None,
        description="Original unit string (e.g. 'lb', 'oz').",
    )
    notes: str | None = Field(
        default=None,
        description="Any free-form details captured during parsing.",
    )


class OptimizationPreferences(BaseModel):
    """Tunable parameters to balance cost versus convenience."""

    cost_priority: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Weight between cost savings (1.0) and travel minimization (0.0).",
    )
    max_stores: int | None = Field(
        default=None,
        ge=1,
        description="Optional cap on how many stores the plan may include.",
    )
    allow_bulk: bool = Field(
        default=False,
        description="Whether large pack sizes can satisfy the request.",
    )


class OptimizationRequest(BaseModel):
    """Payload accepted by the /optimize endpoint."""

    items: list[ShoppingListItem] = Field(..., min_length=1)
    store_ids: list[str] = Field(..., min_length=1)
    latitude: float | None = Field(default=None, description="User latitude for distance calculations.")
    longitude: float | None = Field(default=None, description="User longitude for distance calculations.")
    preferences: OptimizationPreferences | None = None


class PurchasedItem(BaseModel):
    """Represents a resolved product recommendation."""

    list_item: ShoppingListItem
    product_id: str | None = None
    product_name: str | None = None
    price: float | None = None
    currency: str = "USD"
    quantity: float | None = None
    unit: str | None = None


class StoreAssignment(BaseModel):
    """Group of recommended purchases for a single store."""

    store_id: str
    store_name: str
    distance_km: float | None = None
    estimated_duration_minutes: float | None = None
    items: list[PurchasedItem] = Field(default_factory=list)


class OptimizationResult(BaseModel):
    """Full optimization output with per-store assignments and totals."""

    stores: list[StoreAssignment] = Field(default_factory=list)
    total_cost: float | None = None
    total_distance_km: float | None = None
    currency: str = "USD"


class OptimizationResponse(BaseModel):
    """Response returned immediately after queuing an optimization job."""

    task_id: str
    status_url: str | None = Field(
        default=None,
        description="Endpoint clients can poll for status updates.",
    )


class StoreSummary(BaseModel):
    """Minimal representation of a store exposed via the API."""

    id: str
    name: str
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class StoreListResponse(BaseModel):
    """Collection of stores from the catalog available for selection."""

    stores: list[StoreSummary]


class TaskStatusResponse(BaseModel):
    """Lightweight Celery status payload exposed over HTTP."""

    id: str
    status: str
    ready: bool
    successful: bool
    result: Any | None = None
