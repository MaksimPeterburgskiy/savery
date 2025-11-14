"""Allow multiple item matches per store per list item."""

from alembic import op

# revision identifiers, used by Alembic.
revision = "d2e8e7b8da2e"
down_revision = "47337c4ecdae"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_item_matches_plan_item_store", "item_matches", type_="unique")
    op.create_unique_constraint(
        "uq_item_matches_plan_item_store_candidate",
        "item_matches",
        ["plan_id", "list_item_id", "store_id", "item_match_candidate_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_item_matches_plan_item_store_candidate", "item_matches", type_="unique")
    op.create_unique_constraint(
        "uq_item_matches_plan_item_store",
        "item_matches",
        ["plan_id", "list_item_id", "store_id"],
    )
