"""Add CANCELLED value to jobstatus enum.

Revision ID: 521f6725e059
Revises: c3e0a5f6a9f1
Create Date: 2025-11-25

"""
from alembic import op


revision = "521f6725e059"
down_revision = "c3e0a5f6a9f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add CANCELLED value to the jobstatus enum for user-cancelled jobs."""

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE jobstatus ADD VALUE IF NOT EXISTS 'CANCELLED'")


def downgrade() -> None:
    """No downgrade available for enum value additions."""

    # Removing values from a PostgreSQL enum requires recreating the type,
    # which is intentionally omitted here.
    pass

