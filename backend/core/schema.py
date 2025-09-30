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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from geoalchemy2 import Geography  # type: ignore
from pgvector.sqlalchemy import Vector  # type: ignore


# Base class -------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


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


# Utility defaults
_gen_uuid = "gen_random_uuid()"
_now = "now()"


# Shopping Lists ---------------------------------------------------------------


class ShoppingList(Base):
    __tablename__ = "shopping_lists"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=f"{_gen_uuid}",
    )
    client_id: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=_now, nullable=False
    )

    list_items = relationship(
        "ListItem", back_populates="list", cascade="all,delete-orphan"
    )
    route_plans = relationship("RoutePlan", back_populates="list")


class ListItem(Base):
    __tablename__ = "list_items"
    __table_args__ = (Index("ix_list_items_list_id_position", "list_id", "position"),)

    id: Mapped[int] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=_gen_uuid
    )
    list_id = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shopping_lists.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    raw_text_qty = mapped_column(Text)
    raw_text_item = mapped_column(Text)
    item_name = mapped_column(Text)
    qty_value = mapped_column(Numeric)
    qty_unit = mapped_column(String)
    norm_qty_value = mapped_column(Numeric)
    norm_qty_unit = mapped_column(String)
    position = mapped_column(Integer)
    created_at = mapped_column(
        DateTime(timezone=True), server_default=_now, nullable=False
    )
    updated_at = mapped_column(
        DateTime(timezone=True), server_default=_now, nullable=False
    )

    list = relationship("ShoppingList", back_populates="list_items")
    item_matches = relationship("ItemMatch", back_populates="list_item")
    plan_items = relationship("PlanItem", back_populates="list_item")


# Store & Product Catalog ------------------------------------------------------


class StoreChain(Base):
    __tablename__ = "store_chains"

    id = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=_gen_uuid)
    name = mapped_column(Text)
    slug = mapped_column(Text, unique=True, index=True)
    created_at = mapped_column(
        DateTime(timezone=True), server_default=_now, nullable=False
    )
    updated_at = mapped_column(
        DateTime(timezone=True), server_default=_now, nullable=False
    )

    stores = relationship("Store", back_populates="chain")


class Store(Base):
    __tablename__ = "stores"

    id = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=_gen_uuid)
    chain_id = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("store_chains.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name = mapped_column(Text)
    number = mapped_column(Text)
    external_ref = mapped_column(JSON)
    address_line1 = mapped_column(Text)
    address_line2 = mapped_column(Text)
    city = mapped_column(Text)
    region = mapped_column(Text)
    postal_code = mapped_column(Text)
    country_code = mapped_column(String(2))
    latitude = mapped_column(Float)
    longitude = mapped_column(Float)
    timezone = mapped_column(Text)
    hours_json = mapped_column(JSON)
    phone = mapped_column(Text)
    created_at = mapped_column(
        DateTime(timezone=True), server_default=_now, nullable=False
    )
    updated_at = mapped_column(
        DateTime(timezone=True), server_default=_now, nullable=False
    )
    geography = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=True
    )

    chain = relationship("StoreChain", back_populates="stores")
    store_products = relationship("StoreProduct", back_populates="store")
    plan_selected = relationship("PlanSelectedStore", back_populates="store")
    store_visits = relationship("PlanStoreVisit", back_populates="store")
    item_matches = relationship("ItemMatch", back_populates="store")


class Product(Base):
    __tablename__ = "products"

    id = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=_gen_uuid)
    brand = mapped_column(Text)
    name = mapped_column(Text, nullable=False)
    upc = mapped_column(Text)
    size_text = mapped_column(Text)
    pkg_qty_value = mapped_column(Numeric)
    pkg_qty_unit = mapped_column(String)
    base_qty_value = mapped_column(Numeric)
    base_qty_unit = mapped_column(String)
    embedding = mapped_column(Vector(384))  # type: ignore
    embedding_dim = mapped_column(Integer)
    created_at = mapped_column(
        DateTime(timezone=True), server_default=_now, nullable=False
    )
    updated_at = mapped_column(
        DateTime(timezone=True), server_default=_now, nullable=False
    )

    store_products = relationship("StoreProduct", back_populates="product")


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

    id = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=_gen_uuid)
    store_id = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_sku = mapped_column(Text)
    aisle = mapped_column(Text)
    shelf_code = mapped_column(Text)
    product_url = mapped_column(Text)
    is_active = mapped_column(Boolean, server_default="true", nullable=False)
    created_at = mapped_column(
        DateTime(timezone=True), server_default=_now, nullable=False
    )
    updated_at = mapped_column(
        DateTime(timezone=True), server_default=_now, nullable=False
    )

    store = relationship("Store", back_populates="store_products")
    product = relationship("Product", back_populates="store_products")
    price_entries = relationship("PriceEntry", back_populates="store_product")
    plan_items = relationship("PlanItem", back_populates="store_product")
    chosen_for_matches = relationship(
        "ItemMatch", back_populates="chosen_store_product"
    )
    candidate_rows = relationship("ItemMatchCandidate", back_populates="store_product")


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

    id = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=_gen_uuid)
    store_product_id = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("store_products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    currency_code = mapped_column(String(3), nullable=False, server_default="USD")
    price = mapped_column(Numeric(12, 2))
    unit_price = mapped_column(Numeric(12, 6))
    unit_price_unit = mapped_column(String)
    source = mapped_column(Text)
    fetched_at = mapped_column(
        DateTime(timezone=True), server_default=_now, nullable=False
    )
    valid_from = mapped_column(DateTime(timezone=True))
    valid_to = mapped_column(DateTime(timezone=True))
    is_current = mapped_column(Boolean, server_default="true", nullable=False)

    store_product = relationship("StoreProduct", back_populates="price_entries")
    plan_items = relationship("PlanItem", back_populates="price_entry")
    chosen_for_matches = relationship("ItemMatch", back_populates="chosen_price_entry")
    candidate_refs = relationship("ItemMatchCandidate", back_populates="price_entry")


# Route Planning ---------------------------------------------------------------


class RoutePlan(Base):
    __tablename__ = "route_plans"
    __table_args__ = (
        Index("ix_route_plans_list_id", "list_id"),
        Index("ix_route_plans_client_token", "client_token"),
    )

    id = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=_gen_uuid)
    list_id = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shopping_lists.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_token = mapped_column(String, nullable=False, index=True)
    status = mapped_column(String, nullable=False, server_default="draft")
    opt_mode = mapped_column(
        SAEnum(OptimizationMode, name="optimization_mode"),
        nullable=False,
        server_default="BALANCED",
    )
    lowest_unit_price = mapped_column(Boolean, server_default="false", nullable=False)
    max_stores = mapped_column(Integer, server_default="3")
    user_latitude = mapped_column(Float)
    user_longitude = mapped_column(Float)
    total_price = mapped_column(Numeric(12, 2))
    total_distance_m = mapped_column(Integer)
    total_travel_sec = mapped_column(Integer)
    created_at = mapped_column(
        DateTime(timezone=True), server_default=_now, nullable=False
    )
    updated_at = mapped_column(
        DateTime(timezone=True), server_default=_now, nullable=False
    )

    list = relationship("ShoppingList", back_populates="route_plans")
    selected_stores = relationship(
        "PlanSelectedStore", back_populates="plan", cascade="all,delete-orphan"
    )
    item_matches = relationship(
        "ItemMatch", back_populates="plan", cascade="all,delete-orphan"
    )
    store_visits = relationship(
        "PlanStoreVisit", back_populates="plan", cascade="all,delete-orphan"
    )
    jobs = relationship("Job", back_populates="plan", cascade="all,delete-orphan")


class PlanSelectedStore(Base):
    __tablename__ = "plan_selected_stores"
    __table_args__ = (
        UniqueConstraint(
            "plan_id", "store_id", name="uq_plan_selected_stores_plan_store"
        ),
    )

    id = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=_gen_uuid)
    plan_id = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("route_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    store_id = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = mapped_column(
        DateTime(timezone=True), server_default=_now, nullable=False
    )

    plan = relationship("RoutePlan", back_populates="selected_stores")
    store = relationship("Store", back_populates="plan_selected")


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

    id = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=_gen_uuid)
    plan_id = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("route_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    list_item_id = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("list_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    store_id = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = mapped_column(
        SAEnum(MatchStatus, name="match_status"),
        nullable=False,
        server_default="PENDING",
    )
    chosen_store_product_id = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("store_products.id", ondelete="SET NULL"),
    )
    chosen_price_entry_id = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("price_entries.id", ondelete="SET NULL"),
    )
    notes = mapped_column(Text)
    updated_by_user = mapped_column(Boolean, server_default="false", nullable=False)
    created_at = mapped_column(
        DateTime(timezone=True), server_default=_now, nullable=False
    )
    updated_at = mapped_column(
        DateTime(timezone=True), server_default=_now, nullable=False
    )

    plan = relationship("RoutePlan", back_populates="item_matches")
    list_item = relationship("ListItem", back_populates="item_matches")
    store = relationship("Store", back_populates="item_matches")
    chosen_store_product = relationship(
        "StoreProduct", back_populates="chosen_for_matches"
    )
    chosen_price_entry = relationship("PriceEntry", back_populates="chosen_for_matches")
    candidates = relationship(
        "ItemMatchCandidate", back_populates="item_match", cascade="all,delete-orphan"
    )


class ItemMatchCandidate(Base):
    __tablename__ = "item_match_candidates"
    __table_args__ = (
        UniqueConstraint(
            "item_match_id", "rank", name="uq_item_match_candidates_match_rank"
        ),
    )

    id = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=_gen_uuid)
    item_match_id = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("item_matches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    store_product_id = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("store_products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    price_entry_id = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("price_entries.id", ondelete="SET NULL"),
    )
    rank = mapped_column(Integer)
    score = mapped_column(Numeric(6, 3))
    rejected_by_user = mapped_column(Boolean, server_default="false", nullable=False)
    created_at = mapped_column(
        DateTime(timezone=True), server_default=_now, nullable=False
    )

    item_match = relationship("ItemMatch", back_populates="candidates")
    store_product = relationship("StoreProduct", back_populates="candidate_rows")
    price_entry = relationship("PriceEntry", back_populates="candidate_refs")


class PlanStoreVisit(Base):
    __tablename__ = "plan_store_visits"
    __table_args__ = (
        UniqueConstraint(
            "plan_id", "sequence", name="uq_plan_store_visits_plan_sequence"
        ),
    )

    id = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=_gen_uuid)
    plan_id = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("route_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    store_id = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence = mapped_column(Integer, nullable=False)
    travel_sec_from_prev = mapped_column(Integer)
    distance_m_from_prev = mapped_column(Integer)
    subtotal_price = mapped_column(Numeric(12, 2))
    created_at = mapped_column(
        DateTime(timezone=True), server_default=_now, nullable=False
    )
    updated_at = mapped_column(
        DateTime(timezone=True), server_default=_now, nullable=False
    )

    plan = relationship("RoutePlan", back_populates="store_visits")
    store = relationship("Store", back_populates="store_visits")
    plan_items = relationship(
        "PlanItem", back_populates="plan_store_visit", cascade="all,delete-orphan"
    )


class PlanItem(Base):
    __tablename__ = "plan_items"
    __table_args__ = (
        Index("ix_plan_items_plan_store_visit_id", "plan_store_visit_id"),
        Index("ix_plan_items_list_item_id", "list_item_id"),
    )

    id = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=_gen_uuid)
    plan_store_visit_id = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("plan_store_visits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    list_item_id = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("list_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    store_product_id = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("store_products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    price_entry_id = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("price_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    qty = mapped_column(Integer, nullable=False, server_default="1")
    per_qty_price = mapped_column(Numeric(12, 2))
    extended_price = mapped_column(Numeric(12, 2))
    is_checked = mapped_column(Boolean, server_default="false", nullable=False)
    checked_at = mapped_column(DateTime(timezone=True))
    created_at = mapped_column(
        DateTime(timezone=True), server_default=_now, nullable=False
    )
    updated_at = mapped_column(
        DateTime(timezone=True), server_default=_now, nullable=False
    )

    plan_store_visit = relationship("PlanStoreVisit", back_populates="plan_items")
    list_item = relationship("ListItem", back_populates="plan_items")
    store_product = relationship("StoreProduct", back_populates="plan_items")
    price_entry = relationship("PriceEntry", back_populates="plan_items")


# Job Tracking -----------------------------------------------------------------


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("plan_id", "stage", name="uq_jobs_plan_stage"),
        Index("ix_jobs_task_id", "task_id"),
    )

    id = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=_gen_uuid)
    plan_id = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("route_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stage = mapped_column(SAEnum(JobStage, name="job_stage"), nullable=False)
    status = mapped_column(
        SAEnum(JobStatus, name="job_status"),
        nullable=False,
        server_default="PENDING",
    )
    progress_current = mapped_column(Integer)
    progress_total = mapped_column(Integer)
    task_id = mapped_column(String, index=True)
    message = mapped_column(Text)
    created_at = mapped_column(
        DateTime(timezone=True), server_default=_now, nullable=False
    )
    updated_at = mapped_column(
        DateTime(timezone=True), server_default=_now, nullable=False
    )

    plan = relationship("RoutePlan", back_populates="jobs")
