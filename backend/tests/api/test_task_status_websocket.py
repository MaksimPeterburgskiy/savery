"""Integration tests for the job status WebSocket endpoint."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.app.db import session_scope
from backend.app.main import create_app
from backend.app.models import Job, JobStage, JobStatus, RoutePlan, ShoppingList
import backend.app.api.routes.tasks_websocket as tasks_websocket
import backend.app.task_status as task_status_module
import backend.app.lifecycle as lifecycle_module


class StubJobStatusManager:
    """Lightweight stand-in for the Celery-backed manager used in tests."""

    def __init__(self) -> None:
        self.queue: asyncio.Queue | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.enabled = True

    async def start(self) -> None:  # pragma: no cover - hook used in lifespan
        return None

    async def stop(self) -> None:  # pragma: no cover - hook used in lifespan
        return None

    async def subscribe(self, task_id: str, queue: asyncio.Queue) -> bool:
        self.queue = queue
        self.loop = asyncio.get_running_loop()
        return True

    async def unsubscribe(self, task_id: str, queue: asyncio.Queue) -> None:
        return None

    def push(self, meta: dict) -> None:
        """Inject a broker message into the websocket stream."""

        if self.queue and self.loop:
            asyncio.run_coroutine_threadsafe(self.queue.put(meta), self.loop)


def _create_job_with_plan() -> tuple[UUID, UUID]:
    """Insert a plan and job for test execution."""

    with session_scope() as session:
        shopping_list = ShoppingList(client_id=f"ws-client-{uuid4()}", title="WebSocket Test")
        session.add(shopping_list)
        session.flush()

        plan = RoutePlan(list_id=shopping_list.id, client_id=f"ws-client-{uuid4()}")
        session.add(plan)
        session.flush()

        job = Job(
            plan_id=plan.id,
            stage=JobStage.MATCH,
            status=JobStatus.PENDING,
            task_id="ws-test-task",
            progress_current=0,
            progress_total=3,
        )
        session.add(job)
        session.flush()

        return job.id, plan.id


def _cleanup_job(job_id: UUID, plan_id: UUID) -> None:
    """Remove the job and related plan and list artifacts."""

    with session_scope() as session:
        job = session.get(Job, job_id)
        plan = session.get(RoutePlan, plan_id)
        list_id = plan.list_id if plan else None

        if job:
            session.delete(job)
        if plan:
            session.delete(plan)
        if list_id:
            shopping_list = session.get(ShoppingList, list_id)
            if shopping_list:
                session.delete(shopping_list)


def _update_job(job_id: UUID, *, status: JobStatus, current: int, total: int) -> None:
    """Persist a new snapshot of the job."""

    with session_scope() as session:
        job = session.get(Job, job_id)
        assert job is not None
        job.status = status
        job.progress_current = current
        job.progress_total = total
        session.add(job)


@pytest.fixture()
def job_record() -> Iterator[tuple[UUID, UUID]]:
    """Provision and tear down a job for WebSocket streaming tests."""

    job_id, plan_id = _create_job_with_plan()
    try:
        yield job_id, plan_id
    finally:
        _cleanup_job(job_id, plan_id)


def test_job_status_websocket_streams_db_changes(job_record: tuple[UUID, UUID], stub_job_status_manager: StubJobStatusManager) -> None:
    """WebSocket should push status changes even when falling back to DB polling."""

    job_id, plan_id = job_record

    with TestClient(create_app()) as client:
        with client.websocket_connect(f"/api/ws/jobs/{job_id}?plan_id={plan_id}") as websocket:
            initial = websocket.receive_json()
            assert initial["status"] == JobStatus.PENDING.value

            _update_job(job_id, status=JobStatus.RUNNING, current=1, total=3)
            running = websocket.receive_json()
            assert running["status"] == JobStatus.RUNNING.value
            assert running["progress_current"] == 1

            _update_job(job_id, status=JobStatus.SUCCESS, current=3, total=3)
            final = websocket.receive_json()
            assert final["status"] == JobStatus.SUCCESS.value
            assert final["progress_current"] == 3


def test_job_status_websocket_rejects_wrong_plan(job_record: tuple[UUID, UUID], stub_job_status_manager: StubJobStatusManager) -> None:
    """Handshake should close with 4404 when the plan_id does not match the job."""

    job_id, _plan_id = job_record
    wrong_plan = uuid4()

    with TestClient(create_app()) as client:
        with pytest.raises(WebSocketDisconnect) as excinfo:
            with client.websocket_connect(f"/api/ws/jobs/{job_id}?plan_id={wrong_plan}") as websocket:
                websocket.receive_text()

    assert excinfo.value.code == 4404


@pytest.fixture()
def stub_job_status_manager(monkeypatch: pytest.MonkeyPatch) -> Iterator[StubJobStatusManager]:
    """Swap the Celery-backed manager for an in-process stub in tests."""

    stub = StubJobStatusManager()
    monkeypatch.setattr(tasks_websocket, "job_status_manager", stub)
    monkeypatch.setattr(task_status_module, "job_status_manager", stub)
    monkeypatch.setattr(lifecycle_module, "job_status_manager", stub)
    yield stub


def test_job_status_websocket_forwards_celery_meta(job_record: tuple[UUID, UUID], stub_job_status_manager: StubJobStatusManager) -> None:
    """Celery broker messages should be forwarded without extra DB polls."""

    job_id, plan_id = job_record

    with TestClient(create_app()) as client:
        with client.websocket_connect(f"/api/ws/jobs/{job_id}?plan_id={plan_id}") as websocket:
            initial = websocket.receive_json()
            assert initial["status"] == JobStatus.PENDING.value

            running_payload = {**initial, "status": JobStatus.RUNNING.value, "progress_current": 2}
            stub_job_status_manager.push({"task_id": initial["task_id"], "status": "PROGRESS", "result": running_payload})

            running = websocket.receive_json()
            assert running["status"] == JobStatus.RUNNING.value
            assert running["progress_current"] == 2

            success_payload = {**running_payload, "status": JobStatus.SUCCESS.value, "progress_current": 3, "progress_total": 3}
            stub_job_status_manager.push({"task_id": initial["task_id"], "status": "SUCCESS", "result": success_payload})

            final = websocket.receive_json()
            assert final["status"] == JobStatus.SUCCESS.value
            assert final["progress_current"] == 3
