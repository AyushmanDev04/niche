from db import db


class UserModel(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_banned = db.Column(db.Boolean, default=False, nullable=False)
    google_id = db.Column(db.String(255), unique=True, nullable=True)

    # Stores this user owns.
    stores = db.relationship("StoreModel", back_populates="owner")

    # Stores this user works at (as a worker, not owner).
    worked_stores = db.relationship(
        "StoreModel", secondary="store_workers", back_populates="workers"
    )