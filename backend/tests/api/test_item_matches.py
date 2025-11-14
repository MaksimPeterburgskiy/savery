"""Integration tests for the item match candidate API endpoints."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.db import session_scope
from backend.app.main import create_app
from backend.app.models import ItemMatchCandidate, ListItem, Product, RoutePlan, ShoppingList


@pytest.fixture()
def client() -> TestClient:
    """Provide a FastAPI test client for the item match routes."""

    with TestClient(create_app()) as test_client:
        yield test_client


def cleanup_item_match_candidate(candidate_id: UUID) -> None:
    """Delete an item match candidate by its identifier."""

    with session_scope() as session:
        candidate = session.get(ItemMatchCandidate, candidate_id)
        if candidate:
            session.delete(candidate)


def cleanup_route_plan(route_plan_id: UUID) -> None:
    """Delete a route plan if it still exists."""

    with session_scope() as session:
        route_plan = session.get(RoutePlan, route_plan_id)
        if route_plan:
            session.delete(route_plan)


def cleanup_list_item(list_item_id: UUID) -> None:
    """Delete the list item used for the candidate."""

    with session_scope() as session:
        list_item = session.get(ListItem, list_item_id)
        if list_item:
            session.delete(list_item)


def cleanup_product(product_id: UUID) -> None:
    """Delete the product that was created for a candidate."""

    with session_scope() as session:
        product = session.get(Product, product_id)
        if product:
            session.delete(product)


def cleanup_shopping_list(shopping_list_id: UUID) -> None:
    """Delete the shopping list that backs the route plan."""

    with session_scope() as session:
        shopping_list = session.get(ShoppingList, shopping_list_id)
        if shopping_list:
            session.delete(shopping_list)


def create_route_plan_with_list_item(client_id: str) -> dict[str, UUID | str]:
    """Provision a shopping list, list item, and route plan for reuse."""

    shopping_list_id: UUID
    route_plan_id: UUID
    list_item_id: UUID
    list_item_name = f"Candidate Item {client_id[-4:]}"
    raw_text_item = "1x test ingredient"

    with session_scope() as session:
        shopping_list = ShoppingList(client_id=client_id, title=f"List for {client_id}")
        session.add(shopping_list)
        session.flush()

        list_item = ListItem(
            list_id=shopping_list.id,
            position=1,
            raw_text_item=raw_text_item,
            item_name=list_item_name,
            qty_value=1,
            qty_unit="ea",
        )
        session.add(list_item)
        session.flush()

        route_plan = RoutePlan(list_id=shopping_list.id, client_id=client_id)
        session.add(route_plan)
        session.flush()

        shopping_list_id = shopping_list.id
        list_item_id = list_item.id
        route_plan_id = route_plan.id

    return {
        "shopping_list_id": shopping_list_id,
        "route_plan_id": route_plan_id,
        "list_item_id": list_item_id,
        "list_item_name": list_item_name,
        "raw_text_item": raw_text_item,
    }


def create_item_match_candidate(
    route_plan_id: UUID,
    list_item_id: UUID,
    score: float,
    brand_suffix: str,
    rejected: bool = False,
) -> dict[str, UUID | float | str | bool]:
    """Create a product and candidate tied to the provided route plan."""

    product_brand = f"Brand {brand_suffix}"
    product_name = f"Candidate {brand_suffix}"
    product_upc = f"{brand_suffix}-upc"
    size_text = f"{brand_suffix} size"

    candidate_id: UUID
    product_id: UUID

    with session_scope() as session:
        product = Product(
            brand=product_brand,
            name=product_name,
            upc=product_upc,
            size_text=size_text,
            pkg_qty_value=1.0,
            pkg_qty_unit="ea",
            base_qty_value=1.0,
            base_qty_unit="ea",
            image_url=f"https://example.com/{brand_suffix}.jpg",
        )
        session.add(product)
        session.flush()

        candidate = ItemMatchCandidate(
            plan_id=route_plan_id,
            list_item_id=list_item_id,
            product_id=product.id,
            score=score,
            rejected_by_user=rejected,
        )
        session.add(candidate)
        session.flush()

        product_id = product.id
        candidate_id = candidate.id

    return {
        "candidate_id": candidate_id,
        "product_id": product_id,
        "product_brand": product_brand,
        "product_name": product_name,
        "score": score,
        "rejected_by_user": rejected,
    }


def test_get_item_match_candidates_for_route_plan_returns_sorted_candidates(client: TestClient) -> None:
    """Ensure candidates for a route plan are returned sorted by score."""

    client_id = f"test-client-{uuid4()}"
    shopping_list_id: UUID | None = None
    route_plan_id: UUID | None = None
    list_item_id: UUID | None = None
    candidate_meta: list[dict[str, UUID | str | float | bool]] = []
    product_ids: list[UUID] = []

    try:
        base_data = create_route_plan_with_list_item(client_id)
        shopping_list_id = base_data["shopping_list_id"]
        route_plan_id = base_data["route_plan_id"]
        list_item_id = base_data["list_item_id"]

        lower_score_candidate = create_item_match_candidate(
            route_plan_id,
            list_item_id,
            score=1.1,
            brand_suffix="alpha",
        )
        higher_score_candidate = create_item_match_candidate(
            route_plan_id,
            list_item_id,
            score=2.7,
            brand_suffix="beta",
        )
        candidate_meta.extend([lower_score_candidate, higher_score_candidate])
        product_ids.extend([lower_score_candidate["product_id"], higher_score_candidate["product_id"]])

        response = client.get(f"/api/route-plans/{route_plan_id}/item-match-candidates")
        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 2
        assert payload[0]["score"] == higher_score_candidate["score"]
        assert payload[1]["score"] == lower_score_candidate["score"]
        assert payload[0]["product"]["brand"] == higher_score_candidate["product_brand"]
        assert payload[0]["list_item"]["item_name"] == base_data["list_item_name"]
        assert payload[0]["list_item"]["id"] == str(list_item_id)
    finally:
        for cand in candidate_meta:
            cleanup_item_match_candidate(cand["candidate_id"])
        for pid in product_ids:
            cleanup_product(pid)
        if route_plan_id:
            cleanup_route_plan(route_plan_id)
        if list_item_id:
            cleanup_list_item(list_item_id)
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_get_item_match_candidates_for_nonexistent_route_plan_returns_404(client: TestClient) -> None:
    """Ensure requesting candidates for a missing route plan raises 404."""

    response = client.get(f"/api/route-plans/{uuid4()}/item-match-candidates")
    assert response.status_code == 404
    assert response.json()["detail"] == "Route Plan not found"


def test_get_item_match_candidate_by_id_returns_candidate(client: TestClient) -> None:
    """Validate fetching a specific candidate returns populated nested objects."""

    client_id = f"test-client-{uuid4()}"
    shopping_list_id: UUID | None = None
    route_plan_id: UUID | None = None
    list_item_id: UUID | None = None
    product_ids: list[UUID] = []
    candidate_id: UUID | None = None

    try:
        base_data = create_route_plan_with_list_item(client_id)
        shopping_list_id = base_data["shopping_list_id"]
        route_plan_id = base_data["route_plan_id"]
        list_item_id = base_data["list_item_id"]

        candidate = create_item_match_candidate(
            route_plan_id,
            list_item_id,
            score=4.5,
            brand_suffix="single",
        )
        candidate_id = candidate["candidate_id"]
        product_ids.append(candidate["product_id"])

        response = client.get(f"/api/item-match-candidates/{candidate_id}")
        assert response.status_code == 200
        payload = response.json()
        assert payload["id"] == str(candidate_id)
        assert payload["plan_id"] == str(route_plan_id)
        assert payload["score"] == candidate["score"]
        assert payload["rejected_by_user"] is False
        assert payload["product"]["brand"] == candidate["product_brand"]
        assert payload["product"]["name"] == candidate["product_name"]
        assert payload["list_item"]["item_name"] == base_data["list_item_name"]
        assert payload["product"]["upc"] == f"{candidate['product_brand'].split()[-1]}-upc"
    finally:
        if candidate_id:
            cleanup_item_match_candidate(candidate_id)
        for pid in product_ids:
            cleanup_product(pid)
        if route_plan_id:
            cleanup_route_plan(route_plan_id)
        if list_item_id:
            cleanup_list_item(list_item_id)
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_update_item_match_candidate_rejected_by_user(client: TestClient) -> None:
    """Ensure the candidate can be updated to mark user rejection."""

    client_id = f"test-client-{uuid4()}"
    shopping_list_id: UUID | None = None
    route_plan_id: UUID | None = None
    list_item_id: UUID | None = None
    product_ids: list[UUID] = []
    candidate_id: UUID | None = None

    try:
        base_data = create_route_plan_with_list_item(client_id)
        shopping_list_id = base_data["shopping_list_id"]
        route_plan_id = base_data["route_plan_id"]
        list_item_id = base_data["list_item_id"]

        candidate = create_item_match_candidate(
            route_plan_id,
            list_item_id,
            score=3.3,
            brand_suffix="patch",
        )
        candidate_id = candidate["candidate_id"]
        product_ids.append(candidate["product_id"])

        response = client.patch(
            f"/api/item-match-candidates/{candidate_id}",
            json={"rejected_by_user": True},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["rejected_by_user"] is True

        with session_scope() as session:
            stored_candidate = session.get(ItemMatchCandidate, candidate_id)
            assert stored_candidate is not None
            assert stored_candidate.rejected_by_user is True
    finally:
        if candidate_id:
            cleanup_item_match_candidate(candidate_id)
        for pid in product_ids:
            cleanup_product(pid)
        if route_plan_id:
            cleanup_route_plan(route_plan_id)
        if list_item_id:
            cleanup_list_item(list_item_id)
        if shopping_list_id:
            cleanup_shopping_list(shopping_list_id)


def test_update_item_match_candidate_not_found_returns_404(client: TestClient) -> None:
    """Ensure updating a missing candidate returns 404."""

    response = client.patch(
        f"/api/item-match-candidates/{uuid4()}",
        json={"rejected_by_user": True},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Item match candidate not found"
