from db import db


class TagModel(db.Model):
    __tablename__ = "tags"
    __table_args__ = (
        db.UniqueConstraint("store_id", "name", name="uq_tag_store_name"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False)

    store = db.relationship("StoreModel", back_populates="tags")
    items = db.relationship("ItemModel", back_populates="tags", secondary="items_tags")
