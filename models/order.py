from datetime import datetime

from db import db


class OrderModel(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)

    # The price of one unit *at the moment the order was placed*.
    #
    # Without this, an order's total was derived from items.price, so a
    # shopkeeper editing a price silently rewrote the value of every past
    # order. An order is a financial record and must not move.
    #
    # Numeric rather than Float because this is money: binary floats cannot
    # represent 0.10 exactly and the error compounds across a total.
    unit_price = db.Column(db.Numeric(10, 2), nullable=True)

    # pending -> fulfilled, or pending -> cancelled
    status = db.Column(db.String(20), nullable=False, default="pending")

    # Where the shop should deliver. Central to the local-delivery model: the
    # shopkeeper needs an address and a number to actually fulfil the order.
    delivery_address = db.Column(db.String(300), nullable=True)
    contact_phone = db.Column(db.String(20), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("UserModel", back_populates="orders")
    item = db.relationship("ItemModel", back_populates="orders")
    store = db.relationship("StoreModel", back_populates="orders")

    @property
    def reference(self):
        """Human-quotable order number for receipts and support requests."""
        return f"ORD-{self.id:05d}"

    @property
    def total(self):
        """What the customer owes, from the snapshotted price."""
        if self.unit_price is None:
            return None
        return round(float(self.unit_price) * self.quantity, 2)
