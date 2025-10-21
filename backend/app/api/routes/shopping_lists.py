"""Store catalog endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload

from backend.app.dependencies import get_db
from backend.app.models import ShoppingList, ListItem

router = APIRouter()

auth_scheme = HTTPBearer(auto_error=False)


class ShoppingListWithItemsResponse(BaseModel):
    """Response model for shopping list with items."""
    id: UUID
    client_id: str | None
    title: str | None
    created_at: datetime
    updated_at: datetime
    list_items: list[ListItem]

    class Config:
        from_attributes = True


# User's Shopping Lists Endpoints -----------------------------------------------------
#TODO: instead of going by /client_id, we should have an auth system and go by inferred user identity
#Get all shopping lists for a given user by client_id
@router.get("/shopping_lists/{client_id}", response_model=Sequence[ShoppingList], summary="Get a user's shopping list")
async def get_shopping_lists_for_user(client_id: str, session: Session = Depends(get_db)) -> Sequence[ShoppingList]:
    """Return all shopping lists for a given user."""

    statement = select(ShoppingList).where(ShoppingList.client_id == client_id)
    shopping_lists = session.exec(statement).all()
    return shopping_lists


#Create a new shopping list for a certain user
@router.post("/shopping_lists/{client_id}", response_model=ShoppingList, summary="Create a new shopping list")
async def create_shopping_list_for_user(client_id: str, shopping_list: ShoppingList, session: Session = Depends(get_db)) -> ShoppingList:
    """Create a new shopping list for a given user."""

    new_shopping_list = ShoppingList(
        client_id=client_id,
        title=shopping_list.title,
    )
    session.add(new_shopping_list)
    session.commit()
    session.refresh(new_shopping_list)
    return new_shopping_list



# Individual Shopping List Endpoints ------------------------------------------------------

#Get a shopping list and associated items by its id
@router.get("/shopping_list/{shopping_list_id}", response_model=ShoppingListWithItemsResponse, summary="Get a shopping list")
async def get_shopping_list_by_id(shopping_list_id: str, session: Session = Depends(get_db)) -> ShoppingListWithItemsResponse:
    """Return a shopping list and it's items by its ID."""

    statement = (
        select(ShoppingList)
        .where(ShoppingList.id == UUID(shopping_list_id))
        .options(selectinload(ShoppingList.list_items))
    )
    shopping_list = session.exec(statement).first()
    if shopping_list is None:
        raise HTTPException(status_code=404, detail="Shopping list not found")

    # Sort list items by position
    shopping_list.list_items.sort(key=lambda item: item.position)

    return ShoppingListWithItemsResponse.model_validate(shopping_list)


#Update a shopping list and its associated items by its id
@router.put("/shopping_list/{shopping_list_id}", response_model=ShoppingListWithItemsResponse, summary="Update a shopping list")
async def update_shopping_list_by_id(shopping_list_id: str, updated_shopping_list: ShoppingListWithItemsResponse, session: Session = Depends(get_db)) -> ShoppingListWithItemsResponse:
    """Update a shopping list and its items by its ID."""

    statement = select(ShoppingList).where(ShoppingList.id == UUID(shopping_list_id))
    shopping_list = session.exec(statement).first()
    if shopping_list is None:
        raise HTTPException(status_code=404, detail="Shopping list not found")

    # Update shopping list fields
    shopping_list.title = updated_shopping_list.title
    shopping_list.updated_at = datetime.now(timezone.utc)

    # Update list items
    existing_item_ids = {item.id for item in shopping_list.list_items}
    updated_item_ids = {item.id for item in updated_shopping_list.list_items if item.id is not None}

    # Delete removed items
    for item in shopping_list.list_items:
        if item.id not in updated_item_ids:
            session.delete(item)

    # Add or update items
    for item_data in updated_shopping_list.list_items:
        if item_data.id in existing_item_ids:
            # Update existing item
            item = next((i for i in shopping_list.list_items if i.id == item_data.id), None)
            if item:
                item.raw_text_qty = item_data.raw_text_qty
                item.raw_text_item = item_data.raw_text_item
                item.item_name = item_data.item_name
                item.qty_value = item_data.qty_value
                item.qty_unit = item_data.qty_unit
                item.norm_qty_value = item_data.norm_qty_value
                item.norm_qty_unit = item_data.norm_qty_unit
                item.position = item_data.position
        else:
            # Add new item
            new_item = ListItem(
                list_id=shopping_list.id,
                raw_text_qty=item_data.raw_text_qty,
                raw_text_item=item_data.raw_text_item,
                item_name=item_data.item_name,
                qty_value=item_data.qty_value,
                qty_unit=item_data.qty_unit,
                norm_qty_value=item_data.norm_qty_value,
                norm_qty_unit=item_data.norm_qty_unit,
                position=item_data.position
            )
            session.add(new_item)

    session.commit()
    session.refresh(shopping_list)

    # Reload list items with eager loading
    statement = (
        select(ShoppingList)
        .where(ShoppingList.id == shopping_list.id)
        .options(selectinload(ShoppingList.list_items))
    )
    updated_shopping_list = session.exec(statement).first()
    if updated_shopping_list and updated_shopping_list.list_items:
        updated_shopping_list.list_items.sort(key=lambda item: item.position)

    return ShoppingListWithItemsResponse.model_validate(updated_shopping_list)


# Delete a shopping list and its items by its id
@router.delete("/shopping_list/{shopping_list_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a shopping list")
async def delete_shopping_list_by_id(shopping_list_id: str, session: Session = Depends(get_db)) -> Response:
    """Delete a shopping list by its ID."""

    statement = select(ShoppingList).where(ShoppingList.id == UUID(shopping_list_id))
    shopping_list = session.exec(statement).first()
    if shopping_list is None:
        raise HTTPException(status_code=404, detail="Shopping list not found")

    # Delete all items associated with the shopping list
    for item in shopping_list.list_items:
        session.delete(item)

    session.delete(shopping_list)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)



