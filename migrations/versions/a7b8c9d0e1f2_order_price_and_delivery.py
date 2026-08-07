"""Snapshot order price, add delivery address and contact phone

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-08-07

Orders previously stored only a quantity, so any total had to be recomputed
from items.price. That made order history retroactive: editing an item's price
rewrote the value of every order ever placed for it. unit_price freezes the
price at the moment of purchase.

delivery_address and contact_phone are what a local shop actually needs to
fulfil an order.

Existing rows are backfilled from the item's current price. That is not the
true historical price, but it is the closest available estimate and is better
than leaving totals blank; rows where the item has since been deleted stay
NULL and render as "unavailable" rather than as zero.
"""

from alembic import op
import sqlalchemy as sa


revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("orders") as batch_op:
        batch_op.add_column(sa.Column("unit_price", sa.Numeric(10, 2), nullable=True))
        batch_op.add_column(sa.Column("delivery_address", sa.String(length=300), nullable=True))
        batch_op.add_column(sa.Column("contact_phone", sa.String(length=20), nullable=True))

    op.execute(
        """
        UPDATE orders
        SET unit_price = items.price
        FROM items
        WHERE orders.item_id = items.id
          AND orders.unit_price IS NULL
        """
    )


def downgrade():
    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_column("contact_phone")
        batch_op.drop_column("delivery_address")
        batch_op.drop_column("unit_price")
