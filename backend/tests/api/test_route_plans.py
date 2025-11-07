"""Integration tests for the route plan API endpoints."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from backend.app.db import session_scope
from backend.app.main import create_app
from backend.app.models import OptimizationMode, PlanSelectedStore, RoutePlan, ShoppingList, Store


@pytest.fixture()
def client() -> TestClient:
    """Provide a FastAPI test client for the route plan routes."""
    with TestClient(create_app()) as test_client:
        yield test_client


def cleanup_route_plan(route_plan_id: UUID) -> None:
    """Remove a route plan and associated records from the database."""
    with session_scope() as session:
        route_plan = session.exec(select(RoutePlan).where(RoutePlan.id == route_plan_id)).first()
        if route_plan:
            session.delete(route_plan)


def cleanup_shopping_list(shopping_list_id: UUID) -> None:
    """Remove a shopping list from the database."""
    with session_scope() as session:
        shopping_list = session.exec(select(ShoppingList).where(ShoppingList.id == shopping_list_id)).first()
        if shopping_list:
            session.delete(shopping_list)


def cleanup_store(store_id: UUID) -> None:
    """Remove a store from the database."""
    with session_scope() as session:
        store = session.exec(select(Store).where(Store.id == store_id)).first()
        if store:
            session.delete(store)


# Route Plan Creation Tests ---------------------------------------------------


def test_create_route_plan_for_list_with_minimal_data(client: TestClient) -> None:
    """Test creating a route plan with minimal required data."""
    client_id = f"test-client-{uuid4()}"
    shopping_list_id: UUID | None = None
    route_plan_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Test List")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

        response = client.post(
            f"/api/shopping-lists/{shopping_list_id}/route-plans",
            json={},
        )

        assert response.status_code == 201
        body = response.json()
        route_plan_id = UUID(body["id"])
        assert body["list_id"] == str(shopping_list_id)
        assert body["status"] == "draft"
        assert body["opt_mode"] == "BALANCED"
        assert body["lowest_unit_price"] is False
        assert body["max_stores"] == 3
        assert body["selected_stores"] == []
    finally:
        if route_plan_id:
            cleanup_route_plan(route_plan_id)
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_create_route_plan_with_custom_parameters(client: TestClient) -> None:
    """Test creating a route plan with custom parameters."""
    client_id = f"test-client-{uuid4()}"
    shopping_list_id: UUID | None = None
    route_plan_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Test List")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

        response = client.post(
            f"/api/shopping-lists/{shopping_list_id}/route-plans",
            json={
                "status": "matched",
                "opt_mode": "PRICE",
                "lowest_unit_price": True,
                "max_stores": 5,
                "user_longitude": -122.4194,
                "user_latitude": 37.7749,
            },
        )

        assert response.status_code == 201
        body = response.json()
        route_plan_id = UUID(body["id"])
        assert body["status"] == "matched"
        assert body["opt_mode"] == "PRICE"
        assert body["lowest_unit_price"] is True
        assert body["max_stores"] == 5
        assert body["user_longitude"] == -122.4194
        assert body["user_latitude"] == 37.7749
    finally:
        if route_plan_id:
            cleanup_route_plan(route_plan_id)
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_create_route_plan_with_selected_stores(client: TestClient) -> None:
    """Test creating a route plan with selected stores."""
    client_id = f"test-client-{uuid4()}"
    shopping_list_id: UUID | None = None
    route_plan_id: UUID | None = None
    store_ids: list[UUID] = []

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Test List")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

            # Create test stores
            for i in range(2):
                store = Store(
                    name=f"Test Store {i}",
                    number=f"#{i}",
                    address_line1=f"{i} Main St",
                    city="Test City",
                    region="CA",
                    postal_code="12345",
                    country_code="US",
                    timezone="America/Los_Angeles",
                    phone="555-0100",
                )
                session.add(store)
                session.flush()
                store_ids.append(store.id)

        response = client.post(
            f"/api/shopping-lists/{shopping_list_id}/route-plans",
            json={
                "selected_store_ids": [str(sid) for sid in store_ids],
            },
        )

        assert response.status_code == 201
        body = response.json()
        route_plan_id = UUID(body["id"])
        assert len(body["selected_stores"]) == 2
        returned_store_ids = {UUID(store["id"]) for store in body["selected_stores"]}
        assert returned_store_ids == set(store_ids)
    finally:
        if route_plan_id:
            cleanup_route_plan(route_plan_id)
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)
        for store_id in store_ids:
            cleanup_store(store_id)


def test_create_route_plan_with_nonexistent_store_returns_404(client: TestClient) -> None:
    """Test creating route plan with non-existent store ID returns 404."""
    client_id = f"test-client-{uuid4()}"
    shopping_list_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Test List")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

        nonexistent_store_id = uuid4()
        response = client.post(
            f"/api/shopping-lists/{shopping_list_id}/route-plans",
            json={
                "selected_store_ids": [str(nonexistent_store_id)],
            },
        )

        assert response.status_code == 404
        detail = response.json()["detail"]
        assert detail["message"] == "Store(s) not found"
        assert str(nonexistent_store_id) in detail.get("missing_store_ids", [])
    finally:
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_create_route_plan_for_nonexistent_list_returns_404(client: TestClient) -> None:
    """Test creating route plan for non-existent shopping list returns 404."""
    nonexistent_list_id = uuid4()
    response = client.post(
        f"/api/shopping-lists/{nonexistent_list_id}/route-plans",
        json={},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Shopping list not found"


def test_create_route_plan_without_client_id_when_list_has_none_returns_400(
    client: TestClient,
) -> None:
    """Test creating route plan without client_id when shopping list has none returns 400."""
    shopping_list_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=None, title="Test List")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

        response = client.post(
            f"/api/shopping-lists/{shopping_list_id}/route-plans",
            json={},
        )

        assert response.status_code == 400
        assert "client_id is required" in response.json()["detail"]
    finally:
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_create_route_plan_validation_requires_both_lon_lat(client: TestClient) -> None:
    """Test that creating route plan requires both longitude and latitude together."""
    client_id = f"test-client-{uuid4()}"
    shopping_list_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Test List")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

        # Try with only longitude
        response = client.post(
            f"/api/shopping-lists/{shopping_list_id}/route-plans",
            json={"user_longitude": -122.4194},
        )
        assert response.status_code == 422

        # Try with only latitude
        response = client.post(
            f"/api/shopping-lists/{shopping_list_id}/route-plans",
            json={"user_latitude": 37.7749},
        )
        assert response.status_code == 422
    finally:
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


# Route Plan Retrieval Tests --------------------------------------------------


def test_get_route_plans_for_shopping_list(client: TestClient) -> None:
    """Test getting all route plans for a shopping list."""
    client_id = f"test-client-{uuid4()}"
    shopping_list_id: UUID | None = None
    route_plan_ids: list[UUID] = []

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Test List")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

            for i in range(3):
                route_plan = RoutePlan(
                    list_id=shopping_list_id,
                    client_id=client_id,
                    status="draft",
                    opt_mode=OptimizationMode.BALANCED,
                )
                session.add(route_plan)
                session.flush()
                route_plan_ids.append(route_plan.id)

        response = client.get(f"/api/shopping-lists/{shopping_list_id}/route-plans")
        assert response.status_code == 200
        plans = response.json()
        assert len(plans) == 3
        returned_ids = {UUID(plan["id"]) for plan in plans}
        assert returned_ids == set(route_plan_ids)
    finally:
        for route_plan_id in route_plan_ids:
            cleanup_route_plan(route_plan_id)
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_get_route_plan_by_id(client: TestClient) -> None:
    """Test getting a single route plan by ID."""
    client_id = f"test-client-{uuid4()}"
    shopping_list_id: UUID | None = None
    route_plan_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Test List")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

            route_plan = RoutePlan(
                list_id=shopping_list_id,
                client_id=client_id,
                status="draft",
                opt_mode=OptimizationMode.PRICE,
            )
            session.add(route_plan)
            session.flush()
            route_plan_id = route_plan.id

        response = client.get(f"/api/route-plans/{route_plan_id}")
        assert response.status_code == 200
        body = response.json()
        assert UUID(body["id"]) == route_plan_id
        assert body["opt_mode"] == "PRICE"
    finally:
        if route_plan_id:
            cleanup_route_plan(route_plan_id)
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_get_nonexistent_route_plan_returns_404(client: TestClient) -> None:
    """Test getting a non-existent route plan returns 404."""
    nonexistent_id = uuid4()
    response = client.get(f"/api/route-plans/{nonexistent_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Route plan not found"


# Route Plan Update Tests -----------------------------------------------------


def test_update_route_plan_status(client: TestClient) -> None:
    """Test updating a route plan's status."""
    client_id = f"test-client-{uuid4()}"
    shopping_list_id: UUID | None = None
    route_plan_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Test List")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

            route_plan = RoutePlan(
                list_id=shopping_list_id,
                client_id=client_id,
                status="draft",
                opt_mode=OptimizationMode.BALANCED,
            )
            session.add(route_plan)
            session.flush()
            route_plan_id = route_plan.id

        response = client.patch(
            f"/api/route-plans/{route_plan_id}",
            json={"status": "optimized"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "optimized"

        with session_scope() as session:
            stored = session.get(RoutePlan, route_plan_id)
            assert stored is not None
            assert stored.status == "optimized"
    finally:
        if route_plan_id:
            cleanup_route_plan(route_plan_id)
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_update_route_plan_optimization_settings(client: TestClient) -> None:
    """Test updating route plan optimization settings."""
    client_id = f"test-client-{uuid4()}"
    shopping_list_id: UUID | None = None
    route_plan_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Test List")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

            route_plan = RoutePlan(
                list_id=shopping_list_id,
                client_id=client_id,
                status="draft",
                opt_mode=OptimizationMode.BALANCED,
                lowest_unit_price=False,
                max_stores=3,
            )
            session.add(route_plan)
            session.flush()
            route_plan_id = route_plan.id

        response = client.patch(
            f"/api/route-plans/{route_plan_id}",
            json={
                "opt_mode": "SPEED",
                "lowest_unit_price": True,
                "max_stores": 2,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["opt_mode"] == "SPEED"
        assert body["lowest_unit_price"] is True
        assert body["max_stores"] == 2
    finally:
        if route_plan_id:
            cleanup_route_plan(route_plan_id)
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_update_route_plan_user_location(client: TestClient) -> None:
    """Test updating route plan user location."""
    client_id = f"test-client-{uuid4()}"
    shopping_list_id: UUID | None = None
    route_plan_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Test List")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

            route_plan = RoutePlan(
                list_id=shopping_list_id,
                client_id=client_id,
                status="draft",
                opt_mode=OptimizationMode.BALANCED,
            )
            session.add(route_plan)
            session.flush()
            route_plan_id = route_plan.id

        response = client.patch(
            f"/api/route-plans/{route_plan_id}",
            json={
                "user_longitude": -122.4194,
                "user_latitude": 37.7749,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["user_longitude"] == -122.4194
        assert body["user_latitude"] == 37.7749
    finally:
        if route_plan_id:
            cleanup_route_plan(route_plan_id)
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_update_route_plan_clear_user_location(client: TestClient) -> None:
    """Test clearing route plan user location."""
    client_id = f"test-client-{uuid4()}"
    shopping_list_id: UUID | None = None
    route_plan_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Test List")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

            route_plan = RoutePlan(
                list_id=shopping_list_id,
                client_id=client_id,
                status="draft",
                opt_mode=OptimizationMode.BALANCED,
            )
            session.add(route_plan)
            session.flush()
            route_plan_id = route_plan.id

        response = client.patch(
            f"/api/route-plans/{route_plan_id}",
            json={
                "user_longitude": None,
                "user_latitude": None,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["user_longitude"] is None
        assert body["user_latitude"] is None
    finally:
        if route_plan_id:
            cleanup_route_plan(route_plan_id)
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_update_route_plan_totals(client: TestClient) -> None:
    """Test updating route plan totals after optimization."""
    client_id = f"test-client-{uuid4()}"
    shopping_list_id: UUID | None = None
    route_plan_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Test List")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

            route_plan = RoutePlan(
                list_id=shopping_list_id,
                client_id=client_id,
                status="draft",
                opt_mode=OptimizationMode.BALANCED,
            )
            session.add(route_plan)
            session.flush()
            route_plan_id = route_plan.id

        response = client.patch(
            f"/api/route-plans/{route_plan_id}",
            json={
                "total_price": 125.50,
                "total_distance_m": 5000,
                "total_travel_sec": 600,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["total_price"] == 125.50
        assert body["total_distance_m"] == 5000
        assert body["total_travel_sec"] == 600
    finally:
        if route_plan_id:
            cleanup_route_plan(route_plan_id)
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_update_nonexistent_route_plan_returns_404(client: TestClient) -> None:
    """Test updating a non-existent route plan returns 404."""
    nonexistent_id = uuid4()
    response = client.patch(
        f"/api/route-plans/{nonexistent_id}",
        json={"status": "optimized"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Route plan not found"


# Route Plan Deletion Tests ---------------------------------------------------


def test_delete_route_plan(client: TestClient) -> None:
    """Test deleting a route plan."""
    client_id = f"test-client-{uuid4()}"
    shopping_list_id: UUID | None = None
    route_plan_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Test List")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

            route_plan = RoutePlan(
                list_id=shopping_list_id,
                client_id=client_id,
                status="draft",
                opt_mode=OptimizationMode.BALANCED,
            )
            session.add(route_plan)
            session.flush()
            route_plan_id = route_plan.id

        response = client.delete(f"/api/route-plans/{route_plan_id}")
        assert response.status_code == 204

        with session_scope() as session:
            stored = session.get(RoutePlan, route_plan_id)
            assert stored is None
    finally:
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_delete_nonexistent_route_plan_returns_404(client: TestClient) -> None:
    """Test deleting a non-existent route plan returns 404."""
    nonexistent_id = uuid4()
    response = client.delete(f"/api/route-plans/{nonexistent_id}")
    assert response.status_code == 404


# Selected Stores Tests -------------------------------------------------------


def test_add_selected_store_to_route_plan(client: TestClient) -> None:
    """Test adding a selected store to a route plan."""
    client_id = f"test-client-{uuid4()}"
    shopping_list_id: UUID | None = None
    route_plan_id: UUID | None = None
    store_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Test List")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

            route_plan = RoutePlan(
                list_id=shopping_list_id,
                client_id=client_id,
                status="draft",
                opt_mode=OptimizationMode.BALANCED,
            )
            session.add(route_plan)
            session.flush()
            route_plan_id = route_plan.id

            store = Store(
                name="Test Store",
                number="#1",
                address_line1="123 Main St",
                city="Test City",
                region="CA",
                postal_code="12345",
                country_code="US",
                timezone="America/Los_Angeles",
                phone="555-0100",
            )
            session.add(store)
            session.flush()
            store_id = store.id

        response = client.post(
            f"/api/route-plans/{route_plan_id}/selected-stores",
            json={"store_id": str(store_id)},
        )

        assert response.status_code == 200
        body = response.json()
        assert len(body["selected_stores"]) == 1
        assert UUID(body["selected_stores"][0]["id"]) == store_id
    finally:
        if route_plan_id:
            cleanup_route_plan(route_plan_id)
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)
        if store_id:
            cleanup_store(store_id)


def test_add_duplicate_selected_store_returns_409(client: TestClient) -> None:
    """Test adding duplicate selected store returns conflict."""
    client_id = f"test-client-{uuid4()}"
    shopping_list_id: UUID | None = None
    route_plan_id: UUID | None = None
    store_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Test List")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

            route_plan = RoutePlan(
                list_id=shopping_list_id,
                client_id=client_id,
                status="draft",
                opt_mode=OptimizationMode.BALANCED,
            )
            session.add(route_plan)
            session.flush()
            route_plan_id = route_plan.id

            store = Store(
                name="Test Store",
                number="#1",
                address_line1="123 Main St",
                city="Test City",
                region="CA",
                postal_code="12345",
                country_code="US",
                timezone="America/Los_Angeles",
                phone="555-0100",
            )
            session.add(store)
            session.flush()
            store_id = store.id

            # Add store selection
            selection = PlanSelectedStore(plan_id=route_plan_id, store_id=store_id)
            session.add(selection)

        # Try to add the same store again
        response = client.post(
            f"/api/route-plans/{route_plan_id}/selected-stores",
            json={"store_id": str(store_id)},
        )

        assert response.status_code == 409
        assert "already selected" in response.json()["detail"]
    finally:
        if route_plan_id:
            cleanup_route_plan(route_plan_id)
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)
        if store_id:
            cleanup_store(store_id)


def test_add_nonexistent_store_to_route_plan_returns_404(client: TestClient) -> None:
    """Test adding non-existent store to route plan returns 404."""
    client_id = f"test-client-{uuid4()}"
    shopping_list_id: UUID | None = None
    route_plan_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Test List")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

            route_plan = RoutePlan(
                list_id=shopping_list_id,
                client_id=client_id,
                status="draft",
                opt_mode=OptimizationMode.BALANCED,
            )
            session.add(route_plan)
            session.flush()
            route_plan_id = route_plan.id

        nonexistent_store_id = uuid4()
        response = client.post(
            f"/api/route-plans/{route_plan_id}/selected-stores",
            json={"store_id": str(nonexistent_store_id)},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Store not found"
    finally:
        if route_plan_id:
            cleanup_route_plan(route_plan_id)
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_remove_selected_store_from_route_plan(client: TestClient) -> None:
    """Test removing a selected store from a route plan."""
    client_id = f"test-client-{uuid4()}"
    shopping_list_id: UUID | None = None
    route_plan_id: UUID | None = None
    store_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Test List")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

            route_plan = RoutePlan(
                list_id=shopping_list_id,
                client_id=client_id,
                status="draft",
                opt_mode=OptimizationMode.BALANCED,
            )
            session.add(route_plan)
            session.flush()
            route_plan_id = route_plan.id

            store = Store(
                name="Test Store",
                number="#1",
                address_line1="123 Main St",
                city="Test City",
                region="CA",
                postal_code="12345",
                country_code="US",
                timezone="America/Los_Angeles",
                phone="555-0100",
            )
            session.add(store)
            session.flush()
            store_id = store.id

            selection = PlanSelectedStore(plan_id=route_plan_id, store_id=store_id)
            session.add(selection)

        response = client.delete(
            f"/api/route-plans/{route_plan_id}/selected-stores/{store_id}"
        )

        assert response.status_code == 200
        body = response.json()
        assert len(body["selected_stores"]) == 0

        with session_scope() as session:
            selection = session.exec(
                select(PlanSelectedStore).where(
                    PlanSelectedStore.plan_id == route_plan_id,
                    PlanSelectedStore.store_id == store_id,
                )
            ).first()
            assert selection is None
    finally:
        if route_plan_id:
            cleanup_route_plan(route_plan_id)
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)
        if store_id:
            cleanup_store(store_id)


def test_remove_nonexistent_selected_store_returns_404(client: TestClient) -> None:
    """Test removing non-existent selected store returns 404."""
    client_id = f"test-client-{uuid4()}"
    shopping_list_id: UUID | None = None
    route_plan_id: UUID | None = None

    try:
        with session_scope() as session:
            shopping_list = ShoppingList(client_id=client_id, title="Test List")
            session.add(shopping_list)
            session.flush()
            shopping_list_id = shopping_list.id

            route_plan = RoutePlan(
                list_id=shopping_list_id,
                client_id=client_id,
                status="draft",
                opt_mode=OptimizationMode.BALANCED,
            )
            session.add(route_plan)
            session.flush()
            route_plan_id = route_plan.id

        nonexistent_store_id = uuid4()
        response = client.delete(
            f"/api/route-plans/{route_plan_id}/selected-stores/{nonexistent_store_id}"
        )

        assert response.status_code == 404
        assert "Selected store not found" in response.json()["detail"]
    finally:
        if route_plan_id:
            cleanup_route_plan(route_plan_id)
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)
