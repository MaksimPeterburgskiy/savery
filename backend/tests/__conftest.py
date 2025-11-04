"""Test configuration shared across the backend test suite."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest

from backend.app.config import settings


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations() -> None:
    """Ensure the test database schema is up to date before tests run."""

    config_path = Path(__file__).resolve().parent.parent / "alembic.ini"
    alembic_cfg = Config(str(config_path))
    command.upgrade(alembic_cfg, "head")


@pytest.fixture(autouse=True)
def _configure_demo_task_delay() -> None:
    """Speed up the health demo task for tests while Celery runs normally."""

    previous_delay = settings.celery_demo_task_delay_seconds
    settings.celery_demo_task_delay_seconds = 0

    try:
        yield
    finally:
        settings.celery_demo_task_delay_seconds = previous_delay
