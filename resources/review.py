from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import joinedload

from db import db
from models import ReviewModel, ItemModel
from schemas import ReviewSchema
from resources.permissions import can_work_store, is_admin, require_customer
from activity_log import log_activity

blp = Blueprint("Reviews", "reviews", description="Operations on reviews")


@blp.route("/item/<int:item_id>/review")
class ItemReviewList(MethodView):
    @jwt_required(optional=True)
    @blp.response(200, ReviewSchema(many=True))
    def get(self, item_id):
        item = ItemModel.query.get_or_404(item_id)
        if item.is_hidden and not (get_jwt() and can_work_store(item.store)):
            abort(404, message="Item not found.")
        return (
            ReviewModel.query.options(joinedload(ReviewModel.user))
            .filter_by(item_id=item_id)
            .order_by(ReviewModel.created_at.desc())
            .all()
        )

    @jwt_required()
    @blp.arguments(ReviewSchema)
    @blp.response(201, ReviewSchema)
    def post(self, review_data, item_id):
        require_customer()

        item = ItemModel.query.get_or_404(item_id)
        if item.is_hidden:
            abort(404, message="Item not found.")

        user_id = get_jwt_identity()

        review = ReviewModel(
            rating=review_data["rating"],
            comment=review_data.get("comment"),
            item_id=item_id,
            user_id=int(user_id),
        )

        try:
            db.session.add(review)
            db.session.flush()
            log_activity("create_review", details=f"rated item '{item.name}' (id={item.id}) {review.rating}/5")
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            abort(409, message="You have already reviewed this item.")
        except SQLAlchemyError:
            db.session.rollback()
            abort(500, message="An error occurred while inserting the review.")

        return review


@blp.route("/review/<int:review_id>")
class Review(MethodView):
    @jwt_required()
    def delete(self, review_id):
        review = ReviewModel.query.get_or_404(review_id)
        user_id = get_jwt_identity()

        is_author = str(review.user_id) == str(user_id)
        if not is_author and not is_admin():
            abort(403, message="You can only delete your own review.")

        log_activity(
            "delete_review",
            details=("deleted own review" if is_author else "moderated review")
            + f" (id={review.id})",
        )
        db.session.delete(review)
        db.session.commit()
        return {"message": "Review deleted."}
