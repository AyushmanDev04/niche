"""Custom Flask CLI commands.

The admin bootstrap used to run inside create_app(), which meant it executed
once per gunicorn worker on every boot — several workers racing to insert the
same row, and a write to the database on every restart. It belongs in an
explicit deploy step instead:

    flask db upgrade && flask bootstrap-admin
"""

import os

import click
from flask.cli import with_appcontext
from passlib.hash import pbkdf2_sha256

from db import db
from models import UserModel, Role
from blocklist import prune_expired


def register_cli(app):
    app.cli.add_command(bootstrap_admin)
    app.cli.add_command(prune_tokens)


@click.command("bootstrap-admin")
@with_appcontext
def bootstrap_admin():
    """Create or promote the admin account from ADMIN_USERNAME/ADMIN_PASSWORD."""
    username = os.getenv("ADMIN_USERNAME")
    password = os.getenv("ADMIN_PASSWORD")

    if not username or not password:
        click.echo("ADMIN_USERNAME/ADMIN_PASSWORD not set; nothing to do.")
        return

    existing = UserModel.query.filter_by(username=username).first()
    if existing:
        if not existing.is_admin:
            existing.is_admin = True
            db.session.commit()
            click.echo(f"Promoted existing user '{username}' to admin.")
        else:
            click.echo(f"User '{username}' is already an admin.")
        return

    db.session.add(
        UserModel(
            username=username,
            password=pbkdf2_sha256.hash(password),
            is_admin=True,
            role=Role.SHOPKEEPER,
        )
    )
    db.session.commit()
    click.echo(f"Created admin user '{username}'.")


@click.command("prune-tokens")
@with_appcontext
def prune_tokens():
    """Delete revoked-token rows whose tokens have expired anyway."""
    count = prune_expired()
    db.session.commit()
    click.echo(f"Pruned {count} expired blocklist entries.")
