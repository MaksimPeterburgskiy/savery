"""Add HEALTHCHECK value to jobstage enum."""

from alembic import op


revision = "b6a2f84e2d92"
down_revision = "70140a24605c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Ensure the jobstage enum includes the HEALTHCHECK value."""

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE jobstage ADD VALUE IF NOT EXISTS 'HEALTHCHECK'")


def downgrade() -> None:
    """No downgrade available for enum value additions."""

    # Removing values from a PostgreSQL enum requires recreating the type,
    # which is intentionally omitted here.
    pass
