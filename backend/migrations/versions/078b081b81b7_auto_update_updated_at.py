"""auto update updated_at"""

from alembic import op


revision = "078b081b81b7"
down_revision = "be33456893b7"
branch_labels = None
depends_on = None

TABLES_WITH_UPDATED_AT = (
    "products",
    "shopping_lists",
    "store_chains",
    "list_items",
    "route_plans",
    "stores",
    "jobs",
    "plan_selected_stores",
    "plan_store_visits",
    "store_products",
    "price_entries",
    "item_matches",
    "plan_items",
    "item_match_candidates",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS trigger AS $$
        BEGIN
            NEW.updated_at = (CURRENT_TIMESTAMP AT TIME ZONE 'UTC');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    for table in TABLES_WITH_UPDATED_AT:
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_set_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
            """
        )


def downgrade() -> None:
    for table in TABLES_WITH_UPDATED_AT:
        op.execute(
            f"""
            DROP TRIGGER IF EXISTS trg_{table}_set_updated_at ON {table};
            """
        )

    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")
