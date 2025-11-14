"""Database engine and session utilities backed by SQLModel."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlmodel import Session, SQLModel, create_engine

from backend.app.config import settings

_engine = None


def get_engine():
    """Lazily create and cache the SQLModel engine."""

    global _engine

    if _engine is None:
        _engine = create_engine(settings.database_url, echo=settings.debug)

    return _engine


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Provide a transactional SQLModel session for request-scoped work."""

    engine = get_engine()
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


def create_db_and_tables() -> None:
    """Ensure the database schema defined by SQLModel metadata exists."""

    engine = get_engine()
    SQLModel.metadata.create_all(engine)
