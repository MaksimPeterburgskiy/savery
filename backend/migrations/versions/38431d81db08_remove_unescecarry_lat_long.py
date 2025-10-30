"""remove unescecarry lat/long"""

from alembic import op
import sqlalchemy as sa
from geoalchemy2.types import Geography


revision = "38431d81db08"
down_revision = "6c2bd0f6a78d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration."""
    op.add_column(
        "route_plans",
        sa.Column(
            "user_geography",
            Geography(
                geometry_type="POINT",
                srid=4326,
                dimension=2,
                from_text="ST_GeogFromText",
                name="geography",
            ),
            nullable=True,
        ),
    )
    bind = op.get_bind()
    existing_indexes = {idx["name"] for idx in sa.inspect(bind).get_indexes("route_plans")}
    if "idx_route_plans_user_geography" not in existing_indexes:
        op.create_index(
            "idx_route_plans_user_geography",
            "route_plans",
            ["user_geography"],
            unique=False,
            postgresql_using="gist",
        )
    op.drop_column("route_plans", "user_latitude")
    op.drop_column("route_plans", "user_longitude")
    op.drop_column("stores", "longitude")
    op.drop_column("stores", "latitude")


def downgrade() -> None:
    """Rollback migration."""
    op.add_column(
        "stores",
        sa.Column(
            "latitude",
            sa.DOUBLE_PRECISION(precision=53),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "stores",
        sa.Column(
            "longitude",
            sa.DOUBLE_PRECISION(precision=53),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "route_plans",
        sa.Column(
            "user_longitude",
            sa.DOUBLE_PRECISION(precision=53),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "route_plans",
        sa.Column(
            "user_latitude",
            sa.DOUBLE_PRECISION(precision=53),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.drop_index("idx_route_plans_user_geography", table_name="route_plans")
    op.drop_column("route_plans", "user_geography")
