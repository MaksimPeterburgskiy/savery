"""Integration tests that exercise the item match and fanout job endpoints."""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from backend.app.db import session_scope
from backend.app.main import create_app
from backend.app.models import (
    ItemMatch,
    ItemMatchCandidate,
    Job,
    JobStage,
    JobStatus,
    ListItem,
    PlanSelectedStore,
    Product,
    RoutePlan,
    ShoppingList,
    Store,
    StoreChain,
    StoreProduct,
)
from backend.workers.tasks.item_matches import create_item_match_candidates, fanout_candidates_to_item_matches


@pytest.fixture()
def client() -> TestClient:
    """Provide a FastAPI test client for the item match routes."""

    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture()
def sync_enqueue_job(monkeypatch):
    """Run item match jobs synchronously when the API enqueues them."""

    def _fake_enqueue(job_id: UUID | str) -> str:
        job_uuid = UUID(str(job_id))
        with session_scope() as session:
            job = session.get(Job, job_uuid)
            if job is None:
                raise ValueError(f"Job {job_uuid} not found")
            job_stage = job.stage

        if job_stage == JobStage.MATCH:
            create_item_match_candidates.run(job_id=str(job_uuid))
        elif job_stage == JobStage.FANOUT:
            fanout_candidates_to_item_matches.run(job_id=str(job_uuid))
        else:
            raise ValueError(f"Unexpected job stage {job_stage}")

        return "test-task"

    monkeypatch.setattr("backend.app.api.routes.item_matches.enqueue_job", _fake_enqueue)
    return _fake_enqueue


def _cleanup_entities(entity_ids: dict[type, list[UUID]]) -> None:
    """Delete the created rows in an order that respects database constraints."""

    cleanup_order = [
        ItemMatch,
        ItemMatchCandidate,
        PlanSelectedStore,
        StoreProduct,
        Job,
        RoutePlan,
        ListItem,
        ShoppingList,
        Store,
        StoreChain,
        Product,
    ]

    with session_scope() as session:
        for model in cleanup_order:
            for entity_id in entity_ids.get(model, []):
                instance = session.get(model, entity_id)
                if instance is not None:
                    session.delete(instance)


def test_item_match_job_endpoint_creates_candidates(
    client: TestClient,
    sync_enqueue_job: str,
) -> None:
    """The MATCH job endpoint should trigger the task and persist candidates."""

    entity_ids: dict[type, list[UUID]] = defaultdict(list)
    route_plan_id: UUID | None = None
    list_item_id: UUID | None = None
    product_id: UUID | None = None

    try:
        shopping_list_title = f"Match List {uuid4()}"
        with session_scope() as session:
            chain = StoreChain(name=f"Chain {uuid4()}")
            session.add(chain)
            session.flush()
            entity_ids[StoreChain].append(chain.id)

            store = Store(
                chain_id=chain.id,
                name="Match Endpoint Store",
                number="600",
                address_line1="1 API Way",
                city="Testville",
                region="TS",
                postal_code="10001",
                country_code="US",
                timezone="UTC",
                phone="555-6000",
            )
            session.add(store)
            session.flush()
            entity_ids[Store].append(store.id)

            product = Product(
                brand="API Brand",
                name="Organic Milk",
                upc=str(uuid4()),
            )
            session.add(product)
            session.flush()
            entity_ids[Product].append(product.id)
            product_id = product.id

            store_product = StoreProduct(
                store_id=store.id,
                product_id=product.id,
                external_sku=f"SKU-{uuid4()}",
            )
            session.add(store_product)
            session.flush()
            entity_ids[StoreProduct].append(store_product.id)

            shopping_list = ShoppingList(client_id=f"client-{uuid4()}", title=shopping_list_title)
            session.add(shopping_list)
            session.flush()
            entity_ids[ShoppingList].append(shopping_list.id)

            list_item = ListItem(
                list_id=shopping_list.id,
                position=1,
                item_name="organic milk",
                raw_text_item="1 organic milk",
            )
            session.add(list_item)
            session.flush()
            entity_ids[ListItem].append(list_item.id)
            list_item_id = list_item.id

            route_plan = RoutePlan(list_id=shopping_list.id, client_id=f"client-{uuid4()}")
            session.add(route_plan)
            session.flush()
            entity_ids[RoutePlan].append(route_plan.id)
            route_plan_id = route_plan.id

            selection = PlanSelectedStore(plan_id=route_plan.id, store_id=store.id)
            session.add(selection)
            session.flush()
            entity_ids[PlanSelectedStore].append(selection.id)

        assert route_plan_id is not None
        assert list_item_id is not None
        assert product_id is not None

        response = client.post(f"/api/route-plans/{route_plan_id}/item-match-jobs")
        assert response.status_code == 201
        job_payload = response.json()
        job_id = UUID(job_payload["id"])
        entity_ids[Job].append(job_id)

        with session_scope() as session:
            job = session.get(Job, job_id)
            assert job is not None
            assert job.status is JobStatus.SUCCESS
            assert job.progress_total == 1
            assert job.progress_current == 1
            assert job.message == "Item matching task completed"

            candidates = session.exec(select(ItemMatchCandidate).where(ItemMatchCandidate.plan_id == route_plan_id)).all()
            assert len(candidates) == 1
            candidate = candidates[0]
            entity_ids[ItemMatchCandidate].append(candidate.id)
            assert candidate.score == 100
            assert candidate.list_item_id == list_item_id
            assert candidate.product_id == product_id
    finally:
        _cleanup_entities(entity_ids)


def test_item_fanout_job_endpoint_creates_item_matches(
    client: TestClient,
    sync_enqueue_job: str,
) -> None:
    """The FANOUT job endpoint should expand candidates across selected stores."""

    entity_ids: dict[type, list[UUID]] = defaultdict(list)
    route_plan_id: UUID | None = None
    candidate_id: UUID | None = None
    store_a_id: UUID | None = None
    store_b_id: UUID | None = None
    store_product_a_id: UUID | None = None
    store_product_b_id: UUID | None = None

    try:
        with session_scope() as session:
            chain = StoreChain(name=f"Chain {uuid4()}")
            session.add(chain)
            session.flush()
            entity_ids[StoreChain].append(chain.id)

            store_a = Store(
                chain_id=chain.id,
                name="Fanout Store A",
                number="700",
                address_line1="7 API Blvd",
                city="Testville",
                region="TS",
                postal_code="20002",
                country_code="US",
                timezone="UTC",
                phone="555-7000",
            )
            store_b = Store(
                chain_id=chain.id,
                name="Fanout Store B",
                number="701",
                address_line1="8 API Blvd",
                city="Testville",
                region="TS",
                postal_code="20002",
                country_code="US",
                timezone="UTC",
                phone="555-7001",
            )
            session.add_all([store_a, store_b])
            session.flush()
            entity_ids[Store].extend([store_a.id, store_b.id])
            store_a_id = store_a.id
            store_b_id = store_b.id

            product = Product(brand="Fanout Brand", name="Fanout Milk", upc=str(uuid4()))
            rejected_product = Product(
                brand="Fanout Brand",
                name="Fanout Milk (Rejected)",
                upc=str(uuid4()),
            )
            session.add_all([product, rejected_product])
            session.flush()
            entity_ids[Product].extend([product.id, rejected_product.id])

            store_product_a = StoreProduct(
                store_id=store_a.id,
                product_id=product.id,
                external_sku=f"SKU-{uuid4()}",
            )
            store_product_b = StoreProduct(
                store_id=store_b.id,
                product_id=product.id,
                external_sku=f"SKU-{uuid4()}",
            )
            session.add_all([store_product_a, store_product_b])
            session.flush()
            entity_ids[StoreProduct].extend([store_product_a.id, store_product_b.id])
            store_product_a_id = store_product_a.id
            store_product_b_id = store_product_b.id

            shopping_list = ShoppingList(client_id=f"client-{uuid4()}", title="Fanout List")
            session.add(shopping_list)
            session.flush()
            entity_ids[ShoppingList].append(shopping_list.id)

            list_item = ListItem(
                list_id=shopping_list.id,
                position=1,
                item_name="fanout milk",
                raw_text_item="fanout milk",
            )
            session.add(list_item)
            session.flush()
            entity_ids[ListItem].append(list_item.id)

            route_plan = RoutePlan(list_id=shopping_list.id, client_id=f"client-{uuid4()}")
            session.add(route_plan)
            session.flush()
            entity_ids[RoutePlan].append(route_plan.id)
            route_plan_id = route_plan.id

            selections = [
                PlanSelectedStore(plan_id=route_plan.id, store_id=store_a.id),
                PlanSelectedStore(plan_id=route_plan.id, store_id=store_b.id),
            ]
            session.add_all(selections)
            session.flush()
            entity_ids[PlanSelectedStore].extend(sel.id for sel in selections)

            candidate = ItemMatchCandidate(
                plan_id=route_plan.id,
                list_item_id=list_item.id,
                product_id=product.id,
                score=90.0,
            )
            rejected_candidate = ItemMatchCandidate(
                plan_id=route_plan.id,
                list_item_id=list_item.id,
                product_id=rejected_product.id,
                score=50.0,
                rejected_by_user=True,
            )
            session.add_all([candidate, rejected_candidate])
            session.flush()
            entity_ids[ItemMatchCandidate].extend([candidate.id, rejected_candidate.id])
            candidate_id = candidate.id

        assert route_plan_id is not None
        assert store_a_id is not None
        assert store_b_id is not None
        assert store_product_a_id is not None
        assert store_product_b_id is not None
        assert candidate_id is not None

        response = client.post(f"/api/route-plans/{route_plan_id}/item-fanout-jobs")
        assert response.status_code == 201
        job_payload = response.json()
        job_id = UUID(job_payload["id"])
        entity_ids[Job].append(job_id)

        with session_scope() as session:
            job = session.get(Job, job_id)
            assert job is not None
            assert job.status is JobStatus.SUCCESS
            assert job.progress_total == 1
            assert job.progress_current == 1

            matches = session.exec(select(ItemMatch).where(ItemMatch.plan_id == route_plan_id)).all()
            assert len(matches) == 2
            entity_ids[ItemMatch].extend(match.id for match in matches)

            store_ids = {match.store_id for match in matches}
            assert store_ids == {store_a_id, store_b_id}
            assert all(match.item_match_candidate_id == candidate_id for match in matches)
            assert {match.store_product_id for match in matches} == {
                store_product_a_id,
                store_product_b_id,
            }
    finally:
        _cleanup_entities(entity_ids)
