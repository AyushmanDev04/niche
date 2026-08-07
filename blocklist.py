"""Revoked-token helpers.

Previously this module was a bare `set()`. That looked fine in development
(one process, one worker) but meant logout did nothing in production: gunicorn
runs multiple workers, so revoking a token in one worker left every other
worker still accepting it, and a restart cleared the set entirely.
"""

from db import db
from models import TokenBlocklistModel
from timeutils import utc_from_timestamp, utcnow


def add_to_blocklist(jwt_payload):
    """Revoke the token described by `jwt_payload`.

    Does not commit — the caller owns the transaction, matching how the rest
    of the codebase handles writes.
    """
    jti = jwt_payload.get("jti")
    if not jti:
        return

    exp = jwt_payload.get("exp")
    expires_at = utc_from_timestamp(exp) if exp else None

    if db.session.query(
        TokenBlocklistModel.query.filter_by(jti=jti).exists()
    ).scalar():
        return

    db.session.add(TokenBlocklistModel(jti=jti, expires_at=expires_at))


def is_revoked(jti):
    if not jti:
        return False
    return db.session.query(
        TokenBlocklistModel.query.filter_by(jti=jti).exists()
    ).scalar()


def prune_expired():
    """Delete blocklist rows whose tokens have expired on their own.

    Safe to call periodically; revoking an already-expired token is redundant
    because the signature check rejects it first.
    """
    deleted = (
        TokenBlocklistModel.query.filter(
            TokenBlocklistModel.expires_at.isnot(None),
            TokenBlocklistModel.expires_at < utcnow(),
        ).delete(synchronize_session=False)
    )
    return deleted
