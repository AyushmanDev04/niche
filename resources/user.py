import os

from flask import request
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from passlib.hash import pbkdf2_sha256
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import joinedload

from db import db
from models import UserModel, ActivityLogModel, Role, UserProfileModel
from schemas import (
    UserSchema,
    UserRegisterSchema,
    LoginSchema,
    UserAdminSchema,
    GoogleLoginSchema,
    ActivityLogSchema,
    UserProfileSchema,
)
from references import generate_unique_ref
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity,
    create_refresh_token,
    get_jwt,
)
from blocklist import add_to_blocklist
from activity_log import log_activity
from rate_limit import limiter

blp = Blueprint("Users", "users", description="Operations on users")


def _require_admin():
    if not get_jwt().get("is_admin"):
        abort(403, message="Admin privilege required.")


@blp.route("/register")
class UserRegister(MethodView):
    decorators = [limiter.limit("10 per hour")]

    @blp.arguments(UserRegisterSchema)
    def post(self, user_data):
        role = user_data.get("role", Role.CUSTOMER)
        email = (user_data.get("email") or "").strip() or None
        user = UserModel(
            username=user_data["username"],
            password=pbkdf2_sha256.hash(user_data["password"]),
            email=email,
            role=role,
            public_ref=generate_unique_ref(UserModel, "public_ref", "CUST"),
        )
        try:
            db.session.add(user)
            db.session.flush()
            log_activity(
                "register",
                user_id=user.id,
                details=f"new {role} account '{user.username}'",
            )
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
    decorators = [limiter.limit("10 per minute; 50 per hour")]

    @blp.arguments(LoginSchema)
    def post(self, user_data):
        user = UserModel.query.filter(
            UserModel.username == user_data["username"]
        ).first()

        if not user or not user.password or not pbkdf2_sha256.verify(user_data["password"], user.password):
            abort(401, message="Invalid credentials.")

        if user.is_banned:
            abort(403, message="This account has been banned.")

        requested_role = user_data.get("role")
        if requested_role and user.role != requested_role and not user.is_admin:
            abort(
                403,
                message=(
                    f"This is a {user.role} account. "
                    f"Switch to the {user.role} tab to sign in."
                ),
            )

        log_activity("login", user_id=user.id, details=f"{user.role} password login")
        db.session.commit()

        access_token = create_access_token(identity=str(user.id), fresh=True)
        refresh_token = create_refresh_token(identity=str(user.id))
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "role": user.role,
            "is_admin": user.is_admin,
            "username": user.username,
            "id": user.id,
        }


@blp.route("/login/google")
class GoogleLogin(MethodView):
    decorators = [limiter.limit("20 per minute")]

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

        email_verified = bool(idinfo.get("email_verified"))

        user = UserModel.query.filter_by(google_id=google_id).first()
        if not user and email and email_verified:
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
                role=login_data.get("role", Role.CUSTOMER),
                public_ref=generate_unique_ref(UserModel, "public_ref", "CUST"),
            )
            db.session.add(user)
            is_new = True

        if user.is_banned:
            db.session.rollback()
            abort(403, message="This account has been banned.")

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

        access_token = create_access_token(identity=str(user.id), fresh=True)
        refresh_token = create_refresh_token(identity=str(user.id))
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "role": user.role,
            "is_admin": user.is_admin,
            "username": user.username,
            "id": user.id,
        }


@blp.route("/refresh")
class TokenRefresh(MethodView):
    @jwt_required(refresh=True)
    def post(self):
        """Exchange a refresh token for a new access token and a new refresh token.

        The refresh token is rotated, not just consumed: this endpoint revokes
        the one it was called with, so returning only an access token left the
        client holding a dead refresh token and silently logged out as soon as
        the new access token expired.
        """
        current_user = get_jwt_identity()
        access_token = create_access_token(identity=current_user, fresh=False)
        refresh_token = create_refresh_token(identity=current_user)
        add_to_blocklist(get_jwt())
        db.session.commit()
        return {"access_token": access_token, "refresh_token": refresh_token}


@blp.route("/logout")
class UserLogout(MethodView):
    @jwt_required()
    def post(self):
        add_to_blocklist(get_jwt())
        log_activity("logout")
        db.session.commit()
        return {"message": "Successfully logged out."}


@blp.route("/me")
class CurrentUser(MethodView):
    @jwt_required()
    @blp.response(200, UserAdminSchema)
    def get(self):
        """The signed-in user's own profile.

        The frontend needs this to know whether to show admin controls; without
        it the only way to learn your own role was to decode the JWT by hand.
        """
        return db.session.get(UserModel, int(get_jwt_identity())) or abort(404)


@blp.route("/me/profile")
class MyProfile(MethodView):
    """Delivery details, server-side. See models/user_profile.py.

    Every signed-in user has exactly one profile row, created on first write
    rather than at registration — most accounts never fill it in, and there
    is nothing to show for one that doesn't exist yet beyond empty fields.
    """

    @jwt_required()
    @blp.response(200, UserProfileSchema)
    def get(self):
        user_id = int(get_jwt_identity())
        profile = db.session.get(UserProfileModel, user_id)
        if profile is None:
            profile = UserProfileModel(user_id=user_id)
        return profile

    @jwt_required()
    @blp.arguments(UserProfileSchema)
    @blp.response(200, UserProfileSchema)
    def put(self, profile_data):
        user_id = int(get_jwt_identity())
        profile = db.session.get(UserProfileModel, user_id)
        if profile is None:
            profile = UserProfileModel(user_id=user_id)
            db.session.add(profile)

        for field in ("address_line1", "address_line2", "city", "state", "pincode", "phone"):
            setattr(profile, field, profile_data.get(field))

        try:
            log_activity("update_profile", details="delivery details updated")
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            abort(500, message="An error occurred while saving your profile.")

        return profile


@blp.route("/user/<int:user_id>")
class User(MethodView):
    @jwt_required()
    @blp.response(200, UserSchema)
    def get(self, user_id):
        if str(user_id) != str(get_jwt_identity()):
            _require_admin()
        return UserModel.query.get_or_404(user_id)

    @jwt_required(fresh=True)
    def delete(self, user_id):
        _require_admin()
        user = UserModel.query.get_or_404(user_id)

        if user.is_admin:
            abort(400, message="Cannot delete an admin account.")

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
        return UserModel.query.options(joinedload(UserModel.stores)).all()


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
        ?limit=<n> to cap how many rows come back (default 200, max 1000)."""
        _require_admin()
        query = ActivityLogModel.query
        user_id = request.args.get("user_id", type=int)
        if user_id is not None:
            query = query.filter_by(user_id=user_id)
        limit = max(0, min(request.args.get("limit", default=200, type=int) or 200, 1000))
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


