"""Allow multiple job records per stage while keeping only one active."""

from alembic import op
import sqlalchemy as sa


revision = "c3e0a5f6a9f1"
down_revision = "7a174e9b2a16"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop strict uniqueness across all job records for a plan/stage.
    op.drop_constraint("uq_jobs_plan_stage", "jobs", type_="unique")
    # Enforce uniqueness only for active jobs (PENDING/RUNNING).
    op.create_index(
        "ix_jobs_plan_stage_active",
        "jobs",
        ["plan_id", "stage"],
        unique=True,
        postgresql_where=sa.text("status IN ('PENDING', 'RUNNING')"),
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_plan_stage_active", table_name="jobs")
    op.create_unique_constraint(
        "uq_jobs_plan_stage",
        "jobs",
        ["plan_id", "stage"],
    )
