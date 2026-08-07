from db import db


class TagModel(db.Model):
    __tablename__ = "tags"
    __table_args__ = (
        # Tag names are unique per store, not globally — otherwise the first
        # store to create a "sale" tag blocks every other store from having one.
        db.UniqueConstraint("store_id", "name", name="uq_tag_store_name"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False)

    store = db.relationship("StoreModel", back_populates="tags")
    items = db.relationship("ItemModel", back_populates="tags", secondary="items_tags")
