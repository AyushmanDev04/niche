import logging

from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import select
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import joinedload

from db import db
from models import OrderModel, ItemModel, StoreModel, UserProfileModel
from schemas import OrderSchema, PlaceOrderSchema, OrderTransitionSchema
from resources.permissions import can_work_store, require_customer
from order_lifecycle import OrderStatus, TransitionError, assert_transition
from references import generate_unique_ref
from activity_log import log_activity
from tasks import send_order_confirmation_email

blp = Blueprint("Orders", "orders", description="Operations on orders")
logger = logging.getLogger("niche.orders")

_LOCK_TIMEOUT_SQLSTATE = "55P03"


def _is_lock_timeout(exc):
    return getattr(getattr(exc, "orig", None), "pgcode", None) == _LOCK_TIMEOUT_SQLSTATE


def _restore_stock_if_tracked(order):
    """Give back the stock an order reserved at checkout, on cancellation.

    Locks the item row before reading it. Without the lock, restoring stock
    here and decrementing it in a concurrent PlaceOrder on the same item is a
    textbook lost-update race: both read the old value, both write their own
    result, and whichever commits last silently erases the other's change.
    """
    if order.item_id is None:
        return
    item = db.session.execute(
        select(ItemModel).where(ItemModel.id == order.item_id).with_for_update()
    ).scalar_one_or_none()
    if item is not None and item.stock_quantity is not None:
        item.stock_quantity += order.quantity


@blp.route("/item/<int:item_id>/order")
class PlaceOrder(MethodView):
    @jwt_required()
    @blp.arguments(PlaceOrderSchema)
    @blp.response(201, OrderSchema)
    def post(self, order_data, item_id):
        """Customers place orders. Shopkeeper accounts are for selling.

        Stock, if tracked, is locked and decremented in the same transaction
        that creates the order — see the module docstring in
        order_lifecycle.py and the row-lock comment below for why.
        """
        require_customer()

        try:
            item = db.session.execute(
                select(ItemModel).where(ItemModel.id == item_id).with_for_update()
            ).scalar_one_or_none()
        except OperationalError as exc:
            db.session.rollback()
            if _is_lock_timeout(exc):
                abort(
                    409,
                    message="This item is being purchased by someone else right now. Please try again in a moment.",
                )
            raise

        if item is None or item.is_hidden:
            db.session.rollback()
            abort(404, message="This item is not currently available.")

        quantity = order_data.get("quantity", 1)

        if item.stock_quantity is not None and item.stock_quantity < quantity:
            db.session.rollback()
            available = item.stock_quantity
            if available <= 0:
                message = "This item is out of stock."
            elif available == 1:
                message = "Only 1 left in stock."
            else:
                message = f"Only {available} left in stock."
            abort(409, message=message)

        if item.stock_quantity is not None:
            item.stock_quantity -= quantity

        address = order_data.get("delivery_address")
        phone = order_data.get("contact_phone")
        if not address or not phone:
            profile = db.session.get(UserProfileModel, int(get_jwt_identity()))
            if profile is not None:
                if not address and profile.address_line1:
                    address = profile.formatted_address
                if not phone and profile.phone:
                    phone = profile.phone

        order = OrderModel(
            user_id=int(get_jwt_identity()),
            item_id=item.id,
            store_id=item.store_id,
            quantity=quantity,
            unit_price=item.price,
            delivery_address=address or None,
            contact_phone=phone or None,
            status=OrderStatus.PENDING,
            public_ref=generate_unique_ref(OrderModel, "public_ref", "ORD"),
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

        try:
            send_order_confirmation_email.delay(order.id)
        except Exception:  # noqa: BLE001
            logger.exception("Could not enqueue confirmation email for %s", order.reference)

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


@blp.route("/order/<int:order_id>/transition")
class OrderTransition(MethodView):
    @jwt_required()
    @blp.arguments(OrderTransitionSchema)
    @blp.response(200, OrderSchema)
    def post(self, data, order_id):
        """Move an order to its next state.

        Replaces the old separate /fulfill and /cancel endpoints: with five
        states instead of two, "the next thing that can happen" needs one
        authoritative table (order_lifecycle.py), not N near-duplicate route
        handlers that could each drift from it independently.
        """
        try:
            order = db.session.execute(
                select(OrderModel).where(OrderModel.id == order_id).with_for_update()
            ).scalar_one_or_none()
        except OperationalError as exc:
            db.session.rollback()
            if _is_lock_timeout(exc):
                abort(409, message="This order is being updated elsewhere right now. Please try again.")
            raise

        if order is None:
            db.session.rollback()
            abort(404, message="Order not found.")

        user_id = get_jwt_identity()
        is_customer_actor = str(order.user_id) == str(user_id)
        is_shop_actor = can_work_store(order.store)

        if not is_customer_actor and not is_shop_actor:
            db.session.rollback()
            abort(403, message="You do not have permission to update this order.")

        target = data["status"]
        actor = "shop" if is_shop_actor else "customer"

        try:
            assert_transition(order.status, target, actor=actor)
        except TransitionError as exc:
            db.session.rollback()
            abort(400, message=str(exc))

        if target == OrderStatus.CANCELLED:
            try:
                _restore_stock_if_tracked(order)
            except OperationalError as exc:
                db.session.rollback()
                if _is_lock_timeout(exc):
                    abort(409, message="This item is busy right now. Please try cancelling again in a moment.")
                raise

        order.status = target
        log_activity(f"order_{target}", details=f"{order.reference} -> {target}")
        db.session.commit()
        return order
