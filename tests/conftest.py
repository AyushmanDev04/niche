import os
import tempfile

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret")
os.environ.setdefault("SECRET_KEY", "test-secret")


@pytest.fixture()
def app():
    """A fresh application against a throwaway database.

    Defaults to SQLite. Set TEST_DATABASE_URL to a PostgreSQL URL to run the
    same suite where foreign keys are actually enforced — several of these
    tests cover bugs (cascading deletes in particular) that SQLite cannot
    reproduce, because it does not enforce foreign keys by default.
    """
    external_url = os.environ.get("TEST_DATABASE_URL")
    path = None

    if external_url:
        os.environ["DATABASE_URL"] = external_url
    else:
        handle, path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        os.environ["DATABASE_URL"] = f"sqlite:///{path}"

    from app import create_app
    from db import db
    from rate_limit import limiter

    application = create_app()
    limiter.enabled = False

    with application.app_context():
        if external_url:
            db.drop_all()
        db.create_all()

    yield application

    if external_url:
        with application.app_context():
            db.session.remove()
            db.drop_all()
    else:
        os.unlink(path)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def delivered_buyer(client, auth):
    """A customer who has actually received `item`, and so may review it.

    POST /item/<id>/review requires a completed order for the item, so every
    review test needs a buyer who has been walked through the whole lifecycle
    rather than one who merely registered. `owner_headers` is the shop side —
    only staff can advance an order past pending.
    """

    def _make(item, username, owner_headers, quantity=1, role="customer"):
        headers, user_id, tokens = auth(username, role=role)

        order = client.post(
            f"/item/{item['id']}/order",
            json={"quantity": quantity},
            headers=headers,
        )
        assert order.status_code == 201, order.get_json()
        order_id = order.get_json()["id"]

        for status in ("accepted", "packed", "out_for_delivery", "completed"):
            moved = client.post(
                f"/order/{order_id}/transition",
                json={"status": status},
                headers=owner_headers,
            )
            assert moved.status_code == 200, moved.get_json()

        return headers, user_id, tokens

    return _make


@pytest.fixture()
def auth(client):
    """Register + log in a user, returning (headers, user_id, tokens).

    `role` is "customer" or "shopkeeper" — the two sides of the marketplace.
    """

    def _make(username, password="pw123456", admin=False, role="customer"):
        client.post(
            "/register",
            json={"username": username, "password": password, "role": role},
        )

        if admin:
            from db import db
            from models import UserModel

            with client.application.app_context():
                user = UserModel.query.filter_by(username=username).first()
                user.is_admin = True
                db.session.commit()

        tokens = client.post(
            "/login", json={"username": username, "password": password}
        ).get_json()

        from db import db
        from models import UserModel

        with client.application.app_context():
            user_id = UserModel.query.filter_by(username=username).first().id

        return (
            {"Authorization": f"Bearer {tokens['access_token']}"},
            user_id,
            tokens,
        )

    return _make
