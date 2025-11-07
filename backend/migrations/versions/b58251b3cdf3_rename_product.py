"""rename product"""

from alembic import op
import sqlalchemy as sa



revision = 'b58251b3cdf3'
down_revision = 'afbbd84dbbe3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename item_match_candidates.store_product_id -> product_id
    op.add_column('item_match_candidates', sa.Column('product_id', sa.Uuid(), nullable=True))
    op.execute('UPDATE item_match_candidates SET product_id = store_product_id')
    op.alter_column('item_match_candidates', 'product_id', nullable=False)
    op.drop_constraint('item_match_candidates_store_product_id_fkey', 'item_match_candidates', type_='foreignkey')
    op.drop_index('ix_item_match_candidates_store_product_id', table_name='item_match_candidates')
    op.create_index(op.f('ix_item_match_candidates_product_id'), 'item_match_candidates', ['product_id'], unique=False)
    op.create_foreign_key('item_match_candidates_product_id_fkey', 'item_match_candidates', 'store_products', ['product_id'], ['id'])
    op.drop_column('item_match_candidates', 'store_product_id')

    # Rename item_matches.chosen_store_product_id -> chosen_product_id
    op.add_column('item_matches', sa.Column('chosen_product_id', sa.Uuid(), nullable=True))
    op.execute('UPDATE item_matches SET chosen_product_id = chosen_store_product_id')
    op.drop_constraint('item_matches_chosen_store_product_id_fkey', 'item_matches', type_='foreignkey')
    op.drop_index('ix_item_matches_chosen_store_product_id', table_name='item_matches')
    op.create_index(op.f('ix_item_matches_chosen_product_id'), 'item_matches', ['chosen_product_id'], unique=False)
    op.create_foreign_key('item_matches_chosen_product_id_fkey', 'item_matches', 'store_products', ['chosen_product_id'], ['id'])
    op.drop_column('item_matches', 'chosen_store_product_id')


def downgrade() -> None:
    # Rename item_matches.chosen_product_id -> chosen_store_product_id
    op.add_column('item_matches', sa.Column('chosen_store_product_id', sa.UUID(), nullable=True))
    op.execute('UPDATE item_matches SET chosen_store_product_id = chosen_product_id')
    op.drop_constraint('item_matches_chosen_product_id_fkey', 'item_matches', type_='foreignkey')
    op.drop_index(op.f('ix_item_matches_chosen_product_id'), table_name='item_matches')
    op.create_index('ix_item_matches_chosen_store_product_id', 'item_matches', ['chosen_store_product_id'], unique=False)
    op.create_foreign_key('item_matches_chosen_store_product_id_fkey', 'item_matches', 'store_products', ['chosen_store_product_id'], ['id'])
    op.drop_column('item_matches', 'chosen_product_id')

    # Rename item_match_candidates.product_id -> store_product_id
    op.add_column('item_match_candidates', sa.Column('store_product_id', sa.UUID(), nullable=True))
    op.execute('UPDATE item_match_candidates SET store_product_id = product_id')
    op.alter_column('item_match_candidates', 'store_product_id', nullable=False)
    op.drop_constraint('item_match_candidates_product_id_fkey', 'item_match_candidates', type_='foreignkey')
    op.drop_index(op.f('ix_item_match_candidates_product_id'), table_name='item_match_candidates')
    op.create_index('ix_item_match_candidates_store_product_id', 'item_match_candidates', ['store_product_id'], unique=False)
    op.create_foreign_key('item_match_candidates_store_product_id_fkey', 'item_match_candidates', 'store_products', ['store_product_id'], ['id'])
    op.drop_column('item_match_candidates', 'product_id')
