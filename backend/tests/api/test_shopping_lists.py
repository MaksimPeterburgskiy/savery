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
        items = session.exec(
            select(ListItem).where(ListItem.list_id == shopping_list_id)
        ).all()
        for item in items:
            session.delete(item)

        shopping_list = session.exec(
            select(ShoppingList).where(ShoppingList.id == shopping_list_id)
        ).first()
        if shopping_list:
            session.delete(shopping_list)


def test_get_shopping_lists_for_user_returns_expected_lists(client: TestClient) -> None:
    client_id = f"shopping-list-user-{uuid4()}"
    created_ids: list[UUID] = []

    try:
        with session_scope() as session:
            for title in ("Weekly Groceries", "Party Supplies"):
                shopping_list = ShoppingList(client_id=client_id, title=title)
                session.add(shopping_list)
                session.flush()
                created_ids.append(shopping_list.id)

        response = client.get(f"/api/shopping_lists/{client_id}")

        assert response.status_code == 200
        payload = response.json()
        returned_ids = {UUID(entry["id"]) for entry in payload}
        assert returned_ids == set(created_ids)
        returned_titles = {entry["title"] for entry in payload}
        assert returned_titles == {"Weekly Groceries", "Party Supplies"}
    finally:
        for list_id in created_ids:
            cleanup_shopping_list(list_id)


def test_create_shopping_list_for_user_creates_new_entry(client: TestClient) -> None:
    client_id = f"shopping-list-user-{uuid4()}"
    created_list_id: UUID | None = None

    try:
        response = client.post(
            f"/api/shopping_lists/{client_id}",
            json={"title": "My New List"},
        )

        assert response.status_code == 200
        body = response.json()
        created_list_id = UUID(body["id"])
        assert body["client_id"] == client_id
        assert body["title"] == "My New List"

        with session_scope() as session:
            stored = session.exec(
                select(ShoppingList).where(ShoppingList.id == created_list_id)
            ).first()
            assert stored is not None
            assert stored.client_id == client_id
            assert stored.title == "My New List"
    finally:
        if created_list_id:
            cleanup_shopping_list(created_list_id)


def test_get_shopping_list_by_id_returns_sorted_items(client: TestClient) -> None:
    client_id = f"shopping-list-user-{uuid4()}"
    shopping_list_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="With Items")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

            later_item = ListItem(
                list_id=shopping_list.id,
                raw_text_qty="3",
                raw_text_item="pears",
                item_name="Pears",
                qty_value=3.0,
                qty_unit="count",
                norm_qty_value=3.0,
                norm_qty_unit="count",
                position=2,
            )
            early_item = ListItem(
                list_id=shopping_list.id,
                raw_text_qty="1",
                raw_text_item="milk",
                item_name="Milk",
                qty_value=1.0,
                qty_unit="gallon",
                norm_qty_value=3.785,
                norm_qty_unit="liter",
                position=1,
            )
            session.add(later_item)
            session.add(early_item)

        response = client.get(f"/api/shopping_list/{shopping_list_id}")

        assert response.status_code == 200
        payload = response.json()
        assert UUID(payload["id"]) == shopping_list_id
        positions = [item["position"] for item in payload["list_items"]]
        assert positions == [1, 2]
        names_in_order = [item["item_name"] for item in payload["list_items"]]
        assert names_in_order == ["Milk", "Pears"]
    finally:
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_update_shopping_list_by_id_manages_items(client: TestClient) -> None:
    client_id = f"shopping-list-user-{uuid4()}"
    shopping_list_id: UUID | None = None
    removed_item_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Original Title")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

            first_item = ListItem(
                list_id=shopping_list.id,
                raw_text_qty="1",
                raw_text_item="bread",
                item_name="Bread",
                qty_value=1.0,
                qty_unit="loaf",
                norm_qty_value=1.0,
                norm_qty_unit="loaf",
                position=1,
            )
            second_item = ListItem(
                list_id=shopping_list.id,
                raw_text_qty="2",
                raw_text_item="eggs",
                item_name="Eggs",
                qty_value=2.0,
                qty_unit="dozen",
                norm_qty_value=24.0,
                norm_qty_unit="count",
                position=2,
            )
            session.add(first_item)
            session.add(second_item)

        original = client.get(f"/api/shopping_list/{shopping_list_id}").json()
        removed_item_id = UUID(original["list_items"][1]["id"])

        original["title"] = "Updated Title"
        existing_item = original["list_items"][0]
        existing_item["raw_text_qty"] = "3"
        existing_item["raw_text_item"] = "bananas"
        existing_item["item_name"] = "Bananas"
        existing_item["qty_value"] = 3.0
        existing_item["qty_unit"] = "bunch"
        existing_item["norm_qty_value"] = 3.0
        existing_item["norm_qty_unit"] = "bunch"
        existing_item["position"] = 1

        new_item = {
            "list_id": str(shopping_list_id),
            "raw_text_qty": "6",
            "raw_text_item": "oranges",
            "item_name": "Oranges",
            "qty_value": 6.0,
            "qty_unit": "count",
            "norm_qty_value": 6.0,
            "norm_qty_unit": "count",
            "position": 2,
        }
        original["list_items"] = [existing_item, new_item]

        update_response = client.put(
            f"/api/shopping_list/{shopping_list_id}", json=original
        )

        assert update_response.status_code == 200
        updated_payload = update_response.json()
        assert updated_payload["title"] == "Updated Title"
        assert [item["position"] for item in updated_payload["list_items"]] == [1, 2]
        item_names = {item["item_name"] for item in updated_payload["list_items"]}
        assert item_names == {"Bananas", "Oranges"}

        with session_scope() as session:
            stored_list = session.exec(
                select(ShoppingList).where(ShoppingList.id == shopping_list_id)
            ).first()
            assert stored_list is not None
            assert stored_list.title == "Updated Title"

            stored_items = session.exec(
                select(ListItem).where(ListItem.list_id == shopping_list_id)
            ).all()
            assert {item.item_name for item in stored_items} == {"Bananas", "Oranges"}
            assert all(item.position in (1, 2) for item in stored_items)
            assert removed_item_id not in {item.id for item in stored_items}
    finally:
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_delete_shopping_list_by_id_removes_records(client: TestClient) -> None:
    client_id = f"shopping-list-user-{uuid4()}"
    shopping_list_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="To Be Deleted")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

            list_item = ListItem(
                list_id=shopping_list.id,
                raw_text_qty="4",
                raw_text_item="apples",
                item_name="Apples",
                qty_value=4.0,
                qty_unit="count",
                norm_qty_value=4.0,
                norm_qty_unit="count",
                position=1,
            )
            session.add(list_item)

        response = client.delete(f"/api/shopping_list/{shopping_list_id}")

        assert response.status_code == 204

        with session_scope() as session:
            list_exists = session.exec(
                select(ShoppingList).where(ShoppingList.id == shopping_list_id)
            ).first()
            assert list_exists is None
            remaining_items = session.exec(
                select(ListItem).where(ListItem.list_id == shopping_list_id)
            ).all()
            assert remaining_items == []
    finally:
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


# Error Handling Tests --------------------------------------------------------


def test_get_nonexistent_shopping_list_returns_404(client: TestClient) -> None:
    """Test that requesting a non-existent shopping list returns 404."""
    nonexistent_id = uuid4()
    response = client.get(f"/api/shopping_list/{nonexistent_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Shopping list not found"


def test_get_shopping_list_with_invalid_uuid_returns_error(client: TestClient) -> None:
    """Test that requesting a shopping list with invalid UUID format returns error."""
    invalid_uuid = "not-a-valid-uuid"
    response = client.get(f"/api/shopping_list/{invalid_uuid}")

    assert response.status_code == 422 or response.status_code == 500


def test_update_nonexistent_shopping_list_returns_404(client: TestClient) -> None:
    """Test that updating a non-existent shopping list returns 404."""
    nonexistent_id = uuid4()

    update_data = {
        "id": str(nonexistent_id),
        "client_id": "test-client",
        "title": "Test",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
        "list_items": [],
    }

    response = client.put(f"/api/shopping_list/{nonexistent_id}", json=update_data)

    assert response.status_code == 404
    assert response.json()["detail"] == "Shopping list not found"


def test_update_shopping_list_with_invalid_uuid_returns_error(
    client: TestClient,
) -> None:
    """Test that updating a shopping list with invalid UUID format returns error."""
    invalid_uuid = "not-a-valid-uuid"

    update_data = {
        "id": invalid_uuid,
        "client_id": "test-client",
        "title": "Test",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
        "list_items": [],
    }

    response = client.put(f"/api/shopping_list/{invalid_uuid}", json=update_data)

    assert response.status_code == 422 or response.status_code == 500


def test_delete_nonexistent_shopping_list_returns_404(client: TestClient) -> None:
    """Test that deleting a non-existent shopping list returns 404."""
    nonexistent_id = uuid4()

    response = client.delete(f"/api/shopping_list/{nonexistent_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Shopping list not found"


def test_delete_shopping_list_with_invalid_uuid_returns_error(
    client: TestClient,
) -> None:
    """Test that deleting a shopping list with invalid UUID format returns error."""
    invalid_uuid = "not-a-valid-uuid"

    response = client.delete(f"/api/shopping_list/{invalid_uuid}")

    assert response.status_code == 422 or response.status_code == 500


# Edge Case Tests -------------------------------------------------------------


def test_get_shopping_lists_for_user_with_no_lists(client: TestClient) -> None:
    """Test that getting shopping lists for a user with no lists returns empty list."""
    client_id = f"shopping-list-user-{uuid4()}"

    response = client.get(f"/api/shopping_lists/{client_id}")

    assert response.status_code == 200
    assert response.json() == []


def test_create_shopping_list_with_null_title(client: TestClient) -> None:
    """Test creating a shopping list with null title."""
    client_id = f"shopping-list-user-{uuid4()}"
    created_list_id: UUID | None = None

    try:
        response = client.post(
            f"/api/shopping_lists/{client_id}",
            json={"title": None},
        )

        assert response.status_code == 200
        body = response.json()
        created_list_id = UUID(body["id"])
        assert body["title"] is None
        assert body["client_id"] == client_id
    finally:
        if created_list_id:
            cleanup_shopping_list(created_list_id)


def test_create_shopping_list_with_empty_title(client: TestClient) -> None:
    """Test creating a shopping list with empty string title."""
    client_id = f"shopping-list-user-{uuid4()}"
    created_list_id: UUID | None = None

    try:
        response = client.post(
            f"/api/shopping_lists/{client_id}",
            json={"title": ""},
        )

        assert response.status_code == 200
        body = response.json()
        created_list_id = UUID(body["id"])
        assert body["title"] == ""
        assert body["client_id"] == client_id
    finally:
        if created_list_id:
            cleanup_shopping_list(created_list_id)


def test_create_shopping_list_with_very_long_title(client: TestClient) -> None:
    """Test creating a shopping list with very long title."""
    client_id = f"shopping-list-user-{uuid4()}"
    created_list_id: UUID | None = None
    long_title = "x" * 1000

    try:
        response = client.post(
            f"/api/shopping_lists/{client_id}",
            json={"title": long_title},
        )

        assert response.status_code == 200
        body = response.json()
        created_list_id = UUID(body["id"])
        assert body["title"] == long_title
    finally:
        if created_list_id:
            cleanup_shopping_list(created_list_id)


def test_get_shopping_list_with_no_items(client: TestClient) -> None:
    """Test getting a shopping list that has no items."""
    client_id = f"shopping-list-user-{uuid4()}"
    shopping_list_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Empty List")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

        response = client.get(f"/api/shopping_list/{shopping_list_id}")

        assert response.status_code == 200
        payload = response.json()
        assert UUID(payload["id"]) == shopping_list_id
        assert payload["list_items"] == []
    finally:
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_update_shopping_list_removes_all_items(client: TestClient) -> None:
    """Test that updating a shopping list to remove all items works correctly."""
    client_id = f"shopping-list-user-{uuid4()}"
    shopping_list_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="With Items")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

            item = ListItem(
                list_id=shopping_list.id,
                raw_text_qty="1",
                raw_text_item="test",
                item_name="Test",
                qty_value=1.0,
                qty_unit="count",
                norm_qty_value=1.0,
                norm_qty_unit="count",
                position=1,
            )
            session.add(item)

        original = client.get(f"/api/shopping_list/{shopping_list_id}").json()
        original["list_items"] = []

        response = client.put(f"/api/shopping_list/{shopping_list_id}", json=original)

        assert response.status_code == 200
        assert response.json()["list_items"] == []

        with session_scope() as session:
            items = session.exec(
                select(ListItem).where(ListItem.list_id == shopping_list_id)
            ).all()
            assert len(items) == 0
    finally:
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_update_shopping_list_with_only_new_items(client: TestClient) -> None:
    """Test updating a shopping list by removing all old items and adding new ones."""
    client_id = f"shopping-list-user-{uuid4()}"
    shopping_list_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Original Items")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

            old_item = ListItem(
                list_id=shopping_list.id,
                raw_text_qty="1",
                raw_text_item="old",
                item_name="Old",
                qty_value=1.0,
                qty_unit="count",
                norm_qty_value=1.0,
                norm_qty_unit="count",
                position=1,
            )
            session.add(old_item)

        original = client.get(f"/api/shopping_list/{shopping_list_id}").json()
        old_item_id = UUID(original["list_items"][0]["id"])

        new_items = [
            {
                "list_id": str(shopping_list_id),
                "raw_text_qty": "5",
                "raw_text_item": "new item 1",
                "item_name": "New Item 1",
                "qty_value": 5.0,
                "qty_unit": "count",
                "norm_qty_value": 5.0,
                "norm_qty_unit": "count",
                "position": 1,
            },
            {
                "list_id": str(shopping_list_id),
                "raw_text_qty": "3",
                "raw_text_item": "new item 2",
                "item_name": "New Item 2",
                "qty_value": 3.0,
                "qty_unit": "count",
                "norm_qty_value": 3.0,
                "norm_qty_unit": "count",
                "position": 2,
            },
        ]
        original["list_items"] = new_items

        response = client.put(f"/api/shopping_list/{shopping_list_id}", json=original)

        assert response.status_code == 200
        updated = response.json()
        assert len(updated["list_items"]) == 2
        item_names = {item["item_name"] for item in updated["list_items"]}
        assert item_names == {"New Item 1", "New Item 2"}

        with session_scope() as session:
            items = session.exec(
                select(ListItem).where(ListItem.list_id == shopping_list_id)
            ).all()
            assert len(items) == 2
            assert old_item_id not in {item.id for item in items}
    finally:
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_update_shopping_list_with_many_items(client: TestClient) -> None:
    """Test updating a shopping list with a large number of items."""
    client_id = f"shopping-list-user-{uuid4()}"
    shopping_list_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Many Items")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

        original = client.get(f"/api/shopping_list/{shopping_list_id}").json()

        new_items = [
            {
                "list_id": str(shopping_list_id),
                "raw_text_qty": str(i),
                "raw_text_item": f"item {i}",
                "item_name": f"Item {i}",
                "qty_value": float(i),
                "qty_unit": "count",
                "norm_qty_value": float(i),
                "norm_qty_unit": "count",
                "position": i,
            }
            for i in range(1, 51)
        ]
        original["list_items"] = new_items

        response = client.put(f"/api/shopping_list/{shopping_list_id}", json=original)

        assert response.status_code == 200
        updated = response.json()
        assert len(updated["list_items"]) == 50
        positions = [item["position"] for item in updated["list_items"]]
        assert positions == list(range(1, 51))
    finally:
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_update_shopping_list_change_title_only(client: TestClient) -> None:
    """Test updating only the title without changing items."""
    client_id = f"shopping-list-user-{uuid4()}"
    shopping_list_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Original Title")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

            item = ListItem(
                list_id=shopping_list.id,
                raw_text_qty="2",
                raw_text_item="apples",
                item_name="Apples",
                qty_value=2.0,
                qty_unit="count",
                norm_qty_value=2.0,
                norm_qty_unit="count",
                position=1,
            )
            session.add(item)

        original = client.get(f"/api/shopping_list/{shopping_list_id}").json()
        item_id = UUID(original["list_items"][0]["id"])
        original["title"] = "New Title"

        response = client.put(f"/api/shopping_list/{shopping_list_id}", json=original)

        assert response.status_code == 200
        updated = response.json()
        assert updated["title"] == "New Title"
        assert len(updated["list_items"]) == 1
        assert UUID(updated["list_items"][0]["id"]) == item_id

        with session_scope() as session:
            stored_list = session.exec(
                select(ShoppingList).where(ShoppingList.id == shopping_list_id)
            ).first()
            assert stored_list is not None
            assert stored_list.title == "New Title"
    finally:
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_delete_shopping_list_with_many_items(client: TestClient) -> None:
    """Test deleting a shopping list with many items cascades properly."""
    client_id = f"shopping-list-user-{uuid4()}"
    shopping_list_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Many Items Delete")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

            for i in range(1, 21):
                item = ListItem(
                    list_id=shopping_list.id,
                    raw_text_qty=str(i),
                    raw_text_item=f"item {i}",
                    item_name=f"Item {i}",
                    qty_value=float(i),
                    qty_unit="count",
                    norm_qty_value=float(i),
                    norm_qty_unit="count",
                    position=i,
                )
                session.add(item)

        response = client.delete(f"/api/shopping_list/{shopping_list_id}")

        assert response.status_code == 204

        with session_scope() as session:
            list_exists = session.exec(
                select(ShoppingList).where(ShoppingList.id == shopping_list_id)
            ).first()
            assert list_exists is None

            remaining_items = session.exec(
                select(ListItem).where(ListItem.list_id == shopping_list_id)
            ).all()
            assert len(remaining_items) == 0
    finally:
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_delete_shopping_list_with_no_items(client: TestClient) -> None:
    """Test deleting a shopping list that has no items."""
    client_id = f"shopping-list-user-{uuid4()}"
    shopping_list_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Empty Delete")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

        response = client.delete(f"/api/shopping_list/{shopping_list_id}")

        assert response.status_code == 204

        with session_scope() as session:
            list_exists = session.exec(
                select(ShoppingList).where(ShoppingList.id == shopping_list_id)
            ).first()
            assert list_exists is None
    finally:
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


# Data Validation Tests -------------------------------------------------------


def test_update_shopping_list_with_null_item_fields(client: TestClient) -> None:
    """Test updating with items that have null optional fields."""
    client_id = f"shopping-list-user-{uuid4()}"
    shopping_list_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Null Fields Test")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

        original = client.get(f"/api/shopping_list/{shopping_list_id}").json()

        new_item = {
            "list_id": str(shopping_list_id),
            "raw_text_qty": None,
            "raw_text_item": None,
            "item_name": None,
            "qty_value": None,
            "qty_unit": None,
            "norm_qty_value": None,
            "norm_qty_unit": None,
            "position": 1,
        }
        original["list_items"] = [new_item]

        response = client.put(f"/api/shopping_list/{shopping_list_id}", json=original)

        assert response.status_code == 200
        updated = response.json()
        assert len(updated["list_items"]) == 1
        item = updated["list_items"][0]
        assert item["position"] == 1
    finally:
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_update_shopping_list_with_negative_position(client: TestClient) -> None:
    """Test updating with items that have negative positions."""
    client_id = f"shopping-list-user-{uuid4()}"
    shopping_list_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(
                client_id=client_id, title="Negative Position Test"
            )
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

        original = client.get(f"/api/shopping_list/{shopping_list_id}").json()

        new_item = {
            "list_id": str(shopping_list_id),
            "raw_text_qty": "1",
            "raw_text_item": "test",
            "item_name": "Test",
            "qty_value": 1.0,
            "qty_unit": "count",
            "norm_qty_value": 1.0,
            "norm_qty_unit": "count",
            "position": -5,
        }
        original["list_items"] = [new_item]

        response = client.put(f"/api/shopping_list/{shopping_list_id}", json=original)

        assert response.status_code == 200
        updated = response.json()
        assert updated["list_items"][0]["position"] == -5
    finally:
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_update_shopping_list_with_duplicate_positions(client: TestClient) -> None:
    """Test updating with items that have duplicate positions."""
    client_id = f"shopping-list-user-{uuid4()}"
    shopping_list_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(
                client_id=client_id, title="Duplicate Position Test"
            )
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

        original = client.get(f"/api/shopping_list/{shopping_list_id}").json()

        new_items = [
            {
                "list_id": str(shopping_list_id),
                "raw_text_qty": "1",
                "raw_text_item": "item 1",
                "item_name": "Item 1",
                "qty_value": 1.0,
                "qty_unit": "count",
                "norm_qty_value": 1.0,
                "norm_qty_unit": "count",
                "position": 1,
            },
            {
                "list_id": str(shopping_list_id),
                "raw_text_qty": "2",
                "raw_text_item": "item 2",
                "item_name": "Item 2",
                "qty_value": 2.0,
                "qty_unit": "count",
                "norm_qty_value": 2.0,
                "norm_qty_unit": "count",
                "position": 1,
            },
        ]
        original["list_items"] = new_items

        response = client.put(f"/api/shopping_list/{shopping_list_id}", json=original)

        assert response.status_code == 200
        updated = response.json()
        assert len(updated["list_items"]) == 2
    finally:
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_update_shopping_list_with_zero_position(client: TestClient) -> None:
    """Test updating with items at position zero."""
    client_id = f"shopping-list-user-{uuid4()}"
    shopping_list_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(
                client_id=client_id, title="Zero Position Test"
            )
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

        original = client.get(f"/api/shopping_list/{shopping_list_id}").json()

        new_item = {
            "list_id": str(shopping_list_id),
            "raw_text_qty": "1",
            "raw_text_item": "test",
            "item_name": "Test",
            "qty_value": 1.0,
            "qty_unit": "count",
            "norm_qty_value": 1.0,
            "norm_qty_unit": "count",
            "position": 0,
        }
        original["list_items"] = [new_item]

        response = client.put(f"/api/shopping_list/{shopping_list_id}", json=original)

        assert response.status_code == 200
        updated = response.json()
        assert updated["list_items"][0]["position"] == 0
    finally:
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_update_shopping_list_with_large_quantity_values(client: TestClient) -> None:
    """Test updating with items that have very large quantity values."""
    client_id = f"shopping-list-user-{uuid4()}"
    shopping_list_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(
                client_id=client_id, title="Large Quantity Test"
            )
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

        original = client.get(f"/api/shopping_list/{shopping_list_id}").json()

        new_item = {
            "list_id": str(shopping_list_id),
            "raw_text_qty": "999999999",
            "raw_text_item": "test",
            "item_name": "Test",
            "qty_value": 999999999.99,
            "qty_unit": "tons",
            "norm_qty_value": 999999999.99,
            "norm_qty_unit": "kg",
            "position": 1,
        }
        original["list_items"] = [new_item]

        response = client.put(f"/api/shopping_list/{shopping_list_id}", json=original)

        assert response.status_code == 200
        updated = response.json()
        assert updated["list_items"][0]["qty_value"] == 999999999.99
    finally:
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_update_shopping_list_with_special_characters_in_text(
    client: TestClient,
) -> None:
    """Test updating with items that have special characters in text fields."""
    client_id = f"shopping-list-user-{uuid4()}"
    shopping_list_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(
                client_id=client_id, title="Special Characters Test"
            )
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

        original = client.get(f"/api/shopping_list/{shopping_list_id}").json()

        new_item = {
            "list_id": str(shopping_list_id),
            "raw_text_qty": "2½",
            "raw_text_item": "crème brûlée & café",
            "item_name": "Crème Brûlée & Café",
            "qty_value": 2.5,
            "qty_unit": "cups",
            "norm_qty_value": 2.5,
            "norm_qty_unit": "cups",
            "position": 1,
        }
        original["list_items"] = [new_item]

        response = client.put(f"/api/shopping_list/{shopping_list_id}", json=original)

        assert response.status_code == 200
        updated = response.json()
        assert "crème brûlée & café" in updated["list_items"][0]["raw_text_item"]
    finally:
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_update_shopping_list_with_unicode_emoji_in_text(client: TestClient) -> None:
    """Test updating with items that have unicode emoji in text fields."""
    client_id = f"shopping-list-user-{uuid4()}"
    shopping_list_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Emoji Test 🛒")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

        original = client.get(f"/api/shopping_list/{shopping_list_id}").json()

        new_item = {
            "list_id": str(shopping_list_id),
            "raw_text_qty": "5",
            "raw_text_item": "apples 🍎",
            "item_name": "Apples 🍎",
            "qty_value": 5.0,
            "qty_unit": "count",
            "norm_qty_value": 5.0,
            "norm_qty_unit": "count",
            "position": 1,
        }
        original["list_items"] = [new_item]

        response = client.put(f"/api/shopping_list/{shopping_list_id}", json=original)

        assert response.status_code == 200
        updated = response.json()
        assert "🍎" in updated["list_items"][0]["item_name"]
        assert "🛒" in updated["title"]
    finally:
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


# Isolation and Concurrency Tests ---------------------------------------------


def test_multiple_users_can_have_same_list_title(client: TestClient) -> None:
    """Test that different users can create lists with the same title."""
    client_id_1 = f"shopping-list-user-{uuid4()}"
    client_id_2 = f"shopping-list-user-{uuid4()}"
    list_id_1: UUID | None = None
    list_id_2: UUID | None = None

    try:
        response_1 = client.post(
            f"/api/shopping_lists/{client_id_1}",
            json={"title": "Groceries"},
        )
        assert response_1.status_code == 200
        list_id_1 = UUID(response_1.json()["id"])

        response_2 = client.post(
            f"/api/shopping_lists/{client_id_2}",
            json={"title": "Groceries"},
        )
        assert response_2.status_code == 200
        list_id_2 = UUID(response_2.json()["id"])

        assert list_id_1 != list_id_2

        lists_1 = client.get(f"/api/shopping_lists/{client_id_1}").json()
        lists_2 = client.get(f"/api/shopping_lists/{client_id_2}").json()

        assert len(lists_1) == 1
        assert len(lists_2) == 1
        assert UUID(lists_1[0]["id"]) == list_id_1
        assert UUID(lists_2[0]["id"]) == list_id_2
    finally:
        if list_id_1:
            cleanup_shopping_list(list_id_1)
        if list_id_2:
            cleanup_shopping_list(list_id_2)


def test_user_can_create_multiple_lists(client: TestClient) -> None:
    """Test that a single user can create multiple shopping lists."""
    client_id = f"shopping-list-user-{uuid4()}"
    created_ids: list[UUID] = []

    try:
        for i in range(5):
            response = client.post(
                f"/api/shopping_lists/{client_id}",
                json={"title": f"List {i}"},
            )
            assert response.status_code == 200
            created_ids.append(UUID(response.json()["id"]))

        all_lists = client.get(f"/api/shopping_lists/{client_id}").json()
        assert len(all_lists) == 5

        returned_ids = {UUID(lst["id"]) for lst in all_lists}
        assert returned_ids == set(created_ids)
    finally:
        for list_id in created_ids:
            cleanup_shopping_list(list_id)


def test_deleting_one_list_does_not_affect_other_lists(client: TestClient) -> None:
    """Test that deleting one shopping list doesn't affect other lists."""
    client_id = f"shopping-list-user-{uuid4()}"
    list_id_1: UUID | None = None
    list_id_2: UUID | None = None

    try:
        response_1 = client.post(
            f"/api/shopping_lists/{client_id}",
            json={"title": "List 1"},
        )
        list_id_1 = UUID(response_1.json()["id"])

        response_2 = client.post(
            f"/api/shopping_lists/{client_id}",
            json={"title": "List 2"},
        )
        list_id_2 = UUID(response_2.json()["id"])

        delete_response = client.delete(f"/api/shopping_list/{list_id_1}")
        assert delete_response.status_code == 204

        remaining_lists = client.get(f"/api/shopping_lists/{client_id}").json()
        assert len(remaining_lists) == 1
        assert UUID(remaining_lists[0]["id"]) == list_id_2

        with session_scope() as session:
            list_1_exists = session.exec(
                select(ShoppingList).where(ShoppingList.id == list_id_1)
            ).first()
            assert list_1_exists is None

            list_2_exists = session.exec(
                select(ShoppingList).where(ShoppingList.id == list_id_2)
            ).first()
            assert list_2_exists is not None
    finally:
        if list_id_1:
            cleanup_shopping_list(list_id_1)
        if list_id_2:
            cleanup_shopping_list(list_id_2)


def test_updating_one_list_does_not_affect_other_lists(client: TestClient) -> None:
    """Test that updating one shopping list doesn't affect other lists."""
    client_id = f"shopping-list-user-{uuid4()}"
    list_id_1: UUID | None = None
    list_id_2: UUID | None = None

    try:
        with session_scope() as session:
            list_1 = ShoppingList(client_id=client_id, title="List 1")
            list_2 = ShoppingList(client_id=client_id, title="List 2")
            session.add(list_1)
            session.add(list_2)
            session.flush()
            list_id_1 = list_1.id
            list_id_2 = list_2.id

        data_1 = client.get(f"/api/shopping_list/{list_id_1}").json()
        data_1["title"] = "Updated List 1"
        data_1["list_items"] = [
            {
                "list_id": str(list_id_1),
                "raw_text_qty": "1",
                "raw_text_item": "test",
                "item_name": "Test",
                "qty_value": 1.0,
                "qty_unit": "count",
                "norm_qty_value": 1.0,
                "norm_qty_unit": "count",
                "position": 1,
            }
        ]

        update_response = client.put(f"/api/shopping_list/{list_id_1}", json=data_1)
        assert update_response.status_code == 200

        list_2_data = client.get(f"/api/shopping_list/{list_id_2}").json()
        assert list_2_data["title"] == "List 2"
        assert len(list_2_data["list_items"]) == 0
    finally:
        if list_id_1:
            cleanup_shopping_list(list_id_1)
        if list_id_2:
            cleanup_shopping_list(list_id_2)
