"""Alembic helpers for managing database revisions."""

from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

from backend.app.config import settings


def _paths() -> tuple[Path, Path]:
    base = Path(__file__).resolve().parents[1]
    return base / "alembic.ini", base / "migrations"


def build_alembic_config() -> Config:
    """Return an Alembic config wired to the project settings."""

    ini_path, migrations_path = _paths()
    config = Config(str(ini_path))
    config.set_main_option("script_location", str(migrations_path))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


def _configure_alembic_logging() -> None:
    """Ensure Alembic logs bubble up through the FastAPI logger."""

    alembic_logger = logging.getLogger("alembic")
    alembic_logger.setLevel(logging.INFO)

    handler_exists = any(
        getattr(handler, "_savery_alembic_handler", False)
        for handler in alembic_logger.handlers
    )
    if not handler_exists:
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        handler.setFormatter(
            logging.Formatter("%(levelname)s  [%(name)s] %(message)s")
        )
        handler._savery_alembic_handler = True  # type: ignore[attr-defined]
        alembic_logger.addHandler(handler)

    alembic_logger.propagate = True


def upgrade_to_head() -> None:
    """Apply database migrations up to the latest revision."""

    config = build_alembic_config()
    _configure_alembic_logging()
    command.upgrade(config, "head")
