from sqlalchemy import func, select
from sqlalchemy.orm import column_property

from models.store import StoreModel
from models.item import ItemModel
from models.tag import TagModel
from models.item_tags import ItemTags
from models.user import UserModel, Role
from models.review import ReviewModel
from models.store_worker import StoreWorkerModel
from models.activity import ActivityLogModel
from models.order import OrderModel
from models.token_blocklist import TokenBlocklistModel


# --- Aggregate rating columns -------------------------------------------
#
# Defined here rather than on the model classes because they reference
# ReviewModel, which imports later in the dependency graph.
#
# These are correlated subqueries evaluated as part of the parent SELECT, not
# Python properties. That matters: computing an average in Python would load
# every review of every item on any listing endpoint.
#
# COALESCE gives 0.0 for an unreviewed item rather than NULL, so the API always
# returns a number and clients never have to special-case it.

ItemModel.average_rating = column_property(
    select(func.coalesce(func.avg(ReviewModel.rating), 0.0))
    .where(ReviewModel.item_id == ItemModel.id)
    .correlate_except(ReviewModel)
    .scalar_subquery(),
    deferred=False,
)

ItemModel.review_count = column_property(
    select(func.count(ReviewModel.id))
    .where(ReviewModel.item_id == ItemModel.id)
    .correlate_except(ReviewModel)
    .scalar_subquery(),
    deferred=False,
)

# Store-level aggregates roll up every review across every item in the store.
StoreModel.average_rating = column_property(
    select(func.coalesce(func.avg(ReviewModel.rating), 0.0))
    .select_from(ReviewModel)
    .join(ItemModel, ReviewModel.item_id == ItemModel.id)
    .where(ItemModel.store_id == StoreModel.id)
    .correlate_except(ReviewModel, ItemModel)
    .scalar_subquery(),
    deferred=False,
)

StoreModel.review_count = column_property(
    select(func.count(ReviewModel.id))
    .select_from(ReviewModel)
    .join(ItemModel, ReviewModel.item_id == ItemModel.id)
    .where(ItemModel.store_id == StoreModel.id)
    .correlate_except(ReviewModel, ItemModel)
    .scalar_subquery(),
    deferred=False,
)


__all__ = [
    "StoreModel",
    "ItemModel",
    "TagModel",
    "ItemTags",
    "UserModel",
    "Role",
    "ReviewModel",
    "StoreWorkerModel",
    "ActivityLogModel",
    "OrderModel",
    "TokenBlocklistModel",
]
