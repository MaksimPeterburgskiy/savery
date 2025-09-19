"""Shared dependency placeholders for FastAPI routes."""

from collections.abc import AsyncGenerator
from typing import Any

from backend.core.db import session_scope


async def get_db() -> AsyncGenerator[Any, None]:
    """Yield a database session for request handling."""

    with session_scope() as session:
        yield session
