from flask import request
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import jwt_required, get_jwt
from sqlalchemy.exc import SQLAlchemyError

from db import db
from models import ItemModel, StoreModel
from schemas import ItemSchema, ItemUpdateSchema
from resources.permissions import can_manage_store, can_work_store
from activity_log import log_activity

blp = Blueprint("Items", "items", description="Operations on items")


@blp.route("/item/<int:item_id>")
class Item(MethodView):
    @jwt_required()
    @blp.response(200, ItemSchema)
    def get(self, item_id):
        item = ItemModel.query.get_or_404(item_id)
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
        item.name = item_data.get("name", item.name)
        item.price = item_data.get("price", item.price)

        log_activity("edit_item", details=f"item '{item.name}' (id={item.id})")
        db.session.add(item)
        db.session.commit()

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
        return ItemModel.query.all()

    @jwt_required(fresh=True)
    @blp.arguments(ItemSchema)
    @blp.response(201, ItemSchema)
    def post(self, item_data):
        store = StoreModel.query.get_or_404(item_data["store_id"])
        if not can_work_store(store):
            abort(403, message="You do not have permission to add items to this store.")

        item = ItemModel(**item_data)
        try:
            db.session.add(item)
            db.session.flush()
            log_activity("create_item", details=f"item '{item.name}' (id={item.id}) in store id={store.id}")
            db.session.commit()

        except SQLAlchemyError:
            db.session.rollback()
            abort(500, message="An error occurred while inserting the item.")

        return item