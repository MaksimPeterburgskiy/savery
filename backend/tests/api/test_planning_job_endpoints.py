"""Additional coverage for planning job endpoints."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from backend.app.db import session_scope
from backend.app.main import create_app
from backend.app.models import Job, JobStage, JobStatus, RoutePlan, ShoppingList, utcnow


@pytest.fixture()
def client() -> Iterator[TestClient]:
    """Provide a FastAPI test client for exercising the API."""

    with TestClient(create_app()) as test_client:
        yield test_client


def _create_route_plan() -> dict[str, UUID]:
    """Insert the minimal shopping list + route plan graph used by the tests."""

    with session_scope() as session:
        shopping_list = ShoppingList(client_id=f"test-client-{uuid4()}", title="Planning Jobs Test")
        session.add(shopping_list)
        session.flush()

        plan = RoutePlan(list_id=shopping_list.id, client_id=f"token-{uuid4()}")
        session.add(plan)
        session.flush()

        return {"shopping_list_id": shopping_list.id, "route_plan_id": plan.id}


def _cleanup_route_plan(plan_id: UUID, shopping_list_id: UUID) -> None:
    """Remove the plan, its jobs, and the backing shopping list."""

    with session_scope() as session:
        jobs = session.exec(select(Job).where(Job.plan_id == plan_id)).all()
        for job in jobs:
            session.delete(job)

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


def _create_job(
    plan_id: UUID,
    *,
    stage: JobStage,
    status: JobStatus = JobStatus.PENDING,
    **kwargs,
) -> UUID:
    """Insert a job for convenience."""

    with session_scope() as session:
        job = Job(plan_id=plan_id, stage=stage, status=status, **kwargs)
        session.add(job)
        session.flush()
        return job.id


def test_list_plan_route_jobs_filters_active_only(client: TestClient, route_plan: dict[str, UUID]) -> None:
    """Only active OPTIMIZE jobs should be returned when requested."""

    plan_id = route_plan["route_plan_id"]
    active_id = _create_job(plan_id, stage=JobStage.OPTIMIZE, status=JobStatus.PENDING)
    _create_job(plan_id, stage=JobStage.OPTIMIZE, status=JobStatus.SUCCESS)

    response = client.get(f"/api/route-plans/{plan_id}/plan-route-jobs", params={"active_only": True})

    assert response.status_code == 200
    payload = response.json()
    assert [UUID(job["id"]) for job in payload] == [active_id]
    assert payload[0]["status"] == JobStatus.PENDING.value


def test_get_plan_route_job_active_returns_404_when_missing(client: TestClient, route_plan: dict[str, UUID]) -> None:
    """Requesting an active OPTIMIZE job should fail cleanly when none exist."""

    plan_id = route_plan["route_plan_id"]
    _create_job(plan_id, stage=JobStage.OPTIMIZE, status=JobStatus.SUCCESS)

    response = client.get(f"/api/route-plans/{plan_id}/plan-route-jobs/active")

    assert response.status_code == 404


def test_create_item_fanout_job_resets_existing_state(
    client: TestClient, route_plan: dict[str, UUID], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-running a FANOUT job should reset progress fields before enqueueing."""

    plan_id = route_plan["route_plan_id"]
    original_id = _create_job(
        plan_id,
        stage=JobStage.FANOUT,
        status=JobStatus.SUCCESS,
        progress_current=3,
        progress_total=5,
        message="done",
        started_at=utcnow(),
        completed_at=utcnow(),
        task_id=None,
    )

    recorded_job_id: UUID | None = None

    def _fake_enqueue(job_id: UUID) -> str:  # pragma: no cover - injected in test
        nonlocal recorded_job_id
        recorded_job_id = job_id if isinstance(job_id, UUID) else UUID(str(job_id))
        return "fake-task-id"

    monkeypatch.setattr(
        "backend.app.api.routes.planning.planning_job_endpoints.enqueue_job",
        _fake_enqueue,
    )

    response = client.post(f"/api/route-plans/{plan_id}/item-fanout-jobs")
    assert response.status_code == 201

    payload = response.json()
    assert UUID(payload["id"]) == original_id
    assert payload["status"] == JobStatus.PENDING.value
    assert payload["progress_current"] == 0
    assert payload["progress_total"] is None
    assert payload["message"] is None
    assert payload["started_at"] is None
    assert payload["completed_at"] is None
    assert recorded_job_id == original_id

    with session_scope() as session:
        job = session.get(Job, original_id)
        assert job is not None
        assert job.status == JobStatus.PENDING
        assert job.task_id == ""


def test_cancel_item_fanout_job_rejects_non_active_status(client: TestClient, route_plan: dict[str, UUID]) -> None:
    """Only active FANOUT jobs should be cancellable."""

    plan_id = route_plan["route_plan_id"]
    job_id = _create_job(plan_id, stage=JobStage.FANOUT, status=JobStatus.SUCCESS)

    response = client.delete(f"/api/route-plans/{plan_id}/item-fanout-jobs/{job_id}")

    assert response.status_code == 400
