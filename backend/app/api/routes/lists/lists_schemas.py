"""Schemas for shopping list endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ShoppingListCreate(BaseModel):
    """Payload for creating a shopping list."""

    model_config = ConfigDict(extra="forbid")

    client_id: str
    title: str | None = None


class ShoppingListUpdate(BaseModel):
    """Payload for updating a shopping list."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None


class ShoppingListResponse(BaseModel):
    """Response model for shopping list metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: str | None
    title: str | None
    created_at: datetime
    updated_at: datetime


class ListItemResponse(BaseModel):
    """Response model for a list item."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    list_id: UUID
    raw_text_qty: str | None = None
    raw_text_item: str | None = None
    item_name: str | None = None
    qty_value: float | None = None
    qty_unit: str | None = None
    norm_qty_value: float | None = None
    norm_qty_unit: str | None = None
    position: int


class ListItemCreate(BaseModel):
    """Payload for creating a list item."""

    model_config = ConfigDict(extra="forbid")

    raw_text_qty: str | None = None
    raw_text_item: str | None = None
    position: int


class ListItemUpdate(BaseModel):
    """Payload for updating a list item."""

    model_config = ConfigDict(extra="forbid")

    raw_text_qty: str | None = None
    raw_text_item: str | None = None
    position: int | None = None


__all__ = [
    "ListItemCreate",
    "ListItemResponse",
    "ListItemUpdate",
    "ShoppingListCreate",
    "ShoppingListResponse",
    "ShoppingListUpdate",
]
