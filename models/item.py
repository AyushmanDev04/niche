from db import db


class ItemModel(db.Model):
    __tablename__ = "items"
    __table_args__ = (
        db.UniqueConstraint("store_id", "name", name="uq_item_store_name"),
        db.CheckConstraint("stock_quantity IS NULL OR stock_quantity >= 0", name="ck_item_stock_nonneg"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    image_url = db.Column(db.String(500), nullable=True)
    is_hidden = db.Column(db.Boolean, default=False, nullable=False)

    stock_quantity = db.Column(db.Integer, nullable=True)

    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False)

    store = db.relationship("StoreModel", back_populates="items")
    tags = db.relationship("TagModel", back_populates="items", secondary="items_tags")
    reviews = db.relationship(
        "ReviewModel", back_populates="item", cascade="all, delete-orphan"
    )
    orders = db.relationship(
        "OrderModel", back_populates="item", cascade="all, delete-orphan"
    )
