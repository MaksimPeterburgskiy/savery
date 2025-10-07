"""Domain and API models backed by SQLModel."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID
import uuid

from sqlmodel import Enum, Field, Relationship, SQLModel, JSON, Index


# Enumerations -----------------------------------------------------------------


class OptimizationMode(Enum):
    PRICE = "PRICE"
    BALANCED = "BALANCED"
    SPEED = "SPEED"


class JobStage(Enum):
    MATCH = "MATCH"
    PRICING = "PRICING"
    OPTIMIZE = "OPTIMIZE"


class JobStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class MatchStatus(Enum):
    PENDING = "PENDING"
    SELECTED = "SELECTED"
    REJECTED = "REJECTED"
    UNMATCHED = "UNMATCHED"


# Base class -------------------------------------------------------------------
class Base(SQLModel):
    id: UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# Shopping Lists ---------------------------------------------------------------
class ShoppingList(Base, table=True):
    client_id: str = Field(unique=True, index=True, nullable=True)
    title: str = Field(nullable=True)

    list_items: list["ListItem"] = Relationship(back_populates="list")
    route_plans: list["RoutePlan"] = Relationship(back_populates="list")

class ListItem(Base):
    # __table_args__ = (Index("ix_list_items_list_id_position", "list_id", "position"),)

    raw_text_qty: str
    raw_text_item: str
    item_name: str
    qty_value: float
    qty_unit: str
    norm_qty_value: float
    norm_qty_unit: str
    position: int

    list: ShoppingList = Relationship(back_populates="list_items")
    item_matches: list[ItemMatch] = Relationship(back_populates="list_item")
    plan_items: list[PlanItem] = Relationship(back_populates="list_item")


# Store & Product Catalog ------------------------------------------------------


class StoreChain(Base):
    __tablename__ = "store_chains"

    name: str

    stores: list[Store] = Relationship(back_populates="chain")


class Store(Base):
    __tablename__ = "stores"

    name: str
    number: str
    external_ref: JSON
    address_line1: str
    address_line2: str
    city: str
    region: str
    postal_code: str
    country_code: str
    latitude: float
    longitude: float
    timezone: str
    hours_json: JSON
    phone: str
    geography: Geography = Field(
        Geography(geometry_type="POINT", srid=4326), nullable=True
    )

    chain: StoreChain = Relationship(back_populates="stores")
    store_products: list[StoreProduct] = Relationship(back_populates="store")
    plan_selected: list[PlanSelectedStore] = Relationship(
        back_populates="store"
    )
    store_visits: list[PlanStoreVisit] = Relationship(back_populates="store")
    item_matches: list[ItemMatch] = Relationship(back_populates="store")


class Product(Base):
    __tablename__ = "products"

    brand: str
    name: str = Field(nullable=False)
    upc: str
    size_text: str
    pkg_qty_value: float
    pkg_qty_unit: str
    base_qty_value: float
    base_qty_unit: str
    embedding: Vector = Field(Vector(384))
    embedding_dim: int

    store_products: list[StoreProduct] = Relationship(back_populates="product")


class StoreProduct(Base):
    __tablename__ = "store_products"
    __table_args__ = (
        UniqueConstraint(
            "store_id", "product_id", name="uq_store_products_store_product"
        ),
        UniqueConstraint(
            "store_id", "external_sku", name="uq_store_products_store_sku"
        ),
    )

    external_sku: str
    aisle: str
    shelf_code: str
    product_url: str
    is_active: bool = Field(server_default="true", nullable=False)

    store: Store = Relationship(back_populates="store_products")
    product: Product = Relationship(back_populates="store_products")
    price_entries: list[PriceEntry] = Relationship(
        back_populates="store_product"
    )
    plan_items: list[PlanItem] = Relationship(back_populates="store_product")
    chosen_for_matches: list[ItemMatch] = Relationship(
        back_populates="chosen_store_product"
    )
    candidate_rows: list[ItemMatchCandidate] = Relationship(
        back_populates="store_product"
    )


class PriceEntry(Base):
    __tablename__ = "price_entries"
    __table_args__ = (
        Index(
            "ix_price_entries_store_product_is_current",
            "store_product_id",
            "is_current",
        ),
        Index(
            "ix_price_entries_store_product_fetched_at",
            "store_product_id",
            "fetched_at",
        ),
    )

    currency_code: str = Field(
        String(3), nullable=False, server_default="USD"
    )
    price: float = Field(Numeric(12, 2))
    unit_price: float = Field(Numeric(12, 6))
    unit_price_unit: str
    source: str
    valid_from: datetime
    valid_to: datetime
    is_current: bool = Field(server_default="true", nullable=False)

    store_product: StoreProduct = Relationship(back_populates="price_entries")
    plan_items: list[PlanItem] = Relationship(back_populates="price_entry")
    chosen_for_matches: list[ItemMatch] = Relationship(
        back_populates="chosen_price_entry"
    )
    candidate_refs: list[ItemMatchCandidate] = Relationship(
        back_populates="price_entry"
    )


# Route Planning ---------------------------------------------------------------


class RoutePlan(Base):
    __tablename__ = "route_plans"
    __table_args__ = (
        Index("ix_route_plans_list_id", "list_id"),
        Index("ix_route_plans_client_token", "client_token"),
    )

    client_token: str = Field(String, nullable=False, index=True)
    status: str = Field(String, nullable=False, server_default="draft")
    opt_mode: OptimizationMode = Field(
        SAEnum(OptimizationMode, name="optimization_mode"),
        nullable=False,
        server_default="BALANCED",
    )
    lowest_unit_price: bool = Field(
        server_default="false", nullable=False
    )
    max_stores: int = Field(server_default="3")
    user_latitude: float
    user_longitude: float
    total_price: float = Field(Numeric(12, 2))
    total_distance_m: int
    total_travel_sec: int

    list: ShoppingList = Relationship(back_populates="route_plans")
    selected_stores: list[PlanSelectedStore] = Relationship(
        back_populates="plan", cascade="all,delete-orphan"
    )
    item_matches: list[ItemMatch] = Relationship(
        back_populates="plan", cascade="all,delete-orphan"
    )
    store_visits: list[PlanStoreVisit] = Relationship(
        back_populates="plan", cascade="all,delete-orphan"
    )
    jobs: list[Job] = Relationship(
        back_populates="plan", cascade="all,delete-orphan"
    )


class PlanSelectedStore(Base):
    __tablename__ = "plan_selected_stores"
    __table_args__ = (
        UniqueConstraint(
            "plan_id", "store_id", name="uq_plan_selected_stores_plan_store"
        ),
    )

    plan: RoutePlan = Relationship(back_populates="selected_stores")
    store: Store = Relationship(back_populates="plan_selected")


class ItemMatch(Base):
    __tablename__ = "item_matches"
    __table_args__ = (
        UniqueConstraint(
            "plan_id",
            "list_item_id",
            "store_id",
            name="uq_item_matches_plan_item_store",
        ),
    )

    status: MatchStatus = Field(
        SAEnum(MatchStatus, name="match_status"),
        nullable=False,
        server_default="PENDING",
    )
    notes: str
    updated_by_user: bool = Field(
        server_default="false", nullable=False
    )

    plan: RoutePlan = Relationship(back_populates="item_matches")
    list_item: ListItem = Relationship(back_populates="item_matches")
    store: Store = Relationship(back_populates="item_matches")
    chosen_store_product: StoreProduct = Relationship(
        back_populates="chosen_for_matches"
    )
    chosen_price_entry: PriceEntry = Relationship(
        back_populates="chosen_for_matches"
    )
    candidates: list[ItemMatchCandidate] = Relationship(
        back_populates="item_match", cascade="all,delete-orphan"
    )


class ItemMatchCandidate(Base):
    __tablename__ = "item_match_candidates"
    __table_args__ = (
        UniqueConstraint(
            "item_match_id", "rank", name="uq_item_match_candidates_match_rank"
        ),
    )

    rank: int
    score: float = Field(Numeric(6, 3))
    rejected_by_user: bool = Field(
        server_default="false", nullable=False
    )

    item_match: ItemMatch = Relationship(back_populates="candidates")
    store_product: StoreProduct = Relationship(back_populates="candidate_rows")
    price_entry: PriceEntry = Relationship(back_populates="candidate_refs")


class PlanStoreVisit(Base):
    __tablename__ = "plan_store_visits"
    __table_args__ = (
        UniqueConstraint(
            "plan_id", "sequence", name="uq_plan_store_visits_plan_sequence"
        ),
    )

    sequence: int = Field(nullable=False)
    travel_sec_from_prev: int
    distance_m_from_prev: int
    subtotal_price: float = Field(Numeric(12, 2))

    plan: RoutePlan = Relationship(back_populates="store_visits")
    store: Store = Relationship(back_populates="store_visits")
    plan_items: list[PlanItem] = Relationship(
        back_populates="plan_store_visit", cascade="all,delete-orphan"
    )


class PlanItem(Base):
    __tablename__ = "plan_items"
    __table_args__ = (
        Index("ix_plan_items_plan_store_visit_id", "plan_store_visit_id"),
        Index("ix_plan_items_list_item_id", "list_item_id"),
    )

    qty: int = Field(nullable=False, server_default="1")
    per_qty_price: float = Field(Numeric(12, 2))
    extended_price: float = Field(Numeric(12, 2))
    is_checked: bool = Field(server_default="false", nullable=False)
    checked_at: datetime

    plan_store_visit: PlanStoreVisit = Relationship(back_populates="plan_items")
    list_item: ListItem = Relationship(back_populates="plan_items")
    store_product: StoreProduct = Relationship(back_populates="plan_items")
    price_entry: PriceEntry = Relationship(back_populates="plan_items")


# Job Tracking -----------------------------------------------------------------


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("plan_id", "stage", name="uq_jobs_plan_stage"),
        Index("ix_jobs_task_id", "task_id"),
    )

    stage: JobStage = Field(
        SAEnum(JobStage, name="job_stage"), nullable=False
    )
    status: JobStatus = Field(
        SAEnum(JobStatus, name="job_status"),
        nullable=False,
        server_default="PENDING",
    )
    progress_current: int
    progress_total: int
    task_id: str = Field(index=True)
    message: str

    plan: RoutePlan = Relationship(back_populates="jobs")
