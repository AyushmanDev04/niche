"""Add customer/shopkeeper role to users

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-08-07

Splits accounts into the two sides of the marketplace. The column is NOT NULL,
so existing rows are backfilled rather than defaulted blindly: anyone who owns
a store or works one is clearly a seller and becomes a shopkeeper; everyone
else becomes a customer.
"""

from alembic import op
import sqlalchemy as sa


revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column(
                "role",
                sa.String(length=20),
                nullable=False,
                server_default="customer",
            )
        )

    # Backfill from behaviour already recorded in the data: if an account owns
    # a store or is listed as a worker, it was being used as a seller.
    op.execute(
        """
        UPDATE users SET role = 'shopkeeper'
        WHERE id IN (SELECT owner_id FROM stores WHERE owner_id IS NOT NULL)
           OR id IN (SELECT user_id FROM store_workers)
        """
    )


def downgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("role")
