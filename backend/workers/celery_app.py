"""Celery application factory configured for RabbitMQ."""

from celery import Celery
from kombu import Queue

from backend.core.config import settings


celery_app = Celery("savery")
celery_app.conf.update(
    broker_url=settings.celery_broker_url,
    result_backend=settings.celery_result_backend,
    broker_connection_retry_on_startup=True,
    task_default_queue="default",
    task_queues=(
        Queue("default"),
        Queue("matching"),
        Queue("scraping"),
        Queue("optimization"),
    ),
    task_routes={
        "workers.matching.*": {"queue": "matching"},
        "workers.scraping.*": {"queue": "scraping"},
        "workers.optimize.*": {"queue": "optimization"},
    },
)
celery_app.autodiscover_tasks(["backend.workers"])


@celery_app.task(name="workers.health.ping")
def ping() -> str:
    """Simple task to verify the worker is alive."""

    return "pong"
