"""Scope item/tag names per store, one review per user per item, token blocklist

Revision ID: e5f6a7b8c9d0
Revises: d1e2f3a4b5c6
Create Date: 2026-08-07

Three changes:

1. items.name and tags.name were globally unique, so two stores could never
   both sell "Coffee" or both own a "sale" tag. Uniqueness is now scoped to
   (store_id, name).
2. reviews gains a (user_id, item_id) unique constraint so one account cannot
   post unlimited reviews of the same item.
3. token_blocklist replaces the in-memory revoked-token set, which did not work
   across gunicorn workers or survive a restart.

The unique constraints being dropped were created under different names
depending on how the database was built: Alembic named some of them, while
`db.create_all()` left them unnamed (SQLite) or auto-named `<table>_<col>_key`
(PostgreSQL). Rather than guess, this migration inspects the live schema and
drops whichever single-column unique constraint or index actually exists.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "e5f6a7b8c9d0"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


NAMING_CONVENTION = {
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ix": "ix_%(table_name)s_%(column_0_name)s",
}


def _single_column_unique_names(table, column):
    """Every unique constraint/index on exactly `column`, by name."""
    inspector = inspect(op.get_bind())
    names = []

    for constraint in inspector.get_unique_constraints(table):
        if list(constraint.get("column_names") or []) == [column]:
            names.append(constraint.get("name"))

    for index in inspector.get_indexes(table):
        if index.get("unique") and list(index.get("column_names") or []) == [column]:
            name = index.get("name")
            if name and name not in names:
                names.append(name)

    return names


def _drop_column_unique(table, column):
    names = _single_column_unique_names(table, column)

    with op.batch_alter_table(table, naming_convention=NAMING_CONVENTION) as batch_op:
        if not names:
            batch_op.drop_constraint(f"uq_{table}_{column}", type_="unique")
            return
        for name in names:
            if name is None:
                batch_op.drop_constraint(f"uq_{table}_{column}", type_="unique")
            else:
                batch_op.drop_constraint(name, type_="unique")


def upgrade():
    if "image_url" not in {
        column["name"] for column in inspect(op.get_bind()).get_columns("items")
    }:
        with op.batch_alter_table("items") as batch_op:
            batch_op.add_column(sa.Column("image_url", sa.String(length=500), nullable=True))

    _drop_column_unique("items", "name")
    with op.batch_alter_table("items") as batch_op:
        batch_op.create_unique_constraint("uq_item_store_name", ["store_id", "name"])

    _drop_column_unique("tags", "name")
    with op.batch_alter_table("tags") as batch_op:
        batch_op.create_unique_constraint("uq_tag_store_name", ["store_id", "name"])

    with op.batch_alter_table("reviews") as batch_op:
        batch_op.create_unique_constraint("uq_review_user_item", ["user_id", "item_id"])

    op.create_table(
        "token_blocklist",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("jti", sa.String(length=36), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("jti", name="uq_token_blocklist_jti"),
    )
    with op.batch_alter_table("token_blocklist") as batch_op:
        batch_op.create_index("ix_token_blocklist_jti", ["jti"], unique=True)


def downgrade():
    with op.batch_alter_table("token_blocklist") as batch_op:
        batch_op.drop_index("ix_token_blocklist_jti")
    op.drop_table("token_blocklist")

    with op.batch_alter_table("reviews") as batch_op:
        batch_op.drop_constraint("uq_review_user_item", type_="unique")

    with op.batch_alter_table("tags") as batch_op:
        batch_op.drop_constraint("uq_tag_store_name", type_="unique")
        batch_op.create_unique_constraint("uq_tags_name", ["name"])

    with op.batch_alter_table("items") as batch_op:
        batch_op.drop_constraint("uq_item_store_name", type_="unique")
        batch_op.create_unique_constraint("uq_items_name", ["name"])
