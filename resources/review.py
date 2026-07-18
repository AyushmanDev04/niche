from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError

from db import db
from models import ReviewModel, ItemModel
from schemas import ReviewSchema

blp = Blueprint("Reviews", "reviews", description="Operations on reviews")


@blp.route("/item/<int:item_id>/review")
class ItemReviewList(MethodView):
    @blp.response(200, ReviewSchema(many=True))
    def get(self, item_id):
        item = ItemModel.query.get_or_404(item_id)
        return item.reviews

    @jwt_required()
    @blp.arguments(ReviewSchema)
    @blp.response(201, ReviewSchema)
    def post(self, review_data, item_id):
        ItemModel.query.get_or_404(item_id)
        user_id = get_jwt_identity()

        review = ReviewModel(
            rating=review_data["rating"],
            comment=review_data.get("comment"),
            item_id=item_id,
            user_id=user_id,
        )

        try:
            db.session.add(review)
            db.session.commit()
        except SQLAlchemyError:
            abort(500, message="An error occurred while inserting the review.")

        return review


@blp.route("/review/<int:review_id>")
class Review(MethodView):
    @jwt_required()
    def delete(self, review_id):
        review = ReviewModel.query.get_or_404(review_id)
        user_id = get_jwt_identity()

        if str(review.user_id) != str(user_id):
            abort(403, message="You can only delete your own review.")

        db.session.delete(review)
        db.session.commit()
        return {"message": "Review deleted."}