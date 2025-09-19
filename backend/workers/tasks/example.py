"""Example Celery task."""

from celery import shared_task


@shared_task(name="workers.example.echo")
def echo(message: str) -> str:
    """Echo the provided message."""

    return message
