from flask_jwt_extended import get_jwt_identity
from db import db
from models import ActivityLogModel, UserModel


def log_activity(action, details=None, user_id=None):
    """Record an activity log entry. If user_id isn't given, uses the
    current JWT identity (works for any endpoint behind @jwt_required)."""
    if user_id is None:
        try:
            user_id = get_jwt_identity()
        except RuntimeError:
            user_id = None

    username = None
    if user_id is not None:
        user_id = int(user_id)
        user = db.session.get(UserModel, user_id)
        if user:
            username = user.username

    entry = ActivityLogModel(
        user_id=user_id, username=username, action=action, details=details
    )
    db.session.add(entry)
    # Caller is expected to db.session.commit() as part of its own
    # transaction; we don't commit here to avoid partial-write issues.