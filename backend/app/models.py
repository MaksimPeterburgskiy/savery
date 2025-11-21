"""Domain and API models backed by SQLModel."""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import UUID

from geoalchemy2 import Geography
from pgvector.sqlalchemy import Vector
from pydantic import ConfigDict
from sqlalchemy import Column, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Index, Relationship, SQLModel, UniqueConstraint

# Enumerations -----------------------------------------------------------------


class OptimizationMode(str, Enum):
    """Controls whether route planning emphasizes price, speed, or a balance."""

    PRICE = "PRICE"
    """Left slider position: prioritize price optimization."""
    BALANCED = "BALANCED"
    """Middle slider position: balanced trade-off between price and time."""
    SPEED = "SPEED"
    """Right slider position: prioritize speed."""


class JobStage(str, Enum):
    """Type of Job."""

    MATCH = "MATCH"
    """Create Item Match Candidates from Shopping List Entries."""
    PRICING = "PRICING"
    """Fetch pricing data for generated candidates."""
    OPTIMIZE = "OPTIMIZE"
    """Build the final plan and route."""
    HEALTHCHECK = "HEALTHCHECK"
    """Background health validation that the stack is responsive."""
    FANOUT = "FANOUT"
    """Fan out selected candidates to Item Matches at each store."""


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


# Base class -------------------------------------------------------------------
def utcnow() -> datetime:
    """Return current UTC time for timestamp defaults."""
    return datetime.now(timezone.utc)


class Base(SQLModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        use_attribute_docstrings=True,
    )
    id: UUID = Field(default_factory=uuid.uuid4, primary_key=True, nullable=False)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False, sa_column_kwargs={"onupdate": utcnow})


# Shopping Lists ---------------------------------------------------------------
class ShoppingList(Base, table=True):
    __tablename__ = "shopping_lists"

    client_id: str | None = Field(default=None, index=True)
    title: str | None = Field(default=None)
    """Human-readable name or description for the shopping list."""

    list_items: List["ListItem"] = Relationship(
        back_populates="list",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    route_plans: List["RoutePlan"] = Relationship(
        back_populates="list",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class ListItem(Base, table=True):
    __tablename__ = "list_items"

    list_id: UUID = Field(foreign_key="shopping_lists.id", nullable=False, index=True)
    list: ShoppingList | None = Relationship(back_populates="list_items")

    raw_text_qty: str | None = Field(default=None)
    """Raw Item quantity text. (e.g., "2 lbs", "3 packs")."""
    raw_text_item: str | None = Field(default=None)
    """Raw item description. (e.g., "Boneless Skinless Chicken Thighs")."""
    item_name: str | None = Field(default=None)
    """Canonically Normalized item name (e.g., "chicken thigh boneless skinless")."""
    qty_value: float | None = Field(default=None)
    """Numeric portion of the raw quantity."""
    qty_unit: str | None = Field(default=None)
    """Unit portion of the raw quantity ("lb", "packs", etc.)."""
    norm_qty_value: float | None = Field(default=None)
    """Normalized quantity value based on the normalized unit. """
    norm_qty_unit: str | None = Field(default=None)
    """Normalized Base unit of measure ("g", "ml", "count")."""
    position: int = Field(nullable=False)
    """UI order position (1-based)."""

    item_matches: List["ItemMatch"] = Relationship(back_populates="list_item")
    match_candidates: List["ItemMatchCandidate"] = Relationship(back_populates="list_item")
    plan_items: List["PlanItem"] = Relationship(back_populates="list_item")


# Store & Product Catalog ------------------------------------------------------


class StoreChain(Base, table=True):
    __tablename__ = "store_chains"

    name: str
    """Retail brand name (e.g., "Kroger", "Walmart")."""

    stores: List["Store"] = Relationship(back_populates="chain")


class Store(Base, table=True):
    __tablename__ = "stores"

    chain_id: UUID | None = Field(default=None, foreign_key="store_chains.id", index=True)
    chain: StoreChain | None = Relationship(back_populates="stores")

    name: str
    """Display name of the store location."""
    number: str
    """Store number or identifier."""
    external_ref: dict | None = Field(default=None, sa_column=Column(JSONB))
    """Provider-specific identifiers (e.g., kroger_location_id)."""
    address_line1: str
    address_line2: str | None = Field(default=None)
    city: str
    region: str
    """State or province where the store resides."""
    postal_code: str
    country_code: str = Field(sa_column=Column(String(2)))
    """ISO 3166-1 alpha-2 country code."""
    timezone: str
    hours_json: dict | None = Field(default=None, sa_column=Column(JSONB))
    """Raw hours JSON captured."""
    phone: str
    geography: Geography = Field(
        default=None,
        sa_column=Column(Geography(geometry_type="POINT", srid=4326), nullable=True),
    )

    store_products: List["StoreProduct"] = Relationship(back_populates="store")
    plan_selected: List["PlanSelectedStore"] = Relationship(back_populates="store")
    store_visits: List["PlanStoreVisit"] = Relationship(back_populates="store")
    item_matches: List["ItemMatch"] = Relationship(back_populates="store")


class Product(Base, table=True):
    __tablename__ = "products"

    """Catalog of canonical products we match list items against."""

    brand: str
    """Manufacturer or retail brand as reported by the provider."""
    name: str = Field(nullable=False)
    """Canonical product name used for matching and display."""
    upc: str | None = Field(default=None)
    """UPC/GTIN identifier."""
    size_text: str | None = Field(default=None)
    """Provider-reported package size text (e.g., "16 oz", "1 lb")."""
    pkg_qty_value: float | None = Field(default=None)
    """Numeric portion of the package size when parsable."""
    pkg_qty_unit: str | None = Field(default=None)
    """Unit from the size_text ("oz", "g", "ct", etc.)."""
    base_qty_value: float | None = Field(default=None)
    """Normalized quantity for comparisons across package sizes."""
    base_qty_unit: str | None = Field(default=None)
    """Normalized unit (e.g., "g", "ml", "count")."""
    embedding: list[float] | None = Field(default=None, sa_column=Column(Vector(384)))
    """Vector embedding of the product name/attributes used for similarity."""
    embedding_dim: int | None = Field(default=None)
    """Dimension of the stored vector embedding (typically 384)."""
    image_url: str | None = Field(default=None)
    """Image URL for display."""

    store_products: List["StoreProduct"] = Relationship(back_populates="product")
    match_candidates: List["ItemMatchCandidate"] = Relationship(back_populates="product")


class StoreProduct(Base, table=True):
    __tablename__ = "store_products"
    __table_args__ = (
        UniqueConstraint(
            "store_id",
            "product_id",
            name="uq_store_products_store_product",
        ),
        UniqueConstraint(
            "store_id",
            "external_sku",
            name="uq_store_products_store_sku",
        ),
    )

    store_id: UUID = Field(foreign_key="stores.id", nullable=False, index=True)
    store: Store | None = Relationship(back_populates="store_products")

    product_id: UUID = Field(foreign_key="products.id", nullable=False, index=True)
    product: Product | None = Relationship(back_populates="store_products")

    external_sku: str
    """Per-store SKU or identifier from the provider."""
    aisle: str | None = Field(default=None)
    shelf_code: str | None = Field(default=None)
    product_url: str | None = Field(default=None)
    """Deep link to the product on the retailer's site, if available."""
    is_active: bool = Field(default=True, nullable=False)
    """Soft toggle for whether the product is currently sold."""

    price_entries: List["PriceEntry"] = Relationship(back_populates="store_product")
    plan_items: List["PlanItem"] = Relationship(back_populates="store_product")
    chosen_for_matches: List["ItemMatch"] = Relationship(back_populates="store_product")


class PriceEntry(Base, table=True):
    __tablename__ = "price_entries"

    store_product_id: UUID = Field(foreign_key="store_products.id", nullable=False, index=True)
    store_product: StoreProduct | None = Relationship(back_populates="price_entries")

    currency_code: str = Field(default="USD", sa_column=Column(String(3)))
    price: float = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    """Price observed for the store product."""
    unit_price: float | None = Field(default=None, sa_column=Column(Numeric(12, 6), nullable=True))
    """Price normalized per base quantity unit."""
    unit_price_unit: str | None = Field(default=None)
    """Unit expressed for the unit_price ("g", "ml", "count")."""
    source: str
    """Origin of the price."""
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    valid_from: datetime | None = Field(default=None)
    valid_to: datetime | None = Field(default=None)
    is_current: bool = Field(default=True, nullable=False)

    plan_items: List["PlanItem"] = Relationship(back_populates="price_entry")
    chosen_for_matches: List["ItemMatch"] = Relationship(back_populates="price_entry")


# Route Planning ---------------------------------------------------------------


class RoutePlan(Base, table=True):
    __tablename__ = "route_plans"

    list_id: UUID = Field(foreign_key="shopping_lists.id", nullable=False, index=True)
    list: ShoppingList | None = Relationship(back_populates="route_plans")

    client_id: str = Field(nullable=False, index=True)
    status: str = Field(default="draft", nullable=False)
    """Lifecycle status ('draft', 'matched', 'optimized', 'complete')."""
    opt_mode: OptimizationMode = Field(default=OptimizationMode.BALANCED, nullable=False)
    """User-selected optimization mode."""
    lowest_unit_price: bool = Field(default=False, nullable=False)
    """Toggle that favors lowest unit price."""
    max_stores: int = Field(default=3, nullable=False)
    """Maximum number of stores to include in the route."""
    user_geography: Geography = Field(
        default=None,
        sa_column=Column(Geography(geometry_type="POINT", srid=4326), nullable=True),
    )
    """User location at the time the plan was requested."""
    total_price: float | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    """Derived total price across all planned purchases."""
    total_distance_m: int | None = Field(default=None)
    """Derived travel distance in meters."""
    total_travel_sec: int | None = Field(default=None)
    """Derived travel duration in seconds."""

    selected_stores: List["PlanSelectedStore"] = Relationship(
        back_populates="plan",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    item_matches: List["ItemMatch"] = Relationship(
        back_populates="plan",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    match_candidates: List["ItemMatchCandidate"] = Relationship(
        back_populates="plan",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    store_visits: List["PlanStoreVisit"] = Relationship(
        back_populates="plan",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    jobs: List["Job"] = Relationship(
        back_populates="plan",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class PlanSelectedStore(Base, table=True):
    __tablename__ = "plan_selected_stores"
    __table_args__ = (
        UniqueConstraint(
            "plan_id",
            "store_id",
            name="uq_plan_selected_stores_plan_store",
        ),
    )

    plan_id: UUID = Field(foreign_key="route_plans.id", nullable=False, index=True)
    plan: RoutePlan | None = Relationship(back_populates="selected_stores")

    store_id: UUID = Field(foreign_key="stores.id", nullable=False, index=True)
    store: Store | None = Relationship(back_populates="plan_selected")


class ItemMatch(Base, table=True):
    __tablename__ = "item_matches"
    __table_args__ = (
        UniqueConstraint(
            "plan_id",
            "list_item_id",
            "store_id",
            "item_match_candidate_id",
            name="uq_item_matches_plan_item_store_candidate",
        ),
    )

    plan_id: UUID = Field(foreign_key="route_plans.id", nullable=False, index=True)
    plan: RoutePlan | None = Relationship(back_populates="item_matches")

    list_item_id: UUID = Field(foreign_key="list_items.id", nullable=False, index=True)
    list_item: ListItem | None = Relationship(back_populates="item_matches")

    store_id: UUID = Field(foreign_key="stores.id", nullable=False, index=True)
    store: Store | None = Relationship(back_populates="item_matches")

    item_match_candidate_id: UUID = Field(
        sa_column=Column(
            "item_match_candidate_id",
            ForeignKey("item_match_candidates.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    item_match_candidate: Optional["ItemMatchCandidate"] = Relationship(back_populates="chosen_for_matches")

    store_product_id: UUID | None = Field(default=None, foreign_key="store_products.id", index=True)
    store_product: StoreProduct | None = Relationship(back_populates="chosen_for_matches")

    price_entry_id: UUID | None = Field(default=None, foreign_key="price_entries.id", index=True)
    price_entry: PriceEntry | None = Relationship(back_populates="chosen_for_matches")


class ItemMatchCandidate(Base, table=True):
    __tablename__ = "item_match_candidates"
    __table_args__ = (
        UniqueConstraint(
            "plan_id",
            "list_item_id",
            "product_id",
            name="uq_item_match_candidates_plan_item_product",
        ),
    )

    plan_id: UUID = Field(foreign_key="route_plans.id", nullable=False, index=True)
    plan: RoutePlan | None = Relationship(back_populates="match_candidates")

    list_item_id: UUID = Field(foreign_key="list_items.id", nullable=False, index=True)
    list_item: ListItem | None = Relationship(back_populates="match_candidates")

    product_id: UUID = Field(foreign_key="products.id", nullable=False, index=True)
    product: Product | None = Relationship(back_populates="match_candidates")

    score: float
    """Similarity/confidence score for this candidate."""
    rejected_by_user: bool = Field(default=False, nullable=False)
    """Tracks when the user explicitly rejected every match for this store."""

    chosen_for_matches: List["ItemMatch"] = Relationship(
        back_populates="item_match_candidate",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class PlanStoreVisit(Base, table=True):
    __tablename__ = "plan_store_visits"
    __table_args__ = (
        UniqueConstraint(
            "plan_id",
            "sequence",
            name="uq_plan_store_visits_plan_sequence",
        ),
    )

    plan_id: UUID = Field(foreign_key="route_plans.id", nullable=False, index=True)
    plan: RoutePlan | None = Relationship(back_populates="store_visits")

    store_id: UUID = Field(foreign_key="stores.id", nullable=False, index=True)
    store: Store | None = Relationship(back_populates="store_visits")

    sequence: int = Field(nullable=False)
    """Visit order starting at 1."""
    travel_sec_from_prev: int | None = Field(default=None)
    """Seconds needed to travel from the prior stop."""
    distance_m_from_prev: int | None = Field(default=None)
    """Meters traveled from the previous stop."""
    subtotal_price: float | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))

    plan_items: List["PlanItem"] = Relationship(
        back_populates="plan_store_visit",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class PlanItem(Base, table=True):
    __tablename__ = "plan_items"

    plan_store_visit_id: UUID = Field(foreign_key="plan_store_visits.id", nullable=False, index=True)
    plan_store_visit: PlanStoreVisit | None = Relationship(back_populates="plan_items")

    list_item_id: UUID = Field(foreign_key="list_items.id", nullable=False, index=True)
    list_item: ListItem | None = Relationship(back_populates="plan_items")

    store_product_id: UUID | None = Field(default=None, foreign_key="store_products.id", index=True)
    store_product: StoreProduct | None = Relationship(back_populates="plan_items")

    price_entry_id: UUID | None = Field(default=None, foreign_key="price_entries.id", index=True)
    price_entry: PriceEntry | None = Relationship(back_populates="plan_items")

    qty: int = Field(default=1, nullable=False)
    """Quantity needed at purchase time."""
    per_qty_price: float | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    """Price per single qty unit used for the extended total."""
    extended_price: float | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    """qty * per_qty_price, used for subtotal tracking."""
    is_checked: bool = Field(default=False, nullable=False)
    """Checklist flag for whether the shopper has marked the item as purchased."""
    checked_at: datetime | None = Field(default=None)
    """Timestamp when the item was marked as checked."""


# Job Tracking -----------------------------------------------------------------


class Job(Base, table=True):
    __tablename__ = "jobs"

    plan_id: UUID = Field(foreign_key="route_plans.id", nullable=False, index=True)
    plan: RoutePlan | None = Relationship(back_populates="jobs")

    stage: JobStage = Field(default=JobStage.MATCH, nullable=False)
    status: JobStatus = Field(default=JobStatus.PENDING, nullable=False)
    progress_current: int | None = Field(default=None)
    progress_total: int | None = Field(default=None)
    task_id: str | None = Field(default=None, index=True)
    """Celery task identifier for this job."""
    message: str | None = Field(default=None)
    """Error or status message surfaced by the job."""
    started_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)


# Table-level indexes and constraints -----------------------------------------

Index(
    "ix_list_items_list_id_position",
    ListItem.list_id,
    ListItem.position,
)
Index(
    "ix_price_entries_store_product_is_current",
    PriceEntry.store_product_id,
    PriceEntry.is_current,
)
Index(
    "ix_price_entries_store_product_fetched_at",
    PriceEntry.store_product_id,
    PriceEntry.fetched_at,
)
Index(
    "ix_jobs_plan_stage_active",
    Job.plan_id,
    Job.stage,
    unique=True,
    postgresql_where=Job.status.in_((JobStatus.PENDING, JobStatus.RUNNING)),
)
