"""WebSocket endpoint that streams Job status updates to clients."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, WebSocket
from fastapi.encoders import jsonable_encoder
from starlette.websockets import WebSocketDisconnect, WebSocketState

from ...models import JobStatus
from ...task_status import job_status_manager
from ...tasks import get_job_status

router = APIRouter()
logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {JobStatus.SUCCESS.value, JobStatus.FAILED.value}
DB_POLL_INTERVAL_SECONDS = 1.0
MAX_DB_POLL_INTERVAL_SECONDS = 5.0
QUEUE_MAXSIZE = 100


async def _load_job_status(job_id: UUID) -> dict[str, Any]:
    """Fetch the latest persisted job payload in a worker thread."""

    return await asyncio.to_thread(get_job_status, job_id)


def _extract_payload_from_meta(meta: Any) -> dict[str, Any] | None:
    """Return the job payload embedded in a Celery result backend message, if present."""

    if not isinstance(meta, dict):
        return None

    candidate = meta.get("result")
    if isinstance(candidate, dict) and candidate.get("id"):
        return candidate

    # Some backends may pass the full payload directly in the message.
    if meta.get("id") and meta.get("status"):
        return meta  # type: ignore[return-value]

    return None


@router.websocket("/ws/jobs/{job_id}")
async def stream_job_status(websocket: WebSocket, job_id: UUID, plan_id: UUID | None = Query(default=None)) -> None:
    """Push real-time job progress to clients with a Celery backend feed and DB fallback."""

    try:
        initial_payload = await _load_job_status(job_id)
    except ValueError:
        await websocket.close(code=4404)
        return

    if plan_id is not None and initial_payload.get("plan_id") != str(plan_id):
        logger.debug("Rejecting websocket for job %s due to plan mismatch (%s != %s)", job_id, plan_id, initial_payload.get("plan_id"))
        await websocket.close(code=4404)
        return

    await websocket.accept()
    await websocket.send_json(jsonable_encoder(initial_payload))

    task_id = initial_payload.get("task_id")
    loop = asyncio.get_running_loop()
    subscription_queue: asyncio.Queue[dict[str, Any]] | None = None
    poll_interval = DB_POLL_INTERVAL_SECONDS

    if task_id:
        subscription_queue = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
        if not await job_status_manager.subscribe(task_id, subscription_queue):
            subscription_queue = None
            logger.info("Falling back to DB polling for job %s (task %s)", job_id, task_id)

    last_payload = initial_payload

    try:
        while True:
            broker_payload: dict[str, Any] | None = None

            if subscription_queue is not None:
                try:
                    meta = await asyncio.wait_for(subscription_queue.get(), timeout=poll_interval)
                    broker_payload = _extract_payload_from_meta(meta)
                except asyncio.TimeoutError:
                    pass
            else:
                await asyncio.sleep(poll_interval)

            if broker_payload is not None:
                current_payload = broker_payload
            else:
                try:
                    current_payload = await _load_job_status(job_id)
                except ValueError:
                    await websocket.close(code=4404)
                    break

            if plan_id is not None and current_payload.get("plan_id") != str(plan_id):
                await websocket.close(code=4404)
                break

            if current_payload != last_payload:
                await websocket.send_json(jsonable_encoder(current_payload))
                last_payload = current_payload
                poll_interval = DB_POLL_INTERVAL_SECONDS
            else:
                poll_interval = min(MAX_DB_POLL_INTERVAL_SECONDS, poll_interval * 2)

            if current_payload.get("status") in TERMINAL_STATUSES:
                break
    except WebSocketDisconnect:
        logger.debug("Client disconnected from job %s websocket", job_id)
    except Exception as exc:  # pragma: no cover - defensive logging for unexpected failures
        logger.exception("Unhandled error in job status websocket for %s: %s", job_id, exc)
        try:
            await websocket.send_json({"error": "Internal server error", "message": str(exc)})
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        if subscription_queue is not None and task_id:
            await job_status_manager.unsubscribe(task_id, subscription_queue)
        if websocket.client_state != WebSocketState.DISCONNECTED:
            try:
                await websocket.close()
            except Exception:
                pass
