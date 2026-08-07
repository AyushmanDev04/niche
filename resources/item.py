from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import joinedload, selectinload

from db import db
from models import ItemModel, StoreModel
from schemas import ItemSchema, ItemUpdateSchema
from resources.permissions import can_manage_store, can_work_store, require_shopkeeper
from activity_log import log_activity

blp = Blueprint("Items", "items", description="Operations on items")


@blp.route("/item/<int:item_id>")
class Item(MethodView):
    @jwt_required()
    @blp.response(200, ItemSchema)
    def get(self, item_id):
        item = ItemModel.query.get_or_404(item_id)
        # Hiding an item should hide it from customers, not just from lists.
        if item.is_hidden and not can_work_store(item.store):
            abort(404, message="Item not found.")
        return item

    @jwt_required()
    def delete(self, item_id):
        item = ItemModel.query.get_or_404(item_id)
        if not can_manage_store(item.store):
            abort(403, message="Only the store owner or an admin can permanently delete an item.")
        log_activity("delete_item", details=f"item '{item.name}' (id={item.id}) from store id={item.store_id}")
        db.session.delete(item)
        db.session.commit()
        return {"message": "Item deleted"}

    @jwt_required()
    @blp.arguments(ItemUpdateSchema)
    @blp.response(200, ItemSchema)
    def put(self, item_data, item_id):
        item = ItemModel.query.get_or_404(item_id)
        if not can_work_store(item.store):
            abort(403, message="You do not have permission to edit this item.")

        # Previously only name and price were applied, so an image_url edit
        # returned 200 and silently changed nothing.
        for field in ("name", "price", "image_url"):
            if field in item_data:
                setattr(item, field, item_data[field])

        try:
            db.session.add(item)
            log_activity("edit_item", details=f"item '{item.name}' (id={item.id})")
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            abort(409, message="This store already has an item with that name.")
        except SQLAlchemyError:
            db.session.rollback()
            abort(500, message="An error occurred while updating the item.")

        return item


@blp.route("/item/<int:item_id>/hide")
class HideItem(MethodView):
    @jwt_required()
    @blp.response(200, ItemSchema)
    def post(self, item_id):
        item = ItemModel.query.get_or_404(item_id)
        if not can_work_store(item.store):
            abort(403, message="You do not have permission to hide this item.")
        item.is_hidden = True
        log_activity("hide_item", details=f"item '{item.name}' (id={item.id})")
        db.session.commit()
        return item


@blp.route("/item/<int:item_id>/unhide")
class UnhideItem(MethodView):
    @jwt_required()
    @blp.response(200, ItemSchema)
    def post(self, item_id):
        item = ItemModel.query.get_or_404(item_id)
        if not can_work_store(item.store):
            abort(403, message="You do not have permission to unhide this item.")
        item.is_hidden = False
        log_activity("unhide_item", details=f"item '{item.name}' (id={item.id})")
        db.session.commit()
        return item


@blp.route("/item")
class ItemList(MethodView):
    @jwt_required()
    @blp.response(200, ItemSchema(many=True))
    def get(self):
        # joinedload/selectinload prevent a query per item for store, tags and
        # reviews while serialising (the response nests all three).
        query = ItemModel.query.options(
            joinedload(ItemModel.store),
            selectinload(ItemModel.tags),
            selectinload(ItemModel.reviews),
        )

        # Hidden items are visible only to people who can work the store that
        # owns them; everyone else gets the public catalogue.
        items = query.all()
        return [item for item in items if not item.is_hidden or can_work_store(item.store)]

    @jwt_required(fresh=True)
    @blp.arguments(ItemSchema)
    @blp.response(201, ItemSchema)
    def post(self, item_data):
        # Customers cannot sell.
        require_shopkeeper()
        store = StoreModel.query.get_or_404(item_data["store_id"])
        if not can_work_store(store):
            abort(403, message="You do not have permission to add items to this store.")

        item = ItemModel(**item_data)
        try:
            db.session.add(item)
            db.session.flush()
            log_activity("create_item", details=f"item '{item.name}' (id={item.id}) in store id={store.id}")
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            abort(409, message="This store already has an item with that name.")
        except SQLAlchemyError:
            db.session.rollback()
            abort(500, message="An error occurred while inserting the item.")

        return item
