"""Integration tests for the demo health Celery task endpoints."""

from __future__ import annotations

import time
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

        plan = RoutePlan(list_id=shopping_list.id, client_token=f"token-{uuid4()}")
        session.add(plan)
        session.flush()

        job = Job(plan_id=plan.id, stage=JobStage.HEALTHCHECK)
        session.add(job)
        session.flush()

        return job.id


def test_trigger_demo_task_returns_job_payload(client: TestClient) -> None:
    """POSTing to the trigger endpoint should enqueue the Celery task."""

    job_id = _create_health_job()

    response = client.post("/api/health/demo-task", json={"job_id": str(job_id)})
    assert response.status_code == 200

    payload = _wait_for_completion(client, job_id, timeout=30.0)
    assert UUID(payload["id"]) == job_id
    assert payload["stage"] == JobStage.HEALTHCHECK.value
    assert payload["status"] == "SUCCESS"
    assert payload["progress_current"] == 100
    assert payload["progress_total"] == 100


def test_get_demo_task_status_returns_current_state(client: TestClient) -> None:
    """The status endpoint should surface the latest job information."""

    job_id = _create_health_job()

    client.post("/api/health/demo-task", json={"job_id": str(job_id)})

    payload = _wait_for_completion(client, job_id, timeout=30.0)
    assert UUID(payload["id"]) == job_id
    assert payload["status"] == "SUCCESS"
    assert payload["progress_current"] == 100
    assert payload["message"] == "Health demo task finished"


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
