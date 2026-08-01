from models import StoreModel, UserModel
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from db import db

from flask import request
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import jwt_required, get_jwt_identity

from schemas import StoreSchema, AddWorkerSchema
from resources.permissions import can_manage_store
from activity_log import log_activity

blp = Blueprint("stores", __name__, description="Operations on stores")


@blp.route("/store/<int:store_id>")
class Store(MethodView):
    @jwt_required()
    @blp.response(200, StoreSchema)
    def get(self, store_id):
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
    @jwt_required()
    @blp.response(200, StoreSchema(many=True))
    def get(self):
        return StoreModel.query.all()

    @jwt_required()
    @blp.arguments(StoreSchema)
    @blp.response(201, StoreSchema)
    def post(self, store_data):
        store = StoreModel(**store_data, owner_id=get_jwt_identity())
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