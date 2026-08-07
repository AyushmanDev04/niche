from db import db


class StoreModel(db.Model):
    __tablename__ = "stores"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    items = db.relationship(
        "ItemModel",
        back_populates="store",
        lazy="dynamic",
        cascade="all, delete, delete-orphan",
    )
    tags = db.relationship(
        "TagModel",
        back_populates="store",
        lazy="dynamic",
        cascade="all, delete, delete-orphan",
    )
    owner = db.relationship("UserModel", back_populates="stores")
    workers = db.relationship(
        "UserModel", secondary="store_workers", back_populates="worked_stores"
    )
    # orders.store_id is NOT NULL, so a store's orders must go with it.
    orders = db.relationship(
        "OrderModel", back_populates="store", cascade="all, delete-orphan"
    )
