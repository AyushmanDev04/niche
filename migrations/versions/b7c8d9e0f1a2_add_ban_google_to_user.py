"""add is_banned and google_id to user, relax password column

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-07-19 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b7c8d9e0f1a2'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('is_banned', sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column('google_id', sa.String(length=255), nullable=True))
        batch_op.create_unique_constraint('uq_users_google_id', ['google_id'])
        batch_op.alter_column(
            'password', existing_type=sa.String(length=80), type_=sa.String(length=255),
            nullable=True,
        )


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column(
            'password', existing_type=sa.String(length=255), type_=sa.String(length=80),
            nullable=False,
        )
        batch_op.drop_constraint('uq_users_google_id', type_='unique')
        batch_op.drop_column('google_id')
        batch_op.drop_column('is_banned')