"""rename client token"""

from alembic import op


revision = "afbbd84dbbe3"
down_revision = "b6a2f84e2d92"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index(op.f("ix_route_plans_client_token"), table_name="route_plans")
    op.alter_column("route_plans", "client_token", new_column_name="client_id")
    op.create_index(
        op.f("ix_route_plans_client_id"),
        "route_plans",
        ["client_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_route_plans_client_id"), table_name="route_plans")
    op.alter_column("route_plans", "client_id", new_column_name="client_token")
    op.create_index(
        op.f("ix_route_plans_client_token"),
        "route_plans",
        ["client_token"],
        unique=False,
    )
