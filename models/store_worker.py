from db import db


class StoreWorkerModel(db.Model):
    __tablename__ = "store_workers"
    __table_args__ = (
        db.UniqueConstraint("store_id", "user_id", name="uq_store_worker"),
    )

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)