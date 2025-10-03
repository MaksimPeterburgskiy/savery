"""SQLAlchemy ORM models describing the core domain entities."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    Boolean,
    Index,
    UniqueConstraint,
    Enum as SAEnum,
)
import sqlalchemy
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from geoalchemy2 import Geography  # type: ignore
from pgvector.sqlalchemy import Vector
import sqlalchemy.orm  # type: ignore


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
class Base(DeclarativeBase):
    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default="gen_random_uuid()"
    )
    created_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)


# Shopping Lists ---------------------------------------------------------------


class ShoppingList(Base):
    __tablename__ = "shopping_lists"

    client_id: Mapped[str] = mapped_column(unique=True, index=True, nullable=True)
    title: Mapped[str] = mapped_column(nullable=True)

    list_items: Mapped[list[ListItem]] = relationship(
        back_populates="list", cascade="all, delete-orphan"
    )
    route_plans: Mapped[list[RoutePlan]] = relationship(back_populates="list")


class ListItem(Base):
    __tablename__ = "list_items"
    __table_args__ = (Index("ix_list_items_list_id_position", "list_id", "position"),)

    raw_text_qty: Mapped[str]
    raw_text_item: Mapped[str]
    item_name: Mapped[str]
    qty_value: Mapped[float]
    qty_unit: Mapped[str]
    norm_qty_value: Mapped[float]
    norm_qty_unit: Mapped[str]
    position: Mapped[int]

    list: Mapped[ShoppingList] = relationship(back_populates="list_items")
    item_matches: Mapped[list[ItemMatch]] = relationship(back_populates="list_item")
    plan_items: Mapped[list[PlanItem]] = relationship(back_populates="list_item")


# Store & Product Catalog ------------------------------------------------------


class StoreChain(Base):
    __tablename__ = "store_chains"

    name: Mapped[str]

    stores: Mapped[list[Store]] = relationship(back_populates="chain")


class Store(Base):
    __tablename__ = "stores"

    name: Mapped[str]
    number: Mapped[str]
    external_ref: Mapped[JSON]
    address_line1: Mapped[str]
    address_line2: Mapped[str]
    city: Mapped[str]
    region: Mapped[str]
    postal_code: Mapped[str]
    country_code: Mapped[str]
    latitude: Mapped[float]
    longitude: Mapped[float]
    timezone: Mapped[str]
    hours_json: Mapped[JSON]
    phone: Mapped[str]
    geography: Mapped[Geography] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=True
    )

    chain: Mapped[StoreChain] = relationship(back_populates="stores")
    store_products: Mapped[list[StoreProduct]] = relationship(back_populates="store")
    plan_selected: Mapped[list[PlanSelectedStore]] = relationship(
        back_populates="store"
    )
    store_visits: Mapped[list[PlanStoreVisit]] = relationship(back_populates="store")
    item_matches: Mapped[list[ItemMatch]] = relationship(back_populates="store")


class Product(Base):
    __tablename__ = "products"

    brand: Mapped[str]
    name: Mapped[str] = mapped_column(nullable=False)
    upc: Mapped[str]
    size_text: Mapped[str]
    pkg_qty_value: Mapped[float]
    pkg_qty_unit: Mapped[str]
    base_qty_value: Mapped[float]
    base_qty_unit: Mapped[str]
    embedding: Mapped[Vector] = mapped_column(Vector(384))
    embedding_dim: Mapped[int]

    store_products: Mapped[list[StoreProduct]] = relationship(back_populates="product")


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

    external_sku: Mapped[str]
    aisle: Mapped[str]
    shelf_code: Mapped[str]
    product_url: Mapped[str]
    is_active: Mapped[bool] = mapped_column(server_default="true", nullable=False)

    store: Mapped[Store] = relationship(back_populates="store_products")
    product: Mapped[Product] = relationship(back_populates="store_products")
    price_entries: Mapped[list[PriceEntry]] = relationship(
        back_populates="store_product"
    )
    plan_items: Mapped[list[PlanItem]] = relationship(back_populates="store_product")
    chosen_for_matches: Mapped[list[ItemMatch]] = relationship(
        back_populates="chosen_store_product"
    )
    candidate_rows: Mapped[list[ItemMatchCandidate]] = relationship(
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

    currency_code: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default="USD"
    )
    price: Mapped[float] = mapped_column(Numeric(12, 2))
    unit_price: Mapped[float] = mapped_column(Numeric(12, 6))
    unit_price_unit: Mapped[str]
    source: Mapped[str]
    valid_from: Mapped[datetime]
    valid_to: Mapped[datetime]
    is_current: Mapped[bool] = mapped_column(server_default="true", nullable=False)

    store_product: Mapped[StoreProduct] = relationship(back_populates="price_entries")
    plan_items: Mapped[list[PlanItem]] = relationship(back_populates="price_entry")
    chosen_for_matches: Mapped[list[ItemMatch]] = relationship(
        back_populates="chosen_price_entry"
    )
    candidate_refs: Mapped[list[ItemMatchCandidate]] = relationship(
        back_populates="price_entry"
    )


# Route Planning ---------------------------------------------------------------


class RoutePlan(Base):
    __tablename__ = "route_plans"
    __table_args__ = (
        Index("ix_route_plans_list_id", "list_id"),
        Index("ix_route_plans_client_token", "client_token"),
    )

    client_token: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="draft")
    opt_mode: Mapped[OptimizationMode] = mapped_column(
        SAEnum(OptimizationMode, name="optimization_mode"),
        nullable=False,
        server_default="BALANCED",
    )
    lowest_unit_price: Mapped[bool] = mapped_column(
        server_default="false", nullable=False
    )
    max_stores: Mapped[int] = mapped_column(server_default="3")
    user_latitude: Mapped[float]
    user_longitude: Mapped[float]
    total_price: Mapped[float] = mapped_column(Numeric(12, 2))
    total_distance_m: Mapped[int]
    total_travel_sec: Mapped[int]

    list: Mapped[ShoppingList] = relationship(back_populates="route_plans")
    selected_stores: Mapped[list[PlanSelectedStore]] = relationship(
        back_populates="plan", cascade="all,delete-orphan"
    )
    item_matches: Mapped[list[ItemMatch]] = relationship(
        back_populates="plan", cascade="all,delete-orphan"
    )
    store_visits: Mapped[list[PlanStoreVisit]] = relationship(
        back_populates="plan", cascade="all,delete-orphan"
    )
    jobs: Mapped[list[Job]] = relationship(
        back_populates="plan", cascade="all,delete-orphan"
    )


class PlanSelectedStore(Base):
    __tablename__ = "plan_selected_stores"
    __table_args__ = (
        UniqueConstraint(
            "plan_id", "store_id", name="uq_plan_selected_stores_plan_store"
        ),
    )

    plan: Mapped[RoutePlan] = relationship(back_populates="selected_stores")
    store: Mapped[Store] = relationship(back_populates="plan_selected")


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

    status: Mapped[MatchStatus] = mapped_column(
        SAEnum(MatchStatus, name="match_status"),
        nullable=False,
        server_default="PENDING",
    )
    notes: Mapped[str]
    updated_by_user: Mapped[bool] = mapped_column(
        server_default="false", nullable=False
    )

    plan: Mapped[RoutePlan] = relationship(back_populates="item_matches")
    list_item: Mapped[ListItem] = relationship(back_populates="item_matches")
    store: Mapped[Store] = relationship(back_populates="item_matches")
    chosen_store_product: Mapped[StoreProduct] = relationship(
        back_populates="chosen_for_matches"
    )
    chosen_price_entry: Mapped[PriceEntry] = relationship(
        back_populates="chosen_for_matches"
    )
    candidates: Mapped[list[ItemMatchCandidate]] = relationship(
        back_populates="item_match", cascade="all,delete-orphan"
    )


class ItemMatchCandidate(Base):
    __tablename__ = "item_match_candidates"
    __table_args__ = (
        UniqueConstraint(
            "item_match_id", "rank", name="uq_item_match_candidates_match_rank"
        ),
    )

    rank: Mapped[int]
    score: Mapped[float] = mapped_column(Numeric(6, 3))
    rejected_by_user: Mapped[bool] = mapped_column(server_default="false", nullable=False)

    item_match: Mapped[ItemMatch] = relationship(back_populates="candidates")
    store_product: Mapped[StoreProduct] = relationship(back_populates="candidate_rows")
    price_entry: Mapped[PriceEntry] = relationship(back_populates="candidate_refs")


class PlanStoreVisit(Base):
    __tablename__ = "plan_store_visits"
    __table_args__ = (
        UniqueConstraint(
            "plan_id", "sequence", name="uq_plan_store_visits_plan_sequence"
        ),
    )

    sequence: Mapped[int] = mapped_column( nullable=False)
    travel_sec_from_prev: Mapped[int]
    distance_m_from_prev: Mapped[int]
    subtotal_price: Mapped[float] = mapped_column(Numeric(12, 2))

    plan: Mapped[RoutePlan] = relationship(back_populates="store_visits")
    store: Mapped[Store] = relationship(back_populates="store_visits")
    plan_items: Mapped[list[PlanItem]] = relationship(
        back_populates="plan_store_visit", cascade="all,delete-orphan"
    )


class PlanItem(Base):
    __tablename__ = "plan_items"
    __table_args__ = (
        Index("ix_plan_items_plan_store_visit_id", "plan_store_visit_id"),
        Index("ix_plan_items_list_item_id", "list_item_id"),
    )

    qty: Mapped[int] = mapped_column(nullable=False, server_default="1")
    per_qty_price: Mapped[float] = mapped_column(Numeric(12, 2))
    extended_price: Mapped[float] = mapped_column(Numeric(12, 2))
    is_checked: Mapped[bool] = mapped_column(server_default="false", nullable=False)
    checked_at: Mapped[datetime]

    plan_store_visit: Mapped[PlanStoreVisit] = relationship(back_populates="plan_items")
    list_item: Mapped[ListItem] = relationship(back_populates="plan_items")
    store_product: Mapped[StoreProduct] = relationship(back_populates="plan_items")
    price_entry: Mapped[PriceEntry] = relationship(back_populates="plan_items")


# Job Tracking -----------------------------------------------------------------


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("plan_id", "stage", name="uq_jobs_plan_stage"),
        Index("ix_jobs_task_id", "task_id"),
    )

    stage: Mapped[JobStage] = mapped_column(SAEnum(JobStage, name="job_stage"), nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus, name="job_status"),
        nullable=False,
        server_default="PENDING",
    )
    progress_current: Mapped[int]
    progress_total: Mapped[int]
    task_id: Mapped[str] = mapped_column(index=True)
    message: Mapped[str]

    plan: Mapped[RoutePlan] = relationship(back_populates="jobs")
