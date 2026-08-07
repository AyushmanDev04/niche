"""empty message

Revision ID: cd185f0003d1
Revises: 5ddffaf4712d
Create Date: 2026-07-17 20:16:07.079508

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
        batch_op.create_unique_constraint('uq_items_name', ['name'])


def downgrade():
    with op.batch_alter_table('items', schema=None) as batch_op:
        batch_op.drop_constraint('uq_items_name', type_='unique')
        batch_op.drop_column('description')

