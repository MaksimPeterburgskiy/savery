

from uuid import UUID

from sqlalchemy import and_, select

from backend.app.db import session_scope
from backend.app.models import ListItem, ShoppingList


def test_create_shopping_list() -> None:

    # Create a test list
    with session_scope() as session:
        #check if object exists
        statement = select(ShoppingList).where(
            and_(
                ShoppingList.client_id == "test",
                ShoppingList.id == "539d086f-d966-4b60-b15e-e24e8c0358f7",
            )
        )
        shopping_list = session.exec(statement).first()
        if shopping_list is None:
            new_shopping_list = ShoppingList(
                id=UUID("539d086f-d966-4b60-b15e-e24e8c0358f7"),
                client_id="test",
                title="Test List",
            )
            session.add(new_shopping_list)
            session.commit()
            
    # Add a test item to the list
    with session_scope() as session:
        #check if object exists
        statement = select(ListItem).where(
            and_(
                ListItem.list_id == UUID("539d086f-d966-4b60-b15e-e24e8c0358f7"),
                ListItem.id == "539d086f-d966-4b60-b15e-e24e8c0358f7",
            )
        )
        list_item = session.exec(statement).first()
        if list_item is None:
            new_list_item = ListItem(
                id=UUID("539d086f-d966-4b60-b15e-e24e8c0358f7"),
                list_id=UUID("539d086f-d966-4b60-b15e-e24e8c0358f7"),
                raw_text_qty = "2 lbs",
                raw_text_item = "apples",
                item_name = "apples",
                qty_value = 2.0,
                qty_unit = "lbs",
                norm_qty_value = 0.907184,
                norm_qty_unit = "kgs",
                position = 0,
            )
            session.add(new_list_item)
            session.commit()