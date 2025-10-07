"""Alembic environment bridging SQLModel metadata."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig
from typing import Iterable

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from backend.app.config import settings
from backend.app.db import get_engine

# import models so SQLModel metadata is populated
from backend.app import models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""

    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)

    with context.begin_transaction():
        context.run_migrations()


def _run_sync_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    connectable = get_engine()

    def _run_with_connection(connection):
        _run_sync_migrations(connection)

    if getattr(connectable, "dialect", None) and connectable.dialect.is_async:
        async def _run_async():
            async with connectable.connect() as connection:
                await connection.run_sync(_run_sync_migrations)

        asyncio.run(_run_async())
    else:
        with connectable.connect() as connection:
            _run_with_connection(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
