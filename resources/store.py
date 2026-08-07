from models import StoreModel, UserModel, ReviewModel, ItemModel
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import joinedload
from db import db

from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import jwt_required, get_jwt_identity

from schemas import StoreSchema, AddWorkerSchema, StoreReviewSummarySchema
from resources.permissions import can_manage_store, can_work_store, require_shopkeeper
from activity_log import log_activity

blp = Blueprint("stores", __name__, description="Operations on stores")


@blp.route("/store/<int:store_id>")
class Store(MethodView):
    @jwt_required(optional=True)
    @blp.response(200, StoreSchema)
    def get(self, store_id):
        """Public. Storefronts are browsable without an account."""
        store = StoreModel.query.get_or_404(store_id)
        return store

    @jwt_required()
    def delete(self, store_id):
        store = StoreModel.query.get_or_404(store_id)
        if not can_manage_store(store):
            abort(403, message="You do not have permission to delete this store.")
        log_activity("delete_store", details=f"store '{store.name}' (id={store.id})")
        db.session.delete(store)
        db.session.commit()
        return {"message": "store deleted"}


@blp.route("/store")
class StoreList(MethodView):
    @jwt_required(optional=True)
    @blp.response(200, StoreSchema(many=True))
    def get(self):
        """Public, like GET /store/<id>."""
        return StoreModel.query.all()

    @jwt_required()
    @blp.arguments(StoreSchema)
    @blp.response(201, StoreSchema)
    def post(self, store_data):
        require_shopkeeper()
        store = StoreModel(**store_data, owner_id=int(get_jwt_identity()))
        try:
            db.session.add(store)
            db.session.flush()
            log_activity("create_store", details=f"store '{store.name}' (id={store.id})")
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            abort(
                400,
                message="A store with that name already exists.",
            )
        except SQLAlchemyError:
            db.session.rollback()
            abort(500, message="An error occurred creating the store.")

        return store


@blp.route("/store/<int:store_id>/review")
class StoreReviews(MethodView):
    @jwt_required()
    @blp.response(200, StoreReviewSummarySchema)
    def get(self, store_id):
        """Every review left on this store's items, with the ratings rolled up.

        Shopkeepers cannot write reviews, so this read-only view is how they
        see what customers said: the full comments, the mean rating as a
        float, the distribution across 1-5 stars, and a per-item breakdown.
        """
        store = StoreModel.query.get_or_404(store_id)
        if not can_work_store(store):
            abort(403, message="You do not have permission to view this store's reviews.")

        reviews = (
            ReviewModel.query.options(
                joinedload(ReviewModel.user), joinedload(ReviewModel.item)
            )
            .join(ItemModel, ReviewModel.item_id == ItemModel.id)
            .filter(ItemModel.store_id == store_id)
            .order_by(ReviewModel.created_at.desc())
            .all()
        )

        breakdown = {str(star): 0 for star in range(1, 6)}
        for review in reviews:
            breakdown[str(review.rating)] += 1

        per_item = [
            {
                "item_id": item.id,
                "item_name": item.name,
                "average_rating": round(float(item.average_rating or 0), 2),
                "review_count": item.review_count,
            }
            for item in store.items.all()
        ]

        return {
            "store_id": store.id,
            "store_name": store.name,
            "average_rating": round(float(store.average_rating or 0), 2),
            "review_count": store.review_count,
            "rating_breakdown": breakdown,
            "per_item": sorted(per_item, key=lambda row: -row["review_count"]),
            "reviews": reviews,
        }


@blp.route("/store/<int:store_id>/worker")
class StoreWorkers(MethodView):
    @jwt_required()
    @blp.arguments(AddWorkerSchema)
    @blp.response(200, StoreSchema)
    def post(self, worker_data, store_id):
        store = StoreModel.query.get_or_404(store_id)
        if not can_manage_store(store):
            abort(403, message="Only the store owner or an admin can add workers.")

        user = UserModel.query.filter_by(username=worker_data["username"]).first()
        if not user:
            abort(404, message="No user with that username.")

        if not user.is_shopkeeper:
            abort(
                400,
                message="Only shopkeeper accounts can work a store. That user is a customer.",
            )

        if store.owner_id is not None and str(store.owner_id) == str(user.id):
            abort(400, message="This user already owns the store.")

        if user in store.workers:
            abort(400, message="This user is already a worker at this store.")

        store.workers.append(user)
        log_activity(
            "add_worker",
            details=f"added '{user.username}' as worker to store '{store.name}' (id={store.id})",
        )
        db.session.commit()
        return store


@blp.route("/store/<int:store_id>/worker/<int:user_id>")
class StoreWorker(MethodView):
    @jwt_required()
    @blp.response(200, StoreSchema)
    def delete(self, store_id, user_id):
        store = StoreModel.query.get_or_404(store_id)
        if not can_manage_store(store):
            abort(403, message="Only the store owner or an admin can remove workers.")

        user = UserModel.query.get_or_404(user_id)
        if user not in store.workers:
            abort(404, message="This user is not a worker at this store.")

        store.workers.remove(user)
        log_activity(
            "remove_worker",
            details=f"removed '{user.username}' as worker from store '{store.name}' (id={store.id})",
        )
        db.session.commit()
        return store