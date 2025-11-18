"""Add FANOUT value to jobstage enum."""

from alembic import op


revision = "47337c4ecdae"
down_revision = "1f998a128532"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Ensure the jobstage enum includes the FANOUT value."""

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE jobstage ADD VALUE IF NOT EXISTS 'FANOUT'")


def downgrade() -> None:
    """No downgrade available for enum value additions."""

    # Removing values from a PostgreSQL enum requires recreating the type,
    # which is intentionally omitted here.
    pass
