"""restructure item matching schema

Revision ID: xcyd9krp0vw3
Revises: b58251b3cdf3
Create Date: 2025-11-04

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'xcyd9krp0vw3'
down_revision = 'b58251b3cdf3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add image_url to products table
    op.add_column('products', sa.Column('image_url', sa.String(), nullable=True))

    # Begin restructuring item_match_candidates
    op.drop_constraint('uq_item_match_candidates_match_rank', 'item_match_candidates', type_='unique')

    op.add_column('item_match_candidates', sa.Column('plan_id', sa.Uuid(), nullable=True))
    op.add_column('item_match_candidates', sa.Column('list_item_id', sa.Uuid(), nullable=True))

    op.execute(
        """
        UPDATE item_match_candidates imc
        SET plan_id = im.plan_id,
            list_item_id = im.list_item_id
        FROM item_matches im
        WHERE imc.item_match_id = im.id
        """
    )

    op.alter_column('item_match_candidates', 'plan_id', nullable=False)
    op.alter_column('item_match_candidates', 'list_item_id', nullable=False)

    op.create_index(op.f('ix_item_match_candidates_plan_id'), 'item_match_candidates', ['plan_id'], unique=False)
    op.create_index(op.f('ix_item_match_candidates_list_item_id'), 'item_match_candidates', ['list_item_id'], unique=False)
    op.create_foreign_key('item_match_candidates_plan_id_fkey', 'item_match_candidates', 'route_plans', ['plan_id'], ['id'])
    op.create_foreign_key('item_match_candidates_list_item_id_fkey', 'item_match_candidates', 'list_items', ['list_item_id'], ['id'])

    # Convert product linkage from store_products -> products
    op.drop_constraint('item_match_candidates_product_id_fkey', 'item_match_candidates', type_='foreignkey')
    op.execute(
        """
        UPDATE item_match_candidates imc
        SET product_id = sp.product_id
        FROM store_products sp
        WHERE imc.product_id = sp.id
        """
    )
    op.create_foreign_key('item_match_candidates_product_id_fkey', 'item_match_candidates', 'products', ['product_id'], ['id'])

    # Capture the product we will associate to each existing item_match
    op.execute(
        """
        CREATE TEMP TABLE tmp_match_product AS
        WITH candidate_choice AS (
            SELECT
                item_match_id,
                product_id,
                ROW_NUMBER() OVER (
                    PARTITION BY item_match_id
                    ORDER BY rank NULLS LAST, score DESC NULLS LAST, created_at, id
                ) AS rn
            FROM item_match_candidates
        )
        SELECT
            im.id AS match_id,
            im.plan_id,
            im.list_item_id,
            COALESCE(sp.product_id, candidate_choice.product_id) AS product_id
        FROM item_matches im
        LEFT JOIN store_products sp ON sp.id = im.chosen_product_id
        LEFT JOIN candidate_choice ON candidate_choice.item_match_id = im.id AND candidate_choice.rn = 1
        """
    )

    # Deduplicate candidates so only one row per plan/list/product remains
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY plan_id, list_item_id, product_id
                    ORDER BY rank NULLS LAST, score DESC NULLS LAST, created_at, id
                ) AS rn
            FROM item_match_candidates
        )
        DELETE FROM item_match_candidates imc
        USING ranked r
        WHERE imc.id = r.id
          AND r.rn > 1
        """
    )

    # Ensure a candidate exists for every match combination we captured
    op.execute(
        """
        INSERT INTO item_match_candidates (
            id,
            plan_id,
            list_item_id,
            product_id,
            score,
            rejected_by_user,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            tmp.plan_id,
            tmp.list_item_id,
            tmp.product_id,
            0.0,
            false,
            now(),
            now()
        FROM tmp_match_product tmp
        WHERE tmp.product_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM item_match_candidates existing
              WHERE existing.plan_id = tmp.plan_id
                AND existing.list_item_id = tmp.list_item_id
                AND existing.product_id = tmp.product_id
          )
        """
    )

    # Prepare item_matches for the new FK
    op.add_column('item_matches', sa.Column('item_match_candidate_id', sa.Uuid(), nullable=True))

    op.execute(
        """
        UPDATE item_matches im
        SET item_match_candidate_id = imc.id
        FROM tmp_match_product tmp
        JOIN item_match_candidates imc
          ON imc.plan_id = tmp.plan_id
         AND imc.list_item_id = tmp.list_item_id
         AND imc.product_id = tmp.product_id
        WHERE im.id = tmp.match_id
          AND tmp.product_id IS NOT NULL
        """
    )

    bind = op.get_bind()
    missing_products = bind.execute(sa.text('SELECT COUNT(*) FROM tmp_match_product WHERE product_id IS NULL')).scalar()
    if missing_products:
        raise RuntimeError(f"Cannot backfill item_match_candidate_id; {missing_products} item_matches have no product mapping")

    missing_candidates = bind.execute(sa.text('SELECT COUNT(*) FROM item_matches WHERE item_match_candidate_id IS NULL')).scalar()
    if missing_candidates:
        raise RuntimeError(f"Failed to backfill item_match_candidate_id for {missing_candidates} item_matches")

    op.execute('DROP TABLE tmp_match_product')

    # Drop legacy columns now that data has been migrated
    op.drop_constraint('item_match_candidates_item_match_id_fkey', 'item_match_candidates', type_='foreignkey')
    op.drop_index('ix_item_match_candidates_item_match_id', table_name='item_match_candidates')
    op.drop_column('item_match_candidates', 'item_match_id')

    op.drop_constraint('item_match_candidates_price_entry_id_fkey', 'item_match_candidates', type_='foreignkey')
    op.drop_index('ix_item_match_candidates_price_entry_id', table_name='item_match_candidates')
    op.drop_column('item_match_candidates', 'price_entry_id')

    op.drop_column('item_match_candidates', 'rank')

    op.create_unique_constraint('uq_item_match_candidates_plan_item_product', 'item_match_candidates', ['plan_id', 'list_item_id', 'product_id'])

    # Rename chosen_product_id -> store_product_id
    op.add_column('item_matches', sa.Column('store_product_id', sa.Uuid(), nullable=True))
    op.execute('UPDATE item_matches SET store_product_id = chosen_product_id')
    op.drop_constraint('item_matches_chosen_product_id_fkey', 'item_matches', type_='foreignkey')
    op.drop_index(op.f('ix_item_matches_chosen_product_id'), table_name='item_matches')
    op.create_index(op.f('ix_item_matches_store_product_id'), 'item_matches', ['store_product_id'], unique=False)
    op.create_foreign_key('item_matches_store_product_id_fkey', 'item_matches', 'store_products', ['store_product_id'], ['id'])
    op.drop_column('item_matches', 'chosen_product_id')

    # Rename chosen_price_entry_id -> price_entry_id
    op.add_column('item_matches', sa.Column('price_entry_id', sa.Uuid(), nullable=True))
    op.execute('UPDATE item_matches SET price_entry_id = chosen_price_entry_id')
    op.drop_constraint('item_matches_chosen_price_entry_id_fkey', 'item_matches', type_='foreignkey')
    op.drop_index(op.f('ix_item_matches_chosen_price_entry_id'), table_name='item_matches')
    op.create_index(op.f('ix_item_matches_price_entry_id'), 'item_matches', ['price_entry_id'], unique=False)
    op.create_foreign_key('item_matches_price_entry_id_fkey', 'item_matches', 'price_entries', ['price_entry_id'], ['id'])
    op.drop_column('item_matches', 'chosen_price_entry_id')

    # Drop status metadata that is no longer tracked
    op.drop_column('item_matches', 'status')
    op.drop_column('item_matches', 'notes')
    op.drop_column('item_matches', 'updated_by_user')

    op.alter_column('item_matches', 'item_match_candidate_id', nullable=False)
    op.create_index(op.f('ix_item_matches_item_match_candidate_id'), 'item_matches', ['item_match_candidate_id'], unique=False)
    op.create_foreign_key('item_matches_item_match_candidate_id_fkey', 'item_matches', 'item_match_candidates', ['item_match_candidate_id'], ['id'])


def downgrade() -> None:
    # Reverse item_matches changes
    op.drop_constraint('item_matches_item_match_candidate_id_fkey', 'item_matches', type_='foreignkey')
    op.drop_index(op.f('ix_item_matches_item_match_candidate_id'), table_name='item_matches')
    op.drop_column('item_matches', 'item_match_candidate_id')

    op.add_column('item_matches', sa.Column('updated_by_user', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=False))
    op.add_column('item_matches', sa.Column('notes', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.add_column('item_matches', sa.Column('status', sa.VARCHAR(), server_default=sa.text("'PENDING'"), autoincrement=False, nullable=False))

    # Reverse price_entry_id rename
    op.add_column('item_matches', sa.Column('chosen_price_entry_id', sa.UUID(), nullable=True))
    op.execute('UPDATE item_matches SET chosen_price_entry_id = price_entry_id')
    op.drop_constraint('item_matches_price_entry_id_fkey', 'item_matches', type_='foreignkey')
    op.drop_index(op.f('ix_item_matches_price_entry_id'), table_name='item_matches')
    op.create_index('ix_item_matches_chosen_price_entry_id', 'item_matches', ['chosen_price_entry_id'], unique=False)
    op.create_foreign_key('item_matches_chosen_price_entry_id_fkey', 'item_matches', 'price_entries', ['chosen_price_entry_id'], ['id'])
    op.drop_column('item_matches', 'price_entry_id')

    # Reverse store_product_id rename
    op.add_column('item_matches', sa.Column('chosen_product_id', sa.UUID(), nullable=True))
    op.execute('UPDATE item_matches SET chosen_product_id = store_product_id')
    op.drop_constraint('item_matches_store_product_id_fkey', 'item_matches', type_='foreignkey')
    op.drop_index(op.f('ix_item_matches_store_product_id'), table_name='item_matches')
    op.create_index('ix_item_matches_chosen_product_id', 'item_matches', ['chosen_product_id'], unique=False)
    op.create_foreign_key('item_matches_chosen_product_id_fkey', 'item_matches', 'store_products', ['chosen_product_id'], ['id'])
    op.drop_column('item_matches', 'store_product_id')

    # Reverse item_match_candidates changes
    op.drop_constraint('uq_item_match_candidates_plan_item_product', 'item_match_candidates', type_='unique')

    op.add_column('item_match_candidates', sa.Column('rank', sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('item_match_candidates', sa.Column('price_entry_id', sa.UUID(), autoincrement=False, nullable=True))
    op.add_column('item_match_candidates', sa.Column('item_match_id', sa.UUID(), autoincrement=False, nullable=True))

    # NOTE: Data migration would be needed here to populate item_match_id from plan_id/list_item_id/store_id

    op.create_index('ix_item_match_candidates_price_entry_id', 'item_match_candidates', ['price_entry_id'], unique=False)
    op.create_index('ix_item_match_candidates_item_match_id', 'item_match_candidates', ['item_match_id'], unique=False)
    op.create_foreign_key('item_match_candidates_price_entry_id_fkey', 'item_match_candidates', 'price_entries', ['price_entry_id'], ['id'])
    op.create_foreign_key('item_match_candidates_item_match_id_fkey', 'item_match_candidates', 'item_matches', ['item_match_id'], ['id'])

    # Reverse product_id FK change
    op.drop_constraint('item_match_candidates_product_id_fkey', 'item_match_candidates', type_='foreignkey')
    op.create_foreign_key('item_match_candidates_product_id_fkey', 'item_match_candidates', 'store_products', ['product_id'], ['id'])

    # Drop new columns
    op.drop_constraint('item_match_candidates_list_item_id_fkey', 'item_match_candidates', type_='foreignkey')
    op.drop_constraint('item_match_candidates_plan_id_fkey', 'item_match_candidates', type_='foreignkey')
    op.drop_index(op.f('ix_item_match_candidates_list_item_id'), table_name='item_match_candidates')
    op.drop_index(op.f('ix_item_match_candidates_plan_id'), table_name='item_match_candidates')
    op.drop_column('item_match_candidates', 'list_item_id')
    op.drop_column('item_match_candidates', 'plan_id')

    # Restore old unique constraint
    op.create_unique_constraint('uq_item_match_candidates_match_rank', 'item_match_candidates', ['item_match_id', 'rank'])

    # Remove image_url from products
    op.drop_column('products', 'image_url')
