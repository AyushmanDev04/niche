"""items.price: Float -> Numeric(10, 2)

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-08-08

Prices were stored as binary floating point, which cannot represent most
decimal money values exactly: 0.10 is really 0.1000000000000000055..., and
the error compounds once a price is multiplied by a quantity. orders.unit_price
was already Numeric(10, 2) (revision a7b8c9d0e1f2) precisely for this reason,
so the item that a price is snapshotted *from* was the last float left in the
money path.

Existing rows are rounded to 2 decimal places by the cast, which is the value
they were always displayed and charged as.
"""

from alembic import op
import sqlalchemy as sa


revision = "e1f2a3b4c5d6"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("items") as batch_op:
        batch_op.alter_column(
            "price",
            existing_type=sa.Float(precision=2),
            type_=sa.Numeric(10, 2),
            existing_nullable=False,
            postgresql_using="price::numeric(10,2)",
        )


def downgrade():
    with op.batch_alter_table("items") as batch_op:
        batch_op.alter_column(
            "price",
            existing_type=sa.Numeric(10, 2),
            type_=sa.Float(precision=2),
            existing_nullable=False,
            postgresql_using="price::double precision",
        )
