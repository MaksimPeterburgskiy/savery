"""Database helpers for shopping list routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlmodel import Session

from backend.app.models import ListItem, ShoppingList
from backend.app.parsing import ParsedItem


def _get_shopping_list_or_404(session: Session, shopping_list_id: UUID) -> ShoppingList:
    shopping_list = session.get(ShoppingList, shopping_list_id)
    if shopping_list is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shopping list not found")
    return shopping_list


def _get_list_item_or_404(session: Session, shopping_list_id: UUID, item_id: UUID) -> ListItem:
    item = session.get(ListItem, item_id)
    if item is None or item.list_id != shopping_list_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="List item not found")
    return item


def _apply_parsed_fields(item: ListItem, parsed: ParsedItem) -> None:
    """Copy parsed values to the ListItem model."""

    item.item_name = parsed.name or None
    item.qty_value = parsed.quantity
    item.qty_unit = parsed.unit
    item.norm_qty_value = parsed.normalized_quantity
    item.norm_qty_unit = parsed.normalized_unit


__all__ = [
    "_apply_parsed_fields",
    "_get_list_item_or_404",
    "_get_shopping_list_or_404",
]
