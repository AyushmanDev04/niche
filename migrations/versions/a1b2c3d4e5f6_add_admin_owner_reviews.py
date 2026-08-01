"""add is_admin, store owner_id, and reviews table

Revision ID: a1b2c3d4e5f6
Revises: cd185f0003d1
Create Date: 2026-07-19 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = 'cd185f0003d1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('is_admin', sa.Boolean(), nullable=False, server_default=sa.false())
        )

    with op.batch_alter_table('stores', schema=None) as batch_op:
        batch_op.add_column(sa.Column('owner_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_stores_owner_id_users', 'users', ['owner_id'], ['id']
        )

    op.create_table(
        'reviews',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('comment', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('item_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['item_id'], ['items.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('reviews')

    with op.batch_alter_table('stores', schema=None) as batch_op:
        batch_op.drop_constraint('fk_stores_owner_id_users', type_='foreignkey')
        batch_op.drop_column('owner_id')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('is_admin')