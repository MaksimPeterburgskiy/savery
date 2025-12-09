"""Shopping list HTTP endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from backend.app.dependencies import get_db
from backend.app.models import ListItem, ShoppingList
from backend.app.parsing import ItemParser

from .lists_helpers import _apply_parsed_fields, _get_list_item_or_404, _get_shopping_list_or_404
from .lists_schemas import ListItemCreate, ListItemResponse, ListItemUpdate, ShoppingListCreate, ShoppingListResponse, ShoppingListUpdate

router = APIRouter()
item_parser = ItemParser()


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

    parsed = item_parser.parse(raw_text_item=payload.raw_text_item, raw_text_qty=payload.raw_text_qty)
    item = ListItem(
        list_id=shopping_list_id,
        raw_text_qty=payload.raw_text_qty,
        raw_text_item=payload.raw_text_item,
        position=payload.position,
    )
    _apply_parsed_fields(item, parsed)
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

    if "raw_text_qty" in update_fields or "raw_text_item" in update_fields:
        parsed = item_parser.parse(raw_text_item=item.raw_text_item, raw_text_qty=item.raw_text_qty)
        _apply_parsed_fields(item, parsed)

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


__all__ = ["router"]
