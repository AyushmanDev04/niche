from flask_jwt_extended import get_jwt, get_jwt_identity
from flask_smorest import abort

from db import db
from models import Role, UserModel


def current_user():
    identity = get_jwt_identity()
    if identity is None:
        return None
    return db.session.get(UserModel, int(identity))


def current_role():
    """Read the role from the token rather than the database.

    Roles are assigned at registration and never change, so the claim cannot
    go stale, and this keeps permission checks off the hot path.
    """
    return get_jwt().get("role")


def is_admin():
    return bool(get_jwt().get("is_admin"))


def is_shopkeeper():
    return current_role() == Role.SHOPKEEPER or is_admin()


def is_customer():
    return current_role() == Role.CUSTOMER and not is_admin()


def require_shopkeeper():
    if not is_shopkeeper():
        abort(
            403,
            message="Only a shopkeeper account can sell. Register as a shopkeeper to open a store.",
        )


def require_customer():
    if not is_customer():
        abort(
            403,
            message="Only a customer account can do this. Shopkeeper accounts cannot review or place orders.",
        )


def can_manage_store(store):
    """Full control: create/edit/hide/delete items, delete the store itself,
    manage workers. True for a global admin or the store's owner."""
    if is_admin():
        return True
    return store.owner_id is not None and str(store.owner_id) == str(get_jwt_identity())


def can_work_store(store):
    """Limited control: add/edit/hide items, but NOT delete items or the
    store, and NOT manage workers. True for admin, the owner, or anyone
    listed as a worker of this store."""
    if can_manage_store(store):
        return True
    current_user_id = get_jwt_identity()
    return any(str(worker.id) == str(current_user_id) for worker in store.workers)
