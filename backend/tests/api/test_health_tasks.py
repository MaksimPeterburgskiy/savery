"""Integration tests for the demo health Celery task endpoints."""

from __future__ import annotations

from datetime import datetime
import time
from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.db import session_scope
from backend.app.main import create_app
from backend.app.models import Job, JobStage, RoutePlan, ShoppingList


@pytest.fixture()
def client() -> TestClient:
    """Provide a FastAPI test client for the task routes."""

    with TestClient(create_app()) as test_client:
        yield test_client


def _create_health_job() -> UUID:
    """Insert a Job wired to the health stage so it can be triggered."""

    with session_scope() as session:
        shopping_list = ShoppingList(client_id=f"demo-client-{uuid4()}", title="Demo")
        session.add(shopping_list)
        session.flush()

        plan = RoutePlan(list_id=shopping_list.id, client_id=f"token-{uuid4()}")
        session.add(plan)
        session.flush()

        job = Job(plan_id=plan.id, stage=JobStage.HEALTHCHECK)
        session.add(job)
        session.flush()

        return job.id


def _cleanup_health_job(job_id: UUID) -> None:
    """Remove the job and related plan data created for test execution."""

    with session_scope() as session:
        job = session.get(Job, job_id)
        if job is None:
            return

        plan = session.get(RoutePlan, job.plan_id)
        list_id = plan.list_id if plan else None

        session.delete(job)

        if plan is not None:
            session.delete(plan)

        if list_id is not None:
            shopping_list = session.get(ShoppingList, list_id)
            if shopping_list is not None:
                session.delete(shopping_list)


@pytest.fixture()
def health_job_id() -> Iterator[UUID]:
    """Provision and tear down a health job for the Celery demo tests."""

    job_id = _create_health_job()
    try:
        yield job_id
    finally:
        _cleanup_health_job(job_id)


def test_trigger_demo_task_returns_job_payload(
    client: TestClient, health_job_id: UUID
) -> None:
    """POSTing to the trigger endpoint should enqueue the Celery task."""

    job_id = health_job_id

    response = client.post("/api/health/demo-task", json={"job_id": str(job_id)})
    assert response.status_code == 200

    payload = _wait_for_completion(client, job_id, timeout=30.0)
    assert UUID(payload["id"]) == job_id
    assert payload["stage"] == JobStage.HEALTHCHECK.value
    assert payload["status"] == "SUCCESS"
    assert payload["progress_current"] == 100
    assert payload["progress_total"] == 100
    _assert_job_timestamps(payload)


def test_get_demo_task_status_returns_current_state(
    client: TestClient, health_job_id: UUID
) -> None:
    """The status endpoint should surface the latest job information."""

    job_id = health_job_id

    client.post("/api/health/demo-task", json={"job_id": str(job_id)})

    payload = _wait_for_completion(client, job_id, timeout=30.0)
    assert UUID(payload["id"]) == job_id
    assert payload["status"] == "SUCCESS"
    assert payload["progress_current"] == 100
    assert payload["message"] == "Health demo task finished"
    _assert_job_timestamps(payload)


def _wait_for_completion(client: TestClient, job_id: UUID, *, timeout: float = 5.0) -> dict:
    """Poll the status endpoint until the job completes or the timeout expires."""

    deadline = time.monotonic() + timeout
    while True:
        response = client.get(f"/api/health/demo-task/{job_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload.get("status") == "SUCCESS":
            return payload
        if time.monotonic() > deadline:
            raise AssertionError(f"Job {job_id} did not complete within {timeout} seconds")
        time.sleep(0.1)


def _assert_job_timestamps(payload: dict[str, Any]) -> None:
    """Verify the demo job reports both timestamps and that they increase monotonically."""

    started_value = payload.get("started_at")
    completed_value = payload.get("completed_at")
    assert started_value is not None, "Job payload should include a started_at timestamp"
    assert completed_value is not None, "Job payload should include a completed_at timestamp"

    started_at = datetime.fromisoformat(started_value)
    completed_at = datetime.fromisoformat(completed_value)
    assert started_at <= completed_at, "started_at must not be after completed_at"
