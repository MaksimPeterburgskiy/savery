"""Bridge Celery task result events to WebSocket subscribers."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, DefaultDict, Set

from celery.backends.base import DisabledBackend
from celery.states import READY_STATES

from backend.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


class JobStatusManager:
    """Stream Celery task state changes to interested listeners."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._result_consumer = None
        self._drain_task: asyncio.Task[None] | None = None
        self._stop_event: asyncio.Event | None = None
        self._queues: DefaultDict[str, Set[asyncio.Queue[Any]]] = defaultdict(set)
        self._lock = asyncio.Lock()
        self._enabled: bool = False
        self._start_attempted: bool = False
        self._queue_drop_counts: DefaultDict[asyncio.Queue[Any], int] = defaultdict(int)
        self._canceling: Set[str] = set()

    @property
    def _queue_full_drop_threshold(self) -> int:
        """Number of consecutive QueueFull events before dropping a listener."""

        return 3

    @property
    def enabled(self) -> bool:
        """Return True when the Celery consumer is active."""

        return self._enabled

    async def start(self) -> None:
        """Initialise the Celery ResultConsumer and background drain loop."""

        if self._enabled:
            return

        try:
            backend = celery_app.backend
        except Exception as exc:
            if not self._start_attempted:
                logger.warning(
                    "Unable to initialise Celery result backend; job websocket streaming will fall back to DB polling: %s",
                    exc,
                )
            self._start_attempted = True
            return

        if backend is None or isinstance(backend, DisabledBackend):
            if not self._start_attempted:
                logger.warning(
                    "Celery result backend unavailable; job websocket streaming will fall back to DB polling"
                )
            self._start_attempted = True
            return

        consumer = getattr(backend, "result_consumer", None)
        if consumer is None:
            if not self._start_attempted:
                logger.warning(
                    "Celery backend does not expose a result consumer; job websocket streaming will fall back to DB polling"
                )
            self._start_attempted = True
            return

        self._loop = asyncio.get_running_loop()
        self._stop_event = asyncio.Event()
        self._result_consumer = consumer
        self._result_consumer.on_message = self._handle_message
        self._enabled = True
        self._start_attempted = True
        self._drain_task = asyncio.create_task(self._drain_loop())
        logger.info("Started Celery result consumer for job status websockets")

    async def stop(self) -> None:
        """Tear down the consumer and background task."""

        if self._stop_event:
            self._stop_event.set()

        if self._drain_task:
            await self._drain_task

        if self._result_consumer:
            try:
                await asyncio.to_thread(self._result_consumer.stop)
            except Exception as exc:  
                logger.warning("Failed to stop result consumer cleanly: %s", exc)

        self._drain_task = None
        self._result_consumer = None
        self._stop_event = None
        self._enabled = False
        self._start_attempted = False
        self._queues.clear()
        self._queue_drop_counts.clear()
        self._canceling.clear()
        logger.info("Stopped Celery result consumer for job status websockets")

    async def subscribe(self, task_id: str, queue: asyncio.Queue[Any]) -> bool:
        """Subscribe an async queue to receive state changes for the task."""

        await self.start()
        if not self._enabled or self._result_consumer is None:
            return False

        async with self._lock:
            self._queues[task_id].add(queue)
            self._queue_drop_counts.pop(queue, None)

        try:
            await asyncio.to_thread(self._result_consumer.consume_from, task_id)
        except Exception as exc:
            logger.warning("Failed to subscribe to task %s updates via Celery backend: %s", task_id, exc)
            async with self._lock:
                listeners = self._queues.get(task_id)
                if listeners and queue in listeners:
                    listeners.remove(queue)
                    if not listeners:
                        self._queues.pop(task_id, None)
            return False

        return True

    async def unsubscribe(self, task_id: str, queue: asyncio.Queue[Any]) -> None:
        """Remove a queue subscription and cancel the backend feed if idle."""

        cancel_backend = False

        async with self._lock:
            self._canceling.add(task_id)
            listeners = self._queues.get(task_id)
            if listeners and queue in listeners:
                listeners.remove(queue)
                self._queue_drop_counts.pop(queue, None)
                if not listeners:
                    self._queues.pop(task_id, None)
                    cancel_backend = True

        if cancel_backend and self._enabled and self._result_consumer is not None:
            try:
                await asyncio.to_thread(self._result_consumer.cancel_for, task_id)
            except Exception as exc:  
                logger.debug("Failed to cancel result consumer for %s: %s", task_id, exc)
            finally:
                async with self._lock:
                    self._canceling.discard(task_id)
        else:
            async with self._lock:
                self._canceling.discard(task_id)

    async def _auto_unsubscribe(self, task_id: str) -> None:
        """Detach result consumer subscriptions once a task reaches a terminal state."""

        cancel_backend = False

        async with self._lock:
            self._canceling.add(task_id)
            listeners = self._queues.pop(task_id, None)
            if listeners:
                cancel_backend = True
                for listener in listeners:
                    self._queue_drop_counts.pop(listener, None)

        try:
            if cancel_backend and self._enabled and self._result_consumer is not None:
                try:
                    await asyncio.to_thread(self._result_consumer.cancel_for, task_id)
                except Exception as exc:  
                    logger.debug("Failed to cancel result consumer for %s: %s", task_id, exc)
        finally:
            async with self._lock:
                self._canceling.discard(task_id)

    async def _drain_loop(self) -> None:
        """Continuously drain the Celery result backend for state changes."""

        if self._result_consumer is None or self._stop_event is None:
            return

        while not self._stop_event.is_set():
            try:
                await asyncio.to_thread(self._result_consumer.drain_events, timeout=1.0)
            except asyncio.CancelledError:
                return
            except Exception as exc: 
                logger.warning("Error while draining task status events: %s", exc)
                await asyncio.sleep(1.0)

    def _handle_message(self, meta: dict[str, Any]) -> None:
        """Thread-safe hook invoked by the Celery result consumer."""

        if not self._loop:
            return
        if self._loop.is_closed():
            return
        self._loop.call_soon_threadsafe(lambda: self._loop.create_task(self._dispatch_message(meta)))

    async def _dispatch_message(self, meta: dict[str, Any]) -> None:
        """Fan out a Celery state change to all subscribed queues."""

        task_id = meta.get("task_id")
        if not task_id:
            return

        async with self._lock:
            if task_id in self._canceling:
                return
            listeners = list(self._queues.get(task_id, ()))

        if not listeners:
            return

        failed_queues: list[asyncio.Queue[Any]] = []
        delivered_queues: list[asyncio.Queue[Any]] = []

        for queue in listeners:
            try:
                queue.put_nowait(meta)
                delivered_queues.append(queue)
            except asyncio.QueueFull:
                failed_queues.append(queue)
                logger.debug("Dropping task status event for %s because the queue is full", task_id)

        cancel_backend = False
        if failed_queues or delivered_queues:
            async with self._lock:
                if task_id in self._canceling:
                    return
                for queue in delivered_queues:
                    self._queue_drop_counts.pop(queue, None)
                for queue in failed_queues:
                    failures = self._queue_drop_counts[queue] + 1
                    if failures >= self._queue_full_drop_threshold:
                        listeners_for_task = self._queues.get(task_id)
                        if listeners_for_task and queue in listeners_for_task:
                            listeners_for_task.remove(queue)
                            self._queue_drop_counts.pop(queue, None)
                            if not listeners_for_task:
                                self._queues.pop(task_id, None)
                                cancel_backend = True
                    else:
                        self._queue_drop_counts[queue] = failures

        if cancel_backend and self._enabled and self._result_consumer is not None:
            try:
                await asyncio.to_thread(self._result_consumer.cancel_for, task_id)
            except Exception as exc:  
                logger.debug("Failed to cancel result consumer for %s: %s", task_id, exc)

        if meta.get("status") in READY_STATES:
            asyncio.create_task(self._auto_unsubscribe(task_id))


job_status_manager = JobStatusManager()

__all__ = ["job_status_manager", "JobStatusManager"]
