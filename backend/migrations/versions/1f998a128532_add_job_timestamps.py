"""add job timestamps"""

from alembic import op
import sqlalchemy as sa



revision = '1f998a128532'
down_revision = 'xcyd9krp0vw3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "jobs",
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("jobs", "completed_at")
    op.drop_column("jobs", "started_at")
