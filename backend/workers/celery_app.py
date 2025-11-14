"""Celery application factory configured for RabbitMQ."""

from celery import Celery

from backend.app.config import settings


celery_app = Celery("savery")
celery_app.conf.update(
    broker_url=settings.celery_broker_url,
    result_backend=settings.celery_result_backend,
    broker_connection_retry_on_startup=True,
    task_default_queue="default",
)
celery_app.autodiscover_tasks(["backend.workers"])


@celery_app.task(name="workers.health.ping")
def ping() -> str:
    """Simple task to verify the worker is alive."""

    return "pong"
