"""Integration tests for the shopping list API endpoints."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from backend.app.db import session_scope
from backend.app.main import create_app
from backend.app.models import ListItem, ShoppingList


@pytest.fixture()
def client() -> TestClient:
    """Provide a FastAPI test client for the shopping list routes."""

    with TestClient(create_app()) as test_client:
        yield test_client


def cleanup_shopping_list(shopping_list_id: UUID) -> None:
    """Remove a shopping list and any associated items from the database."""

    with session_scope() as session:
        items = session.exec(select(ListItem).where(ListItem.list_id == shopping_list_id)).all()
        for item in items:
            session.delete(item)

        shopping_list = session.exec(select(ShoppingList).where(ShoppingList.id == shopping_list_id)).first()
        if shopping_list:
            session.delete(shopping_list)


# Shopping List Tests ---------------------------------------------------------


def test_list_shopping_lists_with_no_filter_returns_all(client: TestClient) -> None:
    """Test listing all shopping lists without client_id filter."""
    response = client.get("/api/shopping-lists")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_list_shopping_lists_filtered_by_client_id(client: TestClient) -> None:
    """Test listing shopping lists filtered by client_id."""
    client_id = f"test-client-{uuid4()}"
    created_ids: list[UUID] = []

    try:
        with session_scope() as session:
            for title in ("List 1", "List 2"):
                shopping_list = ShoppingList(client_id=client_id, title=title)
                session.add(shopping_list)
                session.flush()
                created_ids.append(shopping_list.id)

        response = client.get(f"/api/shopping-lists?client_id={client_id}")
        assert response.status_code == 200
        payload = response.json()
        returned_ids = {UUID(entry["id"]) for entry in payload}
        assert returned_ids == set(created_ids)
    finally:
        for list_id in created_ids:
            cleanup_shopping_list(list_id)


def test_create_shopping_list_creates_new_entry(client: TestClient) -> None:
    """Test creating a new shopping list."""
    client_id = f"test-client-{uuid4()}"
    created_list_id: UUID | None = None

    try:
        response = client.post(
            "/api/shopping-lists",
            json={"client_id": client_id, "title": "My New List"},
        )

        assert response.status_code == 201
        body = response.json()
        created_list_id = UUID(body["id"])
        assert body["client_id"] == client_id
        assert body["title"] == "My New List"

        with session_scope() as session:
            stored = session.exec(select(ShoppingList).where(ShoppingList.id == created_list_id)).first()
            assert stored is not None
            assert stored.client_id == client_id
            assert stored.title == "My New List"
    finally:
        if created_list_id:
            cleanup_shopping_list(created_list_id)


def test_create_shopping_list_with_null_title(client: TestClient) -> None:
    """Test creating a shopping list with null title."""
    client_id = f"test-client-{uuid4()}"
    created_list_id: UUID | None = None

    try:
        response = client.post(
            "/api/shopping-lists",
            json={"client_id": client_id, "title": None},
        )

        assert response.status_code == 201
        body = response.json()
        created_list_id = UUID(body["id"])
        assert body["title"] is None
    finally:
        if created_list_id:
            cleanup_shopping_list(created_list_id)


def test_get_shopping_list_by_id_returns_list(client: TestClient) -> None:
    """Test getting a shopping list by ID."""
    client_id = f"test-client-{uuid4()}"
    shopping_list_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Test List")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

        response = client.get(f"/api/shopping-lists/{shopping_list_id}")
        assert response.status_code == 200
        payload = response.json()
        assert UUID(payload["id"]) == shopping_list_id
        assert payload["title"] == "Test List"
    finally:
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_get_nonexistent_shopping_list_returns_404(client: TestClient) -> None:
    """Test that requesting a non-existent shopping list returns 404."""
    nonexistent_id = uuid4()
    response = client.get(f"/api/shopping-lists/{nonexistent_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Shopping list not found"


def test_update_shopping_list_title(client: TestClient) -> None:
    """Test updating a shopping list's title."""
    client_id = f"test-client-{uuid4()}"
    shopping_list_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Original Title")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

        response = client.patch(
            f"/api/shopping-lists/{shopping_list_id}",
            json={"title": "Updated Title"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["title"] == "Updated Title"

        with session_scope() as session:
            stored = session.exec(select(ShoppingList).where(ShoppingList.id == shopping_list_id)).first()
            assert stored is not None
            assert stored.title == "Updated Title"
    finally:
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_update_nonexistent_shopping_list_returns_404(client: TestClient) -> None:
    """Test that updating a non-existent shopping list returns 404."""
    nonexistent_id = uuid4()
    response = client.patch(
        f"/api/shopping-lists/{nonexistent_id}",
        json={"title": "New Title"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Shopping list not found"


def test_delete_shopping_list_removes_list_and_items(client: TestClient) -> None:
    """Test deleting a shopping list removes it and its items."""
    client_id = f"test-client-{uuid4()}"
    shopping_list_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="To Delete")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

            item = ListItem(
                list_id=shopping_list.id,
                raw_text_qty="1",
                raw_text_item="test",
                item_name="Test",
                position=1,
            )
            session.add(item)

        response = client.delete(f"/api/shopping-lists/{shopping_list_id}")
        assert response.status_code == 204

        with session_scope() as session:
            list_exists = session.exec(
                select(ShoppingList).where(ShoppingList.id == shopping_list_id)
            ).first()
            assert list_exists is None

            items = session.exec(select(ListItem).where(ListItem.list_id == shopping_list_id)).all()
            assert len(items) == 0
    finally:
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_delete_nonexistent_shopping_list_returns_404(client: TestClient) -> None:
    """Test that deleting a non-existent shopping list returns 404."""
    nonexistent_id = uuid4()
    response = client.delete(f"/api/shopping-lists/{nonexistent_id}")
    assert response.status_code == 404


# List Item Tests -------------------------------------------------------------


def test_list_items_for_shopping_list(client: TestClient) -> None:
    """Test listing items for a shopping list in correct order."""
    client_id = f"test-client-{uuid4()}"
    shopping_list_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="With Items")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

            item1 = ListItem(
                list_id=shopping_list.id,
                item_name="Apples",
                position=1,
            )
            item2 = ListItem(
                list_id=shopping_list.id,
                item_name="Bananas",
                position=2,
            )
            session.add(item1)
            session.add(item2)

        response = client.get(f"/api/shopping-lists/{shopping_list_id}/items")
        assert response.status_code == 200
        items = response.json()
        assert len(items) == 2
        assert items[0]["item_name"] == "Apples"
        assert items[0]["position"] == 1
        assert items[1]["item_name"] == "Bananas"
        assert items[1]["position"] == 2
    finally:
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_list_items_for_nonexistent_list_returns_404(client: TestClient) -> None:
    """Test listing items for non-existent shopping list returns 404."""
    nonexistent_id = uuid4()
    response = client.get(f"/api/shopping-lists/{nonexistent_id}/items")
    assert response.status_code == 404


def test_create_item_for_shopping_list(client: TestClient) -> None:
    """Test creating a new list item."""
    client_id = f"test-client-{uuid4()}"
    shopping_list_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Test List")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

        response = client.post(
            f"/api/shopping-lists/{shopping_list_id}/items",
            json={
                "raw_text_qty": "2",
                "raw_text_item": "Two Apples",
                "position": 1,
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["raw_text_item"] == "Two Apples"
        assert body["raw_text_qty"] == "2"
        assert body["item_name"] is None
        assert body["position"] == 1

        with session_scope() as session:
            items = session.exec(select(ListItem).where(ListItem.list_id == shopping_list_id)).all()
            assert len(items) == 1
            assert items[0].raw_text_item == "Two Apples"
            assert items[0].raw_text_qty == "2"
            assert items[0].item_name is None
    finally:
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_create_item_for_nonexistent_list_returns_404(client: TestClient) -> None:
    """Test creating item for non-existent shopping list returns 404."""
    nonexistent_id = uuid4()
    response = client.post(
        f"/api/shopping-lists/{nonexistent_id}/items",
        json={"raw_text_item": "Test", "position": 1},
    )
    assert response.status_code == 404


def test_create_item_rejects_readonly_fields(client: TestClient) -> None:
    """Test that create payload cannot include derived fields."""
    client_id = f"test-client-{uuid4()}"
    shopping_list_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Test List")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

        response = client.post(
            f"/api/shopping-lists/{shopping_list_id}/items",
            json={
                "raw_text_item": "Apples",
                "item_name": "Not Allowed",
                "qty_value": 1,
                "qty_unit": "count",
                "norm_qty_value": 1,
                "norm_qty_unit": "ct",
                "position": 1,
            },
        )

        assert response.status_code == 422
    finally:
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_update_list_item(client: TestClient) -> None:
    """Test updating a list item's mutable fields."""
    client_id = f"test-client-{uuid4()}"
    shopping_list_id: UUID | None = None
    item_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Test List")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

            item = ListItem(
                list_id=shopping_list.id,
                item_name="Original",
                position=1,
            )
            session.add(item)
            session.flush()
            item_id = item.id

        response = client.patch(
            f"/api/shopping-lists/{shopping_list_id}/items/{item_id}",
            json={"position": 2, "raw_text_item": "two apples"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["item_name"] == "Original"
        assert body["position"] == 2
        assert body["raw_text_item"] == "two apples"

        with session_scope() as session:
            stored_item = session.get(ListItem, item_id)
            assert stored_item is not None
            assert stored_item.position == 2
            assert stored_item.item_name == "Original"
            assert stored_item.raw_text_item == "two apples"
    finally:
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_update_list_item_rejects_readonly_fields(client: TestClient) -> None:
    """Test that derived fields cannot be updated through the API."""
    client_id = f"test-client-{uuid4()}"
    shopping_list_id: UUID | None = None
    item_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Test List")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

            item = ListItem(
                list_id=shopping_list.id,
                item_name="Original",
                qty_value=1.0,
                position=1,
            )
            session.add(item)
            session.flush()
            item_id = item.id

        response = client.patch(
            f"/api/shopping-lists/{shopping_list_id}/items/{item_id}",
            json={
                "item_name": "Updated",
                "qty_value": 3,
                "qty_unit": "each",
                "norm_qty_value": 3,
                "norm_qty_unit": "ea",
            },
        )

        assert response.status_code == 422
    finally:
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_update_nonexistent_item_returns_404(client: TestClient) -> None:
    """Test updating a non-existent item returns 404."""
    client_id = f"test-client-{uuid4()}"
    shopping_list_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Test List")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

        nonexistent_item_id = uuid4()
        response = client.patch(
            f"/api/shopping-lists/{shopping_list_id}/items/{nonexistent_item_id}",
            json={"position": 2},
        )
        assert response.status_code == 404
    finally:
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_update_item_from_different_list_returns_404(client: TestClient) -> None:
    """Test updating an item with wrong shopping list ID returns 404."""
    client_id = f"test-client-{uuid4()}"
    list_id_1: UUID | None = None
    list_id_2: UUID | None = None
    item_id: UUID | None = None

    try:
        with session_scope() as session:
            list_1 = ShoppingList(client_id=client_id, title="List 1")
            list_2 = ShoppingList(client_id=client_id, title="List 2")
            session.add(list_1)
            session.add(list_2)
            session.flush()
            list_id_1 = list_1.id
            list_id_2 = list_2.id

            item = ListItem(list_id=list_id_1, item_name="Item", position=1)
            session.add(item)
            session.flush()
            item_id = item.id

        # Try to update item using wrong list ID
        response = client.patch(
            f"/api/shopping-lists/{list_id_2}/items/{item_id}",
            json={"position": 2},
        )
        assert response.status_code == 404
    finally:
        if list_id_1:
            cleanup_shopping_list(list_id_1)
        if list_id_2:
            cleanup_shopping_list(list_id_2)


def test_delete_list_item(client: TestClient) -> None:
    """Test deleting a list item."""
    client_id = f"test-client-{uuid4()}"
    shopping_list_id: UUID | None = None
    item_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Test List")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

            item = ListItem(list_id=shopping_list.id, item_name="To Delete", position=1)
            session.add(item)
            session.flush()
            item_id = item.id

        response = client.delete(f"/api/shopping-lists/{shopping_list_id}/items/{item_id}")
        assert response.status_code == 204

        with session_scope() as session:
            stored_item = session.get(ListItem, item_id)
            assert stored_item is None
    finally:
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_delete_nonexistent_item_returns_404(client: TestClient) -> None:
    """Test deleting a non-existent item returns 404."""
    client_id = f"test-client-{uuid4()}"
    shopping_list_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Test List")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

        nonexistent_item_id = uuid4()
        response = client.delete(f"/api/shopping-lists/{shopping_list_id}/items/{nonexistent_item_id}")
        assert response.status_code == 404
    finally:
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)
