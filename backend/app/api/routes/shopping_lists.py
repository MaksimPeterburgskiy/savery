"""Shopping list endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from backend.app.dependencies import get_db
from backend.app.models import ListItem, ShoppingList

router = APIRouter()


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
    item_name: str | None = None
    qty_value: float | None = None
    qty_unit: str | None = None
    norm_qty_value: float | None = None
    norm_qty_unit: str | None = None
    position: int


class ListItemUpdate(BaseModel):
    """Payload for updating a list item."""

    model_config = ConfigDict(extra="forbid")

    raw_text_qty: str | None = None
    raw_text_item: str | None = None
    item_name: str | None = None
    qty_value: float | None = None
    qty_unit: str | None = None
    norm_qty_value: float | None = None
    norm_qty_unit: str | None = None
    position: int | None = None


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


@router.get(
    "/shopping-lists",
    response_model=Sequence[ShoppingListResponse],
    summary="List shopping lists",
)
def list_shopping_lists(
    client_id: str | None = Query(default=None, description="Filter by client identifier"),
    session: Session = Depends(get_db),
) -> Sequence[ShoppingListResponse]:
    statement = select(ShoppingList)
    if client_id is not None:
        statement = statement.where(ShoppingList.client_id == client_id)
    statement = statement.order_by(ShoppingList.created_at.desc())
    return session.exec(statement).all()


@router.post(
    "/shopping-lists",
    response_model=ShoppingListResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a shopping list",
)
def create_shopping_list(
    payload: ShoppingListCreate,
    session: Session = Depends(get_db),
) -> ShoppingListResponse:
    shopping_list = ShoppingList(client_id=payload.client_id, title=payload.title)
    session.add(shopping_list)
    session.commit()
    session.refresh(shopping_list)
    return ShoppingListResponse.model_validate(shopping_list)


@router.get(
    "/shopping-lists/{shopping_list_id}",
    response_model=ShoppingListResponse,
    summary="Get a shopping list",
)
def get_shopping_list(
    shopping_list_id: UUID,
    session: Session = Depends(get_db),
) -> ShoppingListResponse:
    shopping_list = _get_shopping_list_or_404(session, shopping_list_id)
    return ShoppingListResponse.model_validate(shopping_list)


@router.patch(
    "/shopping-lists/{shopping_list_id}",
    response_model=ShoppingListResponse,
    summary="Update a shopping list",
)
def update_shopping_list(
    shopping_list_id: UUID,
    payload: ShoppingListUpdate,
    session: Session = Depends(get_db),
) -> ShoppingListResponse:
    shopping_list = _get_shopping_list_or_404(session, shopping_list_id)

    update_fields = payload.model_dump(exclude_unset=True)
    if "title" in update_fields:
        shopping_list.title = update_fields["title"]
    shopping_list.updated_at = datetime.now(timezone.utc)

    session.add(shopping_list)
    session.commit()
    session.refresh(shopping_list)
    return ShoppingListResponse.model_validate(shopping_list)


@router.delete(
    "/shopping-lists/{shopping_list_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a shopping list",
)
def delete_shopping_list(
    shopping_list_id: UUID,
    session: Session = Depends(get_db),
) -> Response:
    shopping_list = session.exec(
        select(ShoppingList)
        .where(ShoppingList.id == shopping_list_id)
        .options(
            selectinload(ShoppingList.list_items),
            selectinload(ShoppingList.route_plans),
        )
    ).first()
    if shopping_list is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shopping list not found")

    session.delete(shopping_list)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/shopping-lists/{shopping_list_id}/items",
    response_model=list[ListItemResponse],
    summary="List items for a shopping list",
)
def list_items(
    shopping_list_id: UUID,
    session: Session = Depends(get_db),
) -> list[ListItemResponse]:
    _get_shopping_list_or_404(session, shopping_list_id)
    items = session.exec(select(ListItem).where(ListItem.list_id == shopping_list_id).order_by(ListItem.position)).all()
    return [ListItemResponse.model_validate(item) for item in items]


@router.post(
    "/shopping-lists/{shopping_list_id}/items",
    response_model=ListItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a list item",
)
def create_item(
    shopping_list_id: UUID,
    payload: ListItemCreate,
    session: Session = Depends(get_db),
) -> ListItemResponse:
    _get_shopping_list_or_404(session, shopping_list_id)

    item = ListItem(list_id=shopping_list_id, **payload.model_dump())
    session.add(item)
    session.commit()
    session.refresh(item)
    return ListItemResponse.model_validate(item)


@router.patch(
    "/shopping-lists/{shopping_list_id}/items/{item_id}",
    response_model=ListItemResponse,
    summary="Update a list item",
)
def update_item(
    shopping_list_id: UUID,
    item_id: UUID,
    payload: ListItemUpdate,
    session: Session = Depends(get_db),
) -> ListItemResponse:
    item = _get_list_item_or_404(session, shopping_list_id, item_id)

    update_fields = payload.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(item, field, value)

    session.add(item)
    session.commit()
    session.refresh(item)
    return ListItemResponse.model_validate(item)


@router.delete(
    "/shopping-lists/{shopping_list_id}/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a list item",
)
def delete_item(
    shopping_list_id: UUID,
    item_id: UUID,
    session: Session = Depends(get_db),
) -> Response:
    item = _get_list_item_or_404(session, shopping_list_id, item_id)
    session.delete(item)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
