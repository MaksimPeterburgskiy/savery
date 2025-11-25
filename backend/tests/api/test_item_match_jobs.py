"""Tests for the item match job lifecycle endpoints."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.db import session_scope
from backend.app.main import create_app
from backend.app.models import Job, JobStage, JobStatus, RoutePlan, ShoppingList


@pytest.fixture()
def client() -> Iterator[TestClient]:
    """Provide a FastAPI test client for exercising the API."""

    with TestClient(create_app()) as test_client:
        yield test_client


def _create_route_plan() -> dict[str, UUID]:
    """Insert the minimal shopping list + route plan graph used by the tests."""

    with session_scope() as session:
        shopping_list = ShoppingList(client_id=f"test-client-{uuid4()}", title="Match Job Test")
        session.add(shopping_list)
        session.flush()

        plan = RoutePlan(list_id=shopping_list.id, client_id=f"token-{uuid4()}")
        session.add(plan)
        session.flush()

        return {"shopping_list_id": shopping_list.id, "route_plan_id": plan.id}


def _cleanup_route_plan(plan_id: UUID, shopping_list_id: UUID) -> None:
    """Remove the plan, its jobs, and the backing shopping list."""

    with session_scope() as session:
        plan = session.get(RoutePlan, plan_id)
        if plan is not None:
            session.delete(plan)

        shopping_list = session.get(ShoppingList, shopping_list_id)
        if shopping_list is not None:
            session.delete(shopping_list)


@pytest.fixture()
def route_plan() -> Iterator[dict[str, UUID]]:
    """Create and tear down a route plan for the duration of a test."""

    data = _create_route_plan()
    try:
        yield data
    finally:
        _cleanup_route_plan(data["route_plan_id"], data["shopping_list_id"])


def _create_match_job(plan_id: UUID, *, status: JobStatus = JobStatus.PENDING) -> UUID:
    """Insert a MATCH-stage job for convenience."""

    with session_scope() as session:
        job = Job(plan_id=plan_id, stage=JobStage.MATCH, status=status)
        session.add(job)
        session.flush()
        return job.id


def test_create_item_match_job_enqueues_task(client: TestClient, route_plan: dict[str, UUID], monkeypatch: pytest.MonkeyPatch) -> None:
    """Creating a job should enqueue the worker task exactly once."""

    recorded_job_id: UUID | None = None

    def _fake_enqueue(job_id: UUID) -> str:  # pragma: no cover - injected in test
        nonlocal recorded_job_id
        recorded_job_id = job_id if isinstance(job_id, UUID) else UUID(str(job_id))
        return "fake-task-id"

    monkeypatch.setattr(
        "backend.app.api.routes.planning.planning_job_endpoints.enqueue_job",
        _fake_enqueue,
    )

    plan_id = route_plan["route_plan_id"]
    response = client.post(f"/api/route-plans/{plan_id}/item-match-jobs")
    assert response.status_code == 201

    payload = response.json()
    job_id = UUID(payload["id"])
    assert recorded_job_id == job_id
    assert payload["status"] == JobStatus.PENDING.value

    with session_scope() as session:
        job = session.get(Job, job_id)
        assert job is not None
        assert job.stage == JobStage.MATCH
        assert job.status == JobStatus.PENDING


def test_create_item_match_job_rejects_when_active_exists(client: TestClient, route_plan: dict[str, UUID], monkeypatch: pytest.MonkeyPatch) -> None:
    """A 409 should be returned if an active MATCH job already exists."""

    plan_id = route_plan["route_plan_id"]
    _create_match_job(plan_id, status=JobStatus.PENDING)

    monkeypatch.setattr(
        "backend.app.api.routes.planning.planning_job_endpoints.enqueue_job",
        lambda job_id: None,
    )

    response = client.post(f"/api/route-plans/{plan_id}/item-match-jobs")
    assert response.status_code == 409


def test_cancel_item_match_job_sets_cancelled_status(client: TestClient, route_plan: dict[str, UUID]) -> None:
    """Cancelling a job should mark it as CANCELLED and include the message."""

    plan_id = route_plan["route_plan_id"]
    job_id = _create_match_job(plan_id, status=JobStatus.PENDING)

    response = client.delete(f"/api/route-plans/{plan_id}/item-match-jobs/{job_id}")
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == JobStatus.CANCELLED.value
    assert payload["message"] == "Cancelled by user"


def test_get_item_match_candidate_by_id_returns_404_when_missing(client: TestClient) -> None:
    """Requesting a nonexistent candidate should surface a 404."""

    missing_id = uuid4()
    response = client.get(f"/api/item-match-candidates/{missing_id}")
    assert response.status_code == 404
