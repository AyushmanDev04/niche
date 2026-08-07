"""Stock tracking, order lifecycle vocabulary, opaque public references

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-08-07

Four independent changes, bundled because they ship together:

1. items.stock_quantity — nothing tracked remaining inventory before this, so
   there was no concept of "sold out" to enforce. NULL means "not tracked"
   (existing items keep selling as before); a shopkeeper opts an item into
   tracking by setting a number.

2. orders.status vocabulary grows from {pending, fulfilled, cancelled} to the
   full lifecycle in order_lifecycle.py. Existing 'fulfilled' rows become
   'completed' — the terminal "customer received it" state under the old
   two-step model maps onto the terminal state of the new five-step one.

3+4. orders.public_ref / users.public_ref — opaque, randomly generated
   reference codes (see references.py for why these are NOT a hash of the
   row's id). Backfilled here with a Python loop rather than a SQL UPDATE,
   because each row needs its own independent random value — something SQL's
   set-based UPDATE can't produce per-row without a database extension this
   migration shouldn't assume is installed.

5. orders.updated_at — tracks when an order last changed state, now that
   there are five states to move through instead of two.
"""

import secrets

from alembic import op
import sqlalchemy as sa
from sqlalchemy import table, column, select


revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def _backfill_refs(table_name, prefix):
    bind = op.get_bind()
    t = table(table_name, column("id", sa.Integer), column("public_ref", sa.String))
    rows = bind.execute(select(t.c.id)).fetchall()

    seen = set()
    for (row_id,) in rows:
        while True:
            token = f"{prefix}-{secrets.token_hex(4).upper()}"
            if token not in seen:
                seen.add(token)
                break
        bind.execute(t.update().where(t.c.id == row_id).values(public_ref=token))


def upgrade():
    with op.batch_alter_table("items") as batch_op:
        batch_op.add_column(sa.Column("stock_quantity", sa.Integer(), nullable=True))
        batch_op.create_check_constraint(
            "ck_item_stock_nonneg", "stock_quantity IS NULL OR stock_quantity >= 0"
        )

    op.execute("UPDATE orders SET status = 'completed' WHERE status = 'fulfilled'")

    with op.batch_alter_table("orders") as batch_op:
        batch_op.add_column(sa.Column("public_ref", sa.String(length=20), nullable=True))
    _backfill_refs("orders", "ORD")
    with op.batch_alter_table("orders") as batch_op:
        batch_op.create_index("ix_orders_public_ref", ["public_ref"])
        batch_op.create_unique_constraint("uq_order_public_ref", ["public_ref"])

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("public_ref", sa.String(length=20), nullable=True))
    _backfill_refs("users", "CUST")
    with op.batch_alter_table("users") as batch_op:
        batch_op.create_index("ix_users_public_ref", ["public_ref"])
        batch_op.create_unique_constraint("uq_user_public_ref", ["public_ref"])

    with op.batch_alter_table("orders") as batch_op:
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.execute("UPDATE orders SET updated_at = created_at WHERE updated_at IS NULL")
    with op.batch_alter_table("orders") as batch_op:
        batch_op.alter_column("updated_at", nullable=False)


def downgrade():
    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_column("updated_at")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("uq_user_public_ref", type_="unique")
        batch_op.drop_index("ix_users_public_ref")
        batch_op.drop_column("public_ref")

    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_constraint("uq_order_public_ref", type_="unique")
        batch_op.drop_index("ix_orders_public_ref")
        batch_op.drop_column("public_ref")

    op.execute("UPDATE orders SET status = 'fulfilled' WHERE status = 'completed'")

    with op.batch_alter_table("items") as batch_op:
        batch_op.drop_constraint("ck_item_stock_nonneg", type_="check")
        batch_op.drop_column("stock_quantity")
