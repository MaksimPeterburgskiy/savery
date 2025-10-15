"""Domain and API models backed by SQLModel."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import uuid
from uuid import UUID

from geoalchemy2 import Geography
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Float, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Index, Relationship, SQLModel, UniqueConstraint
from pydantic import ConfigDict


# Enumerations -----------------------------------------------------------------


class OptimizationMode(str, Enum):
    PRICE = "PRICE"
    BALANCED = "BALANCED"
    SPEED = "SPEED"


class JobStage(str, Enum):
    MATCH = "MATCH"
    PRICING = "PRICING"
    OPTIMIZE = "OPTIMIZE"


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class MatchStatus(str, Enum):
    PENDING = "PENDING"
    SELECTED = "SELECTED"
    REJECTED = "REJECTED"
    UNMATCHED = "UNMATCHED"


# Base class -------------------------------------------------------------------
class Base(SQLModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    id: UUID = Field(default_factory=uuid.uuid4, primary_key=True, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)


# Shopping Lists ---------------------------------------------------------------
class ShoppingList(Base, table=True):
    __tablename__ = "shopping_lists"

    client_id: str | None = Field(default=None, unique=True, index=True)
    title: str | None = Field(default=None)

    list_items: list[ListItem] = Relationship(back_populates="list")
    route_plans: list[RoutePlan] = Relationship(back_populates="list")


class ListItem(Base, table=True):
    __tablename__ = "list_items"

    list_id: UUID = Field(
        foreign_key="shopping_lists.id", nullable=False, index=True
    )
    list: ShoppingList | None = Relationship(back_populates="list_items")

    raw_text_qty: str
    raw_text_item: str
    item_name: str
    qty_value: float
    qty_unit: str
    norm_qty_value: float
    norm_qty_unit: str
    position: int = Field(nullable=False)

    item_matches: list[ItemMatch] = Relationship(back_populates="list_item")
    plan_items: list[PlanItem] = Relationship(back_populates="list_item")


# Store & Product Catalog ------------------------------------------------------


class StoreChain(Base, table=True):
    __tablename__ = "store_chains"

    name: str

    stores: list[Store] = Relationship(back_populates="chain")


class Store(Base, table=True):
    __tablename__ = "stores"

    chain_id: UUID | None = Field(
        default=None, foreign_key="store_chains.id", index=True
    )
    chain: StoreChain | None = Relationship(back_populates="stores")

    name: str
    number: str
    external_ref: dict | None = Field(default=None, sa_column=Column(JSONB))
    address_line1: str
    address_line2: str | None = Field(default=None)
    city: str
    region: str
    postal_code: str
    country_code: str = Field(sa_column=Column(String(2)))
    latitude: float = Field(sa_column=Column(Float))
    longitude: float = Field(sa_column=Column(Float))
    timezone: str
    hours_json: dict | None = Field(default=None, sa_column=Column(JSONB))
    phone: str
    geography: Geography = Field(
        default=None,
        sa_column=Column(Geography(geometry_type="POINT", srid=4326), nullable=True),
    )

    store_products: list[StoreProduct] = Relationship(back_populates="store")
    plan_selected: list[PlanSelectedStore] = Relationship(back_populates="store")
    store_visits: list[PlanStoreVisit] = Relationship(back_populates="store")
    item_matches: list[ItemMatch] = Relationship(back_populates="store")


class Product(Base, table=True):
    __tablename__ = "products"

    brand: str
    name: str = Field(nullable=False)
    upc: str | None = Field(default=None)
    size_text: str | None = Field(default=None)
    pkg_qty_value: float | None = Field(default=None)
    pkg_qty_unit: str | None = Field(default=None)
    base_qty_value: float | None = Field(default=None)
    base_qty_unit: str | None = Field(default=None)
    embedding: list[float] | None = Field(default=None,sa_column=Column(Vector(384)))
    embedding_dim: int | None = Field(default=None)

    store_products: list[StoreProduct] = Relationship(back_populates="product")


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

    store_id: UUID = Field(
        foreign_key="stores.id", nullable=False, index=True
    )
    store: Store | None = Relationship(back_populates="store_products")

    product_id: UUID = Field(
        foreign_key="products.id", nullable=False, index=True
    )
    product: Product | None = Relationship(back_populates="store_products")

    external_sku: str
    aisle: str | None = Field(default=None)
    shelf_code: str | None = Field(default=None)
    product_url: str | None = Field(default=None)
    is_active: bool = Field(default=True, nullable=False)

    price_entries: list[PriceEntry] = Relationship(back_populates="store_product")
    plan_items: list[PlanItem] = Relationship(back_populates="store_product")
    chosen_for_matches: list[ItemMatch] = Relationship(
        back_populates="chosen_store_product",
        sa_relationship_kwargs={
            "foreign_keys": "ItemMatch.chosen_store_product_id"
        },
    )
    candidate_rows: list[ItemMatchCandidate] = Relationship(
        back_populates="store_product"
    )


class PriceEntry(Base, table=True):
    __tablename__ = "price_entries"

    store_product_id: UUID = Field(
        foreign_key="store_products.id", nullable=False, index=True
    )
    store_product: StoreProduct | None = Relationship(back_populates="price_entries")

    currency_code: str = Field(default="USD", sa_column=Column(String(3)))
    price: float = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    unit_price: float | None = Field(default=None, sa_column=Column(Numeric(12, 6), nullable=True))
    unit_price_unit: str | None = Field(default=None)
    source: str
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    valid_from: datetime | None = Field(default=None)
    valid_to: datetime | None = Field(default=None)
    is_current: bool = Field(default=True, nullable=False)

    plan_items: list[PlanItem] = Relationship(back_populates="price_entry")
    chosen_for_matches: list[ItemMatch] = Relationship(
        back_populates="chosen_price_entry",
        sa_relationship_kwargs={
            "foreign_keys": "ItemMatch.chosen_price_entry_id"
        },
    )
    candidate_refs: list[ItemMatchCandidate] = Relationship(
        back_populates="price_entry"
    )


# Route Planning ---------------------------------------------------------------


class RoutePlan(Base, table=True):
    __tablename__ = "route_plans"

    list_id: UUID = Field(
        foreign_key="shopping_lists.id", nullable=False, index=True
    )
    list: ShoppingList | None = Relationship(back_populates="route_plans")

    client_token: str = Field(nullable=False, index=True)
    status: str = Field(default="draft", nullable=False)
    opt_mode: OptimizationMode = Field(
        default=OptimizationMode.BALANCED, nullable=False
    )
    lowest_unit_price: bool = Field(default=False, nullable=False)
    max_stores: int = Field(default=3, nullable=False)
    user_latitude: float | None = Field(default=None)
    user_longitude: float | None = Field(default=None)
    total_price: float | None = Field(
        default=None, sa_column=Column(Numeric(12, 2), nullable=True)
    )
    total_distance_m: int | None = Field(default=None)
    total_travel_sec: int | None = Field(default=None)

    selected_stores: list[PlanSelectedStore] = Relationship(back_populates="plan")
    item_matches: list[ItemMatch] = Relationship(back_populates="plan")
    store_visits: list[PlanStoreVisit] = Relationship(back_populates="plan")
    jobs: list[Job] = Relationship(back_populates="plan")


class PlanSelectedStore(Base, table=True):
    __tablename__ = "plan_selected_stores"
    __table_args__ = (
        UniqueConstraint(
            "plan_id",
            "store_id",
            name="uq_plan_selected_stores_plan_store",
        ),
    )

    plan_id: UUID = Field(
        foreign_key="route_plans.id", nullable=False, index=True
    )
    plan: RoutePlan | None = Relationship(back_populates="selected_stores")

    store_id: UUID = Field(
        foreign_key="stores.id", nullable=False, index=True
    )
    store: Store | None = Relationship(back_populates="plan_selected")



class ItemMatch(Base, table=True):
    __tablename__ = "item_matches"
    __table_args__ = (
        UniqueConstraint(
            "plan_id",
            "list_item_id",
            "store_id",
            name="uq_item_matches_plan_item_store",
        ),
    )

    plan_id: UUID = Field(
        foreign_key="route_plans.id", nullable=False, index=True
    )
    plan: RoutePlan | None = Relationship(back_populates="item_matches")

    list_item_id: UUID = Field(
        foreign_key="list_items.id", nullable=False, index=True
    )
    list_item: ListItem | None = Relationship(back_populates="item_matches")

    store_id: UUID = Field(
        foreign_key="stores.id", nullable=False, index=True
    )
    store: Store | None = Relationship(back_populates="item_matches")

    chosen_store_product_id: UUID | None = Field(
        default=None, foreign_key="store_products.id", index=True
    )
    chosen_store_product: StoreProduct | None = Relationship(
        back_populates="chosen_for_matches",
        sa_relationship_kwargs={"foreign_keys": "ItemMatch.chosen_store_product_id"},
    )
    chosen_price_entry_id: UUID | None = Field(
        default=None, foreign_key="price_entries.id", index=True
    )
    chosen_price_entry: PriceEntry | None = Relationship(
        back_populates="chosen_for_matches",
        sa_relationship_kwargs={"foreign_keys": "ItemMatch.chosen_price_entry_id"},
    )
    status: MatchStatus = Field(default=MatchStatus.PENDING, nullable=False)
    notes: str | None = Field(default=None)
    updated_by_user: bool = Field(default=False, nullable=False)

    candidates: list[ItemMatchCandidate] = Relationship(back_populates="item_match")


class ItemMatchCandidate(Base, table=True):
    __tablename__ = "item_match_candidates"
    __table_args__ = (
        UniqueConstraint(
            "item_match_id",
            "rank",
            name="uq_item_match_candidates_match_rank",
        ),
    )

    item_match_id: UUID = Field(
        foreign_key="item_matches.id", nullable=False, index=True
    )
    item_match: ItemMatch | None = Relationship(back_populates="candidates")

    store_product_id: UUID = Field(
        foreign_key="store_products.id", nullable=False, index=True
    )
    store_product: StoreProduct | None = Relationship(back_populates="candidate_rows")

    price_entry_id: UUID | None = Field(
        default=None, foreign_key="price_entries.id", index=True
    )
    price_entry: PriceEntry | None = Relationship(back_populates="candidate_refs")

    rank: int
    score: float
    rejected_by_user: bool = Field(default=False, nullable=False)



class PlanStoreVisit(Base, table=True):
    __tablename__ = "plan_store_visits"
    __table_args__ = (
        UniqueConstraint(
            "plan_id",
            "sequence",
            name="uq_plan_store_visits_plan_sequence",
        ),
    )

    plan_id: UUID = Field(
        foreign_key="route_plans.id", nullable=False, index=True
    )
    plan: RoutePlan | None = Relationship(back_populates="store_visits")

    store_id: UUID = Field(
        foreign_key="stores.id", nullable=False, index=True
    )
    store: Store | None = Relationship(back_populates="store_visits")

    sequence: int = Field(nullable=False)
    travel_sec_from_prev: int | None = Field(default=None)
    distance_m_from_prev: int | None = Field(default=None)
    subtotal_price: float | None = Field(
        default=None, sa_column=Column(Numeric(12, 2), nullable=True)
    )

    plan_items: list[PlanItem] = Relationship(back_populates="plan_store_visit")


class PlanItem(Base, table=True):
    __tablename__ = "plan_items"

    plan_store_visit_id: UUID = Field(
        foreign_key="plan_store_visits.id", nullable=False, index=True
    )
    plan_store_visit: PlanStoreVisit | None = Relationship(back_populates="plan_items")

    list_item_id: UUID = Field(
        foreign_key="list_items.id", nullable=False, index=True
    )
    list_item: ListItem | None = Relationship(back_populates="plan_items")

    store_product_id: UUID | None = Field(
        default=None, foreign_key="store_products.id", index=True
    )
    store_product: StoreProduct | None = Relationship(back_populates="plan_items")

    price_entry_id: UUID | None = Field(
        default=None, foreign_key="price_entries.id", index=True
    )
    price_entry: PriceEntry | None = Relationship(back_populates="plan_items")

    qty: int = Field(default=1, nullable=False)
    per_qty_price: float | None = Field(
        default=None, sa_column=Column(Numeric(12, 2), nullable=True)
    )
    extended_price: float | None = Field(
        default=None, sa_column=Column(Numeric(12, 2), nullable=True)
    )
    is_checked: bool = Field(default=False, nullable=False)
    checked_at: datetime | None = Field(default=None)


# Job Tracking -----------------------------------------------------------------


class Job(Base, table=True):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint(
            "plan_id",
            "stage",
            name="uq_jobs_plan_stage",
        ),
    )

    plan_id: UUID = Field(
        foreign_key="route_plans.id", nullable=False, index=True
    )
    plan: RoutePlan | None = Relationship(back_populates="jobs")

    stage: JobStage = Field(default=JobStage.MATCH, nullable=False)
    status: JobStatus = Field(default=JobStatus.PENDING, nullable=False)
    progress_current: int | None = Field(default=None)
    progress_total: int | None = Field(default=None)
    task_id: str = Field(index=True)
    message: str | None = Field(default=None)


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
