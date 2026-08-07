from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError

from sqlalchemy.orm import joinedload

from db import db
from models import OrderModel, ItemModel, StoreModel
from schemas import OrderSchema, PlaceOrderSchema
from resources.permissions import can_work_store, require_customer
from activity_log import log_activity

blp = Blueprint("Orders", "orders", description="Operations on orders")


@blp.route("/item/<int:item_id>/order")
class PlaceOrder(MethodView):
    @jwt_required()
    @blp.arguments(PlaceOrderSchema)
    @blp.response(201, OrderSchema)
    def post(self, order_data, item_id):
        """Customers place orders. Shopkeeper accounts are for selling."""
        require_customer()

        item = ItemModel.query.get_or_404(item_id)
        if item.is_hidden:
            abort(404, message="This item is not currently available.")

        order = OrderModel(
            # get_jwt_identity() returns a string; the column is an integer.
            user_id=int(get_jwt_identity()),
            item_id=item.id,
            store_id=item.store_id,
            quantity=order_data.get("quantity", 1),
            # Freeze the price now. Reading items.price at display time meant a
            # later price edit rewrote the value of orders already placed.
            unit_price=item.price,
            delivery_address=(order_data.get("delivery_address") or None),
            contact_phone=(order_data.get("contact_phone") or None),
            status="pending",
        )
        try:
            db.session.add(order)
            db.session.flush()
            log_activity(
                "place_order",
                details=f"{order.reference}: {order.quantity} x '{item.name}' = {order.total}",
            )
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            abort(500, message="An error occurred while placing the order.")

        return order


@blp.route("/orders")
class MyOrders(MethodView):
    @jwt_required()
    @blp.response(200, OrderSchema(many=True))
    def get(self):
        """The current user's own order history."""
        user_id = get_jwt_identity()
        return (
            OrderModel.query.options(
                joinedload(OrderModel.item), joinedload(OrderModel.user)
            )
            .filter_by(user_id=int(user_id))
            .order_by(OrderModel.created_at.desc())
            .all()
        )


@blp.route("/store/<int:store_id>/order")
class StoreOrders(MethodView):
    @jwt_required()
    @blp.response(200, OrderSchema(many=True))
    def get(self, store_id):
        """Owner, workers, or admin see every order placed at this store."""
        store = StoreModel.query.get_or_404(store_id)
        if not can_work_store(store):
            abort(403, message="You do not have permission to view this store's orders.")

        return (
            OrderModel.query.options(
                joinedload(OrderModel.item), joinedload(OrderModel.user)
            )
            .filter_by(store_id=store_id)
            .order_by(OrderModel.created_at.desc())
            .all()
        )


@blp.route("/order/<int:order_id>/fulfill")
class FulfillOrder(MethodView):
    @jwt_required()
    @blp.response(200, OrderSchema)
    def post(self, order_id):
        order = OrderModel.query.get_or_404(order_id)
        if not can_work_store(order.store):
            abort(403, message="You do not have permission to fulfill this order.")
        if order.status != "pending":
            abort(400, message=f"Order is already {order.status}.")

        order.status = "fulfilled"
        log_activity("fulfill_order", details=f"fulfilled {order.reference}")
        db.session.commit()
        return order


@blp.route("/order/<int:order_id>/cancel")
class CancelOrder(MethodView):
    @jwt_required()
    @blp.response(200, OrderSchema)
    def post(self, order_id):
        order = OrderModel.query.get_or_404(order_id)
        user_id = get_jwt_identity()

        is_customer = str(order.user_id) == str(user_id)
        if not is_customer and not can_work_store(order.store):
            abort(403, message="You do not have permission to cancel this order.")
        if order.status != "pending":
            abort(400, message=f"Order is already {order.status}.")

        order.status = "cancelled"
        log_activity("cancel_order", details=f"cancelled {order.reference}")
        db.session.commit()
        return order