"""Add items.description, scope item names to their store

Revision ID: cd185f0003d1
Revises: 5ddffaf4712d
Create Date: 2026-07-17 20:16:07.079508

This originally created a store-wide unique constraint on items.name, which
meant two shops could never both sell "Coffee". The model has always intended
uniqueness per store (see ItemModel.__table_args__), so the constraint is
created on (store_id, name) here.

Revision e5f6a7b8c9d0 later repaired this on databases that had already run
the store-wide version; its items work is now conditional, so migrating from
scratch and migrating an existing database both end at the same schema.
"""
from alembic import op
import sqlalchemy as sa


revision = 'cd185f0003d1'
down_revision = '5ddffaf4712d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('description', sa.String(), nullable=True))
        batch_op.create_unique_constraint('uq_item_store_name', ['store_id', 'name'])


def downgrade():
    with op.batch_alter_table('items', schema=None) as batch_op:
        batch_op.drop_constraint('uq_item_store_name', type_='unique')
        batch_op.drop_column('description')
