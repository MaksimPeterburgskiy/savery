"""Celery application factory configured for RabbitMQ."""

from celery import Celery
from celery.schedules import crontab
from celery.utils.log import get_task_logger

from backend.app.config import settings


celery_app = Celery("savery")
celery_app.conf.update(
    broker_url=settings.celery_broker_url,
    result_backend=settings.celery_result_backend,
    broker_connection_retry_on_startup=True,
    task_default_queue="default",
    timezone="UTC",
    enable_utc=True,
)


celery_app.conf.beat_schedule = {
    
    #scrape all hannaford stores every day at midnight eastern time
    "scrape-hannaford-every-24-hours": {
        "task": "workers.scraping.scrape_hannaford_stores",
        "schedule": crontab(minute=0, hour=0),
        "args": (),
    },

    #quick test that celery is working every minute
    # "test-celery": {
    #     "task": "workers.scraping.test_celery",
    #     "schedule": 10,
    #     "args": (),
    # },

    # "test-hannaford": {
    #     "task": "workers.scraping.scrape_hannaford_stores",
    #     "schedule": crontab(minute="*/1"),
    #     "args": (),
    # },
    
    # "test-ping": {
    #     "task": "workers.health.ping",
    #      "schedule":5,
    #     "args": (),
    # }
}

celery_app.autodiscover_tasks(["backend.workers"])




@celery_app.task(name="workers.health.ping")
def ping() -> str:
    """Simple task to verify the worker is alive."""
    # Emit an informational log so the worker terminal shows a visible trace
    # when this test task runs.
    logger = get_task_logger(__name__)
    logger.info("ping task executed")

    return "pong"
