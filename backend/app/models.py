"""Domain and API models backed by SQLModel."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, JSON
from sqlmodel import Field, Relationship, SQLModel


# --- API payload models ----------------------------------------------------


class ShoppingListItem(SQLModel):
    """Single item supplied by the user."""

    name: str = Field(description="User provided item name, e.g. '2% milk'.")
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


class OptimizationPreferences(SQLModel):
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


class OptimizationRequest(SQLModel):
    """Payload accepted by the /optimize endpoint."""

    items: list[ShoppingListItem] = Field(min_length=1)
    store_ids: list[str] = Field(min_length=1)
    latitude: float | None = Field(default=None, description="User latitude for distance calculations.")
    longitude: float | None = Field(default=None, description="User longitude for distance calculations.")
    preferences: OptimizationPreferences | None = None


class PurchasedItem(SQLModel):
    """Represents a resolved product recommendation."""

    list_item: ShoppingListItem
    product_id: str | None = None
    product_name: str | None = None
    price: float | None = None
    currency: str = "USD"
    quantity: float | None = None
    unit: str | None = None


class StoreAssignment(SQLModel):
    """Group of recommended purchases for a single store."""

    store_id: str
    store_name: str
    distance_km: float | None = None
    estimated_duration_minutes: float | None = None
    items: list[PurchasedItem] = Field(default_factory=list)


class OptimizationResult(SQLModel):
    """Full optimization output with per-store assignments and totals."""

    stores: list[StoreAssignment] = Field(default_factory=list)
    total_cost: float | None = None
    total_distance_km: float | None = None
    currency: str = "USD"


class OptimizationResponse(SQLModel):
    """Response returned immediately after queuing an optimization job."""

    task_id: str
    status_url: str | None = Field(
        default=None,
        description="Endpoint clients can poll for status updates.",
    )


class StoreSummary(SQLModel):
    """Minimal representation of a store exposed via the API."""

    id: str
    name: str
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class StoreListResponse(SQLModel):
    """Collection of stores from the catalog available for selection."""

    stores: list[StoreSummary]


class TaskStatusResponse(SQLModel):
    """Lightweight Celery status payload exposed over HTTP."""

    id: str
    status: str
    ready: bool
    successful: bool
    result: Any | None = None
    pipeline: list[dict[str, Any]] | None = None


# --- SQLModel table definitions -------------------------------------------


class Store(SQLModel, table=True):
    """Retail store participating in optimization."""

    __tablename__ = "stores"

    id: int | None = Field(default=None, primary_key=True)
    external_id: str = Field(index=True, sa_column_kwargs={"unique": True})
    name: str = Field(index=True)
    latitude: float | None = Field(default=None)
    longitude: float | None = Field(default=None)
    timezone: str | None = Field(default=None)
    metadata_blob: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime, nullable=False, default=datetime.utcnow),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(
            DateTime,
            nullable=False,
            default=datetime.utcnow,
            onupdate=datetime.utcnow,
        ),
    )

    prices: list["Price"] = Relationship(back_populates="store")


class Product(SQLModel, table=True):
    """Canonical product definition aggregated across stores."""

    __tablename__ = "products"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: str | None = None
    category: str | None = Field(default=None, index=True)
    brand: str | None = Field(default=None, index=True)
    unit: str | None = Field(default=None)
    vector_embedding: list[float] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime, nullable=False, default=datetime.utcnow),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(
            DateTime,
            nullable=False,
            default=datetime.utcnow,
            onupdate=datetime.utcnow,
        ),
    )

    prices: list["Price"] = Relationship(back_populates="product")


class Price(SQLModel, table=True):
    """Price observation for a specific product at a specific store."""

    __tablename__ = "prices"

    id: int | None = Field(default=None, primary_key=True)
    store_id: int = Field(foreign_key="stores.id")
    product_id: int = Field(foreign_key="products.id")
    list_price: float
    promo_price: float | None = None
    unit: str | None = None
    currency: str = Field(default="USD")
    observed_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime, nullable=False, default=datetime.utcnow),
    )
    raw_payload: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )

    store: Store | None = Relationship(back_populates="prices")
    product: Product | None = Relationship(back_populates="prices")


class OptimizationJob(SQLModel, table=True):
    """Track Celery tasks and optimization results."""

    __tablename__ = "optimization_jobs"

    id: int | None = Field(default=None, primary_key=True)
    task_id: str = Field(index=True, sa_column_kwargs={"unique": True})
    input_payload: dict[str, Any] = Field(
        sa_column=Column(JSON, nullable=False),
    )
    result_payload: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    status: str = Field(default="pending")
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime, nullable=False, default=datetime.utcnow),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(
            DateTime,
            nullable=False,
            default=datetime.utcnow,
            onupdate=datetime.utcnow,
        ),
    )
