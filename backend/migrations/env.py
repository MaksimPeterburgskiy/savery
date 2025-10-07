"""Alembic environment configuration wired to the Savery ORM models."""

from __future__ import annotations

from logging.config import fileConfig
from pathlib import Path
import sys

from alembic import context
from sqlalchemy import engine_from_config, pool

# Third-party helpers enabling richer autogenerate support.
try:  # pragma: no cover - optional dependency late in setup
    import alembic_postgresql_enum  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - triggered before dependency install
    alembic_postgresql_enum = None

try:  # pragma: no cover - optional dependency late in setup
    from alembic_utils.replaceable_entity import register_entities
except ModuleNotFoundError:  # pragma: no cover - triggered before dependency install
    register_entities = None


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.core.alembic_entities import iter_replaceable_entities  # noqa: E402
from backend.core.config import settings  # noqa: E402  (import after sys.path tweak)
from backend.core.schema import Base  # noqa: E402

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

config.set_main_option("sqlalchemy.url", settings.database_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata used for autogenerate.
target_metadata = Base.metadata

if register_entities is not None:
    register_entities(list(iter_replaceable_entities()))


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    configuration = config.get_section(config.config_ini_section, {}).copy()
    configuration["sqlalchemy.url"] = settings.database_url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
