from db import db


class Role:
    """The two sides of the marketplace.

    A customer buys and reviews; a shopkeeper sells. The split is deliberate:
    a shopkeeper must not be able to review (they would be rating their own
    market), and a customer must not be able to sell.

    `is_admin` is a separate flag rather than a third role, because an admin
    moderates the platform rather than participating in it.
    """

    CUSTOMER = "customer"
    SHOPKEEPER = "shopkeeper"

    ALL = (CUSTOMER, SHOPKEEPER)


class UserModel(db.Model):
    __tablename__ = "users"
    __table_args__ = (
        db.UniqueConstraint("public_ref", name="uq_user_public_ref"),
    )

    id = db.Column(db.Integer, primary_key=True)
    public_ref = db.Column(db.String(20), nullable=True, index=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    role = db.Column(
        db.String(20), nullable=False, default=Role.CUSTOMER, server_default=Role.CUSTOMER
    )
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_banned = db.Column(db.Boolean, default=False, nullable=False)
    google_id = db.Column(db.String(255), unique=True, nullable=True)

    @property
    def is_shopkeeper(self):
        return self.role == Role.SHOPKEEPER or self.is_admin

    @property
    def is_customer(self):
        return self.role == Role.CUSTOMER

    stores = db.relationship("StoreModel", back_populates="owner")

    worked_stores = db.relationship(
        "StoreModel", secondary="store_workers", back_populates="workers"
    )

    reviews = db.relationship(
        "ReviewModel", back_populates="user", cascade="all, delete-orphan"
    )
    orders = db.relationship(
        "OrderModel", back_populates="user", cascade="all, delete-orphan"
    )

    activity_logs = db.relationship("ActivityLogModel", back_populates="user")

    profile = db.relationship(
        "UserProfileModel", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
