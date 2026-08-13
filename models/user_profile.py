from db import db
from timeutils import utcnow


class UserProfileModel(db.Model):
    """Delivery details, server-side.

    This used to live only in the browser's localStorage. That's not a
    security fix by itself — localStorage is only readable by script running
    on the same origin, same as any form field would be — but it meant the
    address didn't sync across devices, disappeared if the browser's storage
    was cleared, and couldn't be prefilled server-side (e.g. in a future
    admin or support view). One row per user; kept as its own table rather
    than columns on UserModel so profile completeness is optional without
    nullable-column sprawl on the account row itself.

    Note what this table is NOT for: individual orders keep their own copy of
    the address and phone at the time they were placed (see OrderModel).
    Editing a saved profile must never rewrite a past order's delivery
    details — this table only supplies the *default* the checkout form
    prefills from.
    """

    __tablename__ = "user_profiles"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)

    address_line1 = db.Column(db.String(150), nullable=True)
    address_line2 = db.Column(db.String(150), nullable=True)
    city = db.Column(db.String(80), nullable=True)
    state = db.Column(db.String(80), nullable=True)
    pincode = db.Column(db.String(10), nullable=True)
    phone = db.Column(db.String(20), nullable=True)

    updated_at = db.Column(
        db.DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    user = db.relationship("UserModel", back_populates="profile")

    @property
    def formatted_address(self):
        """Single-line rendering for order snapshots and display."""
        parts = [self.address_line1, self.address_line2, self.city, self.state, self.pincode]
        return ", ".join(p for p in parts if p)

    @property
    def is_complete(self):
        return bool(self.address_line1 and self.city and self.pincode and self.phone)
