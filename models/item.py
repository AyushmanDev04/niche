from db import db


class ItemModel(db.Model):
    __tablename__ = "items"
    __table_args__ = (
        # Item names are unique *within a store*, not globally. A global unique
        # constraint would stop two different stores both selling "Coffee".
        db.UniqueConstraint("store_id", "name", name="uq_item_store_name"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String)
    price = db.Column(db.Float(precision=2), nullable=False)
    image_url = db.Column(db.String(500), nullable=True)
    is_hidden = db.Column(db.Boolean, default=False, nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False)

    store = db.relationship("StoreModel", back_populates="items")
    tags = db.relationship("TagModel", back_populates="items", secondary="items_tags")
    reviews = db.relationship(
        "ReviewModel", back_populates="item", cascade="all, delete-orphan"
    )
    # orders.item_id is NOT NULL; without this cascade, deleting an item that
    # has ever been ordered raises a foreign key violation on Postgres.
    orders = db.relationship(
        "OrderModel", back_populates="item", cascade="all, delete-orphan"
    )
