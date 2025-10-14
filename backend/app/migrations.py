"""Alembic helpers for managing database revisions."""

from __future__ import annotations

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


def upgrade_to_head() -> None:
    """Apply database migrations up to the latest revision."""

    config = build_alembic_config()
    command.upgrade(config, "head")
