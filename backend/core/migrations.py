"""Helpers for coordinating Alembic migrations with application startup."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterable, Tuple, Type

try:  # pragma: no cover - optional during bootstrap
    from sqlalchemy.exc import SQLAlchemyError
except ModuleNotFoundError:  # pragma: no cover
    class SQLAlchemyError(Exception):
        """Fallback when SQLAlchemy is not installed yet."""


from backend.core.config import settings
from backend.core.db import get_engine

logger = logging.getLogger(__name__)


def _load_alembic() -> Tuple[Type[object], Type[object], Type[object]]:
    try:
        from alembic.config import Config as AlembicConfig
        from alembic.runtime.migration import MigrationContext as AlembicMigrationContext
        from alembic.script import ScriptDirectory as AlembicScriptDirectory
    except ModuleNotFoundError as exc:  # pragma: no cover - requires missing dependency
        raise RuntimeError(
            "Alembic is required for migration utilities. Install backend dependencies"
            " with `pip install -r backend/requirements.txt`."
        ) from exc

    return AlembicConfig, AlembicMigrationContext, AlembicScriptDirectory


def _alembic_paths() -> tuple[Path, Path]:
    root = Path(__file__).resolve().parents[1]
    return root / "alembic.ini", root / "migrations"


def build_alembic_config() -> Any:
    """Return an ``alembic.config.Config`` wired to project paths & settings."""

    Config, _, _ = _load_alembic()
    ini_path, migrations_path = _alembic_paths()

    config = Config(str(ini_path))
    config.set_main_option("script_location", str(migrations_path))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


def _expected_heads(script: Any) -> Iterable[str]:
    heads = script.get_heads()
    return heads


def ensure_database_revision() -> None:
    """Validate that the connected database is on the latest Alembic head.

    Raises a ``RuntimeError`` when the database revisions do not match the
    migration scripts. When the check succeeds, the function returns ``None``.
    ``SQLAlchemyError`` exceptions are allowed to propagate so callers can deal
    with connection issues explicitly (e.g., retry or skip depending on
    environment).
    """

    Config, MigrationContext, ScriptDirectory = _load_alembic()

    config = build_alembic_config()
    script = ScriptDirectory.from_config(config)
    expected = set(_expected_heads(script))

    engine = get_engine()

    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current = set(context.get_current_heads() or [])
    except SQLAlchemyError:
        logger.exception("Unable to verify database revision via Alembic")
        raise

    if not current:
        raise RuntimeError(
            "Database is not stamped with any Alembic revision. Run `alembic upgrade head`."
        )

    if current != expected:
        raise RuntimeError(
            "Database schema is out of date. Current revision(s): %s; expected head(s): %s. "
            "Run `alembic upgrade head`."
            % (sorted(current), sorted(expected))
        )

    logger.debug("Database schema is up to date (revision %s)", sorted(current))
