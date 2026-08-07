from datetime import datetime
from db import db


class TokenBlocklistModel(db.Model):
    """Revoked JWTs.

    This lives in the database rather than in a Python set because gunicorn
    runs several worker processes: an in-memory set would only revoke a token
    in whichever worker happened to serve the logout request, and would be
    wiped entirely on restart. Both make logout silently ineffective.
    """

    __tablename__ = "token_blocklist"

    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(36), nullable=False, unique=True, index=True)
    # When the underlying token would have expired anyway. Rows past this point
    # are dead weight and can be pruned.
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
