from datetime import datetime

from db import db
from order_lifecycle import OrderStatus


class OrderModel(db.Model):
    __tablename__ = "orders"
    __table_args__ = (
        db.UniqueConstraint("public_ref", name="uq_order_public_ref"),
    )

    id = db.Column(db.Integer, primary_key=True)
    public_ref = db.Column(db.String(20), nullable=True, index=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)

    unit_price = db.Column(db.Numeric(10, 2), nullable=True)

    status = db.Column(
        db.String(20), nullable=False, default=OrderStatus.PENDING
    )

    delivery_address = db.Column(db.String(300), nullable=True)
    contact_phone = db.Column(db.String(20), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user = db.relationship("UserModel", back_populates="orders")
    item = db.relationship("ItemModel", back_populates="orders")
    store = db.relationship("StoreModel", back_populates="orders")

    @property
    def reference(self):
        """Human-quotable order number for receipts and support requests."""
        return self.public_ref or f"ORD-LEGACY-{self.id:05d}"

    @property
    def total(self):
        """What the customer owes, from the snapshotted price."""
        if self.unit_price is None:
            return None
        return round(float(self.unit_price) * self.quantity, 2)
