import os
from flask import request
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from passlib.hash import pbkdf2_sha256
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from db import db
from models import UserModel, ActivityLogModel
from schemas import UserSchema, UserAdminSchema, GoogleLoginSchema, ActivityLogSchema
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity,
    create_refresh_token,
    get_jwt,
)
from blocklist import BLOCKLIST
from activity_log import log_activity

blp = Blueprint("Users", "users", description="Operations on users")


def _require_admin():
    if not get_jwt().get("is_admin"):
        abort(403, message="Admin privilege required.")


@blp.route("/register")
class UserRegister(MethodView):
    @blp.arguments(UserSchema)
    def post(self, user_data):
        user = UserModel(
            username=user_data["username"],
            password=pbkdf2_sha256.hash(user_data["password"])
        )
        try:
            db.session.add(user)
            db.session.flush()
            log_activity("register", user_id=user.id, details=f"new account '{user.username}'")
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            abort(409, message="A user with that username already exists.")
        except SQLAlchemyError:
            db.session.rollback()
            abort(500, message="An error occurred while inserting the user.")

        return {"message": "User created successfully."}, 201


@blp.route("/login")
class UserLogin(MethodView):
    @blp.arguments(UserSchema)
    def post(self, user_data):
        user = UserModel.query.filter(
            UserModel.username == user_data["username"]
        ).first()

        if not user or not user.password or not pbkdf2_sha256.verify(user_data["password"], user.password):
            abort(401, message="Invalid credentials.")

        if user.is_banned:
            abort(403, message="This account has been banned.")

        log_activity("login", user_id=user.id, details="password login")
        db.session.commit()

        access_token = create_access_token(identity=str(user.id), fresh=True)
        refresh_token = create_refresh_token(identity=str(user.id))
        return {"access_token": access_token, "refresh_token": refresh_token}


@blp.route("/login/google")
class GoogleLogin(MethodView):
    @blp.arguments(GoogleLoginSchema)
    def post(self, login_data):
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        if not client_id:
            abort(500, message="Google sign-in is not configured on this server.")

        try:
            from google.oauth2 import id_token as google_id_token
            from google.auth.transport import requests as google_requests

            idinfo = google_id_token.verify_oauth2_token(
                login_data["credential"], google_requests.Request(), client_id
            )
        except ValueError:
            abort(401, message="Invalid Google credential.")
        except ImportError:
            abort(500, message="Google sign-in dependency not installed (google-auth).")

        google_id = idinfo["sub"]
        email = idinfo.get("email")

        user = UserModel.query.filter_by(google_id=google_id).first()
        if not user and email:
            user = UserModel.query.filter_by(email=email).first()
            if user:
                user.google_id = google_id

        is_new = False
        if not user:
            base_username = (email.split("@")[0] if email else f"google_{google_id[:8]}")
            username = base_username
            suffix = 1
            while UserModel.query.filter_by(username=username).first():
                suffix += 1
                username = f"{base_username}{suffix}"

            user = UserModel(
                username=username,
                email=email,
                google_id=google_id,
                password=None,
            )
            db.session.add(user)
            is_new = True

        try:
            db.session.flush()
            log_activity(
                "register" if is_new else "login",
                user_id=user.id,
                details="google sign-in" + (" (new account)" if is_new else ""),
            )
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            abort(500, message="An error occurred while signing in with Google.")

        if user.is_banned:
            abort(403, message="This account has been banned.")

        access_token = create_access_token(identity=str(user.id), fresh=True)
        refresh_token = create_refresh_token(identity=str(user.id))
        return {"access_token": access_token, "refresh_token": refresh_token}


@blp.route("/refresh")
class TokenRefresh(MethodView):
    @jwt_required(refresh=True)
    def post(self):
        current_user = get_jwt_identity()
        new_token = create_access_token(identity=current_user, fresh=False)
        jti = get_jwt()["jti"]
        BLOCKLIST.add(jti)
        return {"access_token": new_token}


@blp.route("/logout")
class UserLogout(MethodView):
    @jwt_required()
    def post(self):
        jti = get_jwt().get("jti")
        BLOCKLIST.add(jti)
        log_activity("logout")
        db.session.commit()
        return {"message": "Successfully logged out."}


@blp.route("/user/<int:user_id>")
class User(MethodView):
    @jwt_required()
    @blp.response(200, UserSchema)
    def get(self, user_id):
        user = UserModel.query.get_or_404(user_id)
        return user

    @jwt_required()
    def delete(self, user_id):
        _require_admin()
        user = UserModel.query.get_or_404(user_id)

        for store in user.stores:
            store.owner_id = None

        log_activity("delete_user", details=f"deleted account '{user.username}' (id={user.id})")
        db.session.delete(user)
        db.session.commit()
        return {"message": "User deleted."}, 200


@blp.route("/users")
class UserList(MethodView):
    @jwt_required()
    @blp.response(200, UserAdminSchema(many=True))
    def get(self):
        _require_admin()
        return UserModel.query.all()


@blp.route("/user/<int:user_id>/ban")
class BanUser(MethodView):
    @jwt_required()
    @blp.response(200, UserAdminSchema)
    def post(self, user_id):
        _require_admin()
        user = UserModel.query.get_or_404(user_id)
        if user.is_admin:
            abort(400, message="Cannot ban another admin.")
        user.is_banned = True
        log_activity("ban_user", details=f"banned '{user.username}' (id={user.id})")
        db.session.commit()
        return user


@blp.route("/user/<int:user_id>/unban")
class UnbanUser(MethodView):
    @jwt_required()
    @blp.response(200, UserAdminSchema)
    def post(self, user_id):
        _require_admin()
        user = UserModel.query.get_or_404(user_id)
        user.is_banned = False
        log_activity("unban_user", details=f"unbanned '{user.username}' (id={user.id})")
        db.session.commit()
        return user


@blp.route("/activity")
class ActivityFeed(MethodView):
    @jwt_required()
    @blp.response(200, ActivityLogSchema(many=True))
    def get(self):
        """Admin-only: see everyone's recent activity, newest first.
        Optional query params: ?user_id=<id> to filter to one account,
        ?limit=<n> to cap how many rows come back (default 200)."""
        _require_admin()
        query = ActivityLogModel.query
        user_id = request.args.get("user_id")
        if user_id:
            query = query.filter_by(user_id=user_id)
        limit = request.args.get("limit", default=200, type=int)
        return query.order_by(ActivityLogModel.created_at.desc()).limit(limit).all()


@blp.route("/user/<int:user_id>/activity")
class UserActivity(MethodView):
    @jwt_required()
    @blp.response(200, ActivityLogSchema(many=True))
    def get(self, user_id):
        """Admin-only: a specific user's activity history."""
        _require_admin()
        return (
            ActivityLogModel.query.filter_by(user_id=user_id)
            .order_by(ActivityLogModel.created_at.desc())
            .limit(200)
            .all()
        )



@blp.route("/make-admin/<string:username>")
class MakeAdmin(MethodView):
    def post(self, username):
        secret = request.headers.get("X-Admin-Secret")
        if not secret or secret != os.getenv("ADMIN_SECRET"):
            abort(403, message="Forbidden")
        user = UserModel.query.filter_by(username=username).first()
        if not user:
            abort(404, message="User not found")
        user.is_admin = True
        db.session.commit()
        return {"message": f"{username} is now an admin."}