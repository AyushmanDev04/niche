from flask_jwt_extended import get_jwt, get_jwt_identity


def can_manage_store(store):
    """Full control: create/edit/hide/delete items, delete the store itself,
    manage workers. True for a global admin or the store's owner."""
    jwt = get_jwt()
    if jwt.get("is_admin"):
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