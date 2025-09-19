"""SQLAlchemy ORM models describing the core domain entities."""

from __future__ import annotations

from datetime import datetime
from typing import Any

try:
    from sqlalchemy import (
        Column,
        DateTime,
        Float,
        ForeignKey,
        Integer,
        JSON,
        Numeric,
        String,
        Text,
    )
    from sqlalchemy.dialects.postgresql import JSONB
    from sqlalchemy.orm import declarative_base, relationship
except ModuleNotFoundError:  # pragma: no cover - optional during early scaffolding
    Column = lambda *args, **kwargs: None  # type: ignore
    DateTime = Float = ForeignKey = Integer = JSON = Numeric = String = Text = JSONB = Any  # type: ignore # noqa: N816
    relationship = lambda *args, **kwargs: None  # type: ignore

    def declarative_base() -> Any:  # type: ignore
        class _Base:  # noqa: D401 - simple placeholder
            """Fallback base placeholder when SQLAlchemy is unavailable."""

            metadata: Any | None = None

        return _Base

Base = declarative_base()


JSONType = JSONB

try:  # Match JSON column types to the configured database dialect.
    from backend.core.config import settings

    database_url = settings.database_url.lower()
    if database_url.startswith("postgres"):
        JSONType = JSONB
    else:
        JSONType = JSON
except Exception:  # pragma: no cover - best-effort fallback when settings unavailable
    JSONType = JSON


class Store(Base):
    """Retail store participating in optimization."""

    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(64), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    timezone = Column(String(64), nullable=True)
    metadata_blob = Column(JSONType, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    prices = relationship("Price", back_populates="store")


class Product(Base):
    """Canonical product definition aggregated across stores."""

    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(128), nullable=True)
    brand = Column(String(128), nullable=True)
    unit = Column(String(32), nullable=True)
    vector_embedding = Column(JSONType, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    prices = relationship("Price", back_populates="product")


class Price(Base):
    """Price observation for a specific product at a specific store."""

    __tablename__ = "prices"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    list_price = Column(Numeric(10, 2), nullable=False)
    promo_price = Column(Numeric(10, 2), nullable=True)
    unit = Column(String(32), nullable=True)
    currency = Column(String(8), default="USD", nullable=False)
    observed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    raw_payload = Column(JSONType, nullable=True)

    store = relationship("Store", back_populates="prices")
    product = relationship("Product", back_populates="prices")


class OptimizationJob(Base):
    """Track Celery tasks and optimization results."""

    __tablename__ = "optimization_jobs"

    id = Column(Integer, primary_key=True)
    task_id = Column(String(64), unique=True, nullable=False, index=True)
    input_payload = Column(JSONType, nullable=False)
    result_payload = Column(JSONType, nullable=True)
    status = Column(String(32), default="pending", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
