"""Define PostgreSQL replaceable entities managed by Alembic Utils."""

from __future__ import annotations

from typing import Iterable

try:
    from alembic_utils.replaceable_entity import ReplaceableEntity
except ModuleNotFoundError:  # pragma: no cover - library optional during install bootstrap
    ReplaceableEntity = object  # type: ignore[misc, assignment]


def iter_replaceable_entities() -> Iterable[ReplaceableEntity]:
    """Return replaceable entities (functions/views/triggers) to track.

    Populate this generator with instances from ``alembic_utils`` such as
    ``PGFunction`` or ``PGView``. Keeping the logic in a dedicated module avoids
    import-time side effects inside Alembic ``env.py`` while providing a single
    place to expand the DDL surface managed by migrations.
    """

    # Example placeholder:
    # yield PGFunction(
    #     schema="public",
    #     signature="to_upper(some_text text)",
    #     definition="""\
    #     RETURNS text AS $$
    #         SELECT upper(some_text)
    #     $$ LANGUAGE SQL;
    #     """,
    # )

    yield from ()
