from datetime import datetime
from db import db


class ActivityLogModel(db.Model):
    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    # Snapshot of the username at the time of the action, so the log stays
    # readable even if the user account is later deleted.
    username = db.Column(db.String(80), nullable=True)
    action = db.Column(db.String(80), nullable=False)
    details = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("UserModel", back_populates="activity_logs")
