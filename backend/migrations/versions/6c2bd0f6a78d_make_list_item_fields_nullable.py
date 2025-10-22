"""Allow nullable optional list item attributes."""

from alembic import op
import sqlalchemy as sa


revision = "6c2bd0f6a78d"
down_revision = "078b081b81b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Relax list_items columns to accept NULL values."""

    op.alter_column("list_items", "raw_text_qty", existing_type=sa.String(), nullable=True)
    op.alter_column("list_items", "raw_text_item", existing_type=sa.String(), nullable=True)
    op.alter_column("list_items", "item_name", existing_type=sa.String(), nullable=True)
    op.alter_column("list_items", "qty_value", existing_type=sa.Float(), nullable=True)
    op.alter_column("list_items", "qty_unit", existing_type=sa.String(), nullable=True)
    op.alter_column("list_items", "norm_qty_value", existing_type=sa.Float(), nullable=True)
    op.alter_column("list_items", "norm_qty_unit", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    """Revert list_items columns to NOT NULL."""

    op.alter_column("list_items", "norm_qty_unit", existing_type=sa.String(), nullable=False)
    op.alter_column("list_items", "norm_qty_value", existing_type=sa.Float(), nullable=False)
    op.alter_column("list_items", "qty_unit", existing_type=sa.String(), nullable=False)
    op.alter_column("list_items", "qty_value", existing_type=sa.Float(), nullable=False)
    op.alter_column("list_items", "item_name", existing_type=sa.String(), nullable=False)
    op.alter_column("list_items", "raw_text_item", existing_type=sa.String(), nullable=False)
    op.alter_column("list_items", "raw_text_qty", existing_type=sa.String(), nullable=False)
