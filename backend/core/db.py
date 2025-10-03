"""Database connection helpers and session utilities."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from importlib import import_module
from typing import Any, Generator

from backend.core.config import settings

logger = logging.getLogger(__name__)

_engine: Any | None = None
_session_factory: Any | None = None


def _bootstrap_sqlalchemy() -> tuple[Any, Any]:
    """Lazy-load SQLAlchemy engine/sessionmaker to avoid hard dependency at import time."""

    global _engine, _session_factory

    if _engine is not None and _session_factory is not None:
        return _engine, _session_factory

    try:
        sqlalchemy = import_module("sqlalchemy")
        orm = import_module("sqlalchemy.orm")
    except ModuleNotFoundError as exc:  # pragma: no cover - triggered only without dependency installed
        message = (
            "SQLAlchemy is required for database access. "
            "Install it with `pip install SQLAlchemy psycopg[binary]`."
        )
        raise RuntimeError(message) from exc

    create_engine = getattr(sqlalchemy, "create_engine")
    sessionmaker = getattr(orm, "sessionmaker")

    engine = create_engine(settings.database_url, future=True, echo=settings.debug)
    _engine = engine
    _session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    return _engine, _session_factory


def get_engine() -> Any:
    """Return the configured SQLAlchemy engine."""

    engine, _ = _bootstrap_sqlalchemy()
    return engine


def get_session_factory() -> Any:
    """Return a configured SQLAlchemy sessionmaker."""

    _, session_factory = _bootstrap_sqlalchemy()
    return session_factory


@contextmanager
def session_scope() -> Generator[Any, None, None]:
    """Provide a transactional scope around operations for use in dependencies."""

    session_factory = get_session_factory()
    session = session_factory()

    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
