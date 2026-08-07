import os

from flask import Flask, jsonify
from flask_smorest import Api
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_cors import CORS  # type: ignore

from db import db
from blocklist import is_revoked
import models
from models.user import UserModel

from resources.user import blp as UserBlueprint
from resources.item import blp as ItemBlueprint
from resources.store import blp as StoreBlueprint
from resources.tag import blp as TagBlueprint
from resources.review import blp as ReviewBlueprint
from resources.order import blp as OrderBlueprint
from rate_limit import limiter
from cli import register_cli


def _require_env(name):
    """Read a required secret, refusing to start without it.

    A default here would be worse than a crash: the app would boot happily and
    sign every token with a value that is public in the repository.
    """
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"{name} is not set. Refusing to start with an insecure default. "
            f"Set {name} in the environment (Render: Environment tab)."
        )
    return value


def create_app():
    # The frontend lives in static/ and *only* static/ is web-reachable.
    # This used to be static_folder="." which served the entire project root,
    # meaning /.env, /data.db and /app.py were all downloadable by anyone.
    app = Flask(__name__, static_folder="static", static_url_path="")

    app.config["PROPAGATE_EXCEPTIONS"] = True
    app.config["API_TITLE"] = "Stores REST API"
    app.config["API_VERSION"] = "v1"
    app.config["OPENAPI_VERSION"] = "3.0.3"
    app.config["OPENAPI_URL_PREFIX"] = "/api-docs"
    app.config["OPENAPI_SWAGGER_UI_PATH"] = "/swagger-ui"
    app.config["OPENAPI_SWAGGER_UI_URL"] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///data.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["JWT_SECRET_KEY"] = _require_env("JWT_SECRET_KEY")
    app.config["SECRET_KEY"] = _require_env("SECRET_KEY")

    db.init_app(app)
    Migrate(app, db)
    api = Api(app)
    limiter.init_app(app)

    # Only allow browsers on origins we name. `CORS(app)` allowed every site on
    # the internet to call this API with a logged-in user's credentials.
    origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
    CORS(app, origins=origins or ["http://localhost:5000"], supports_credentials=False)

    jwt = JWTManager(app)

    @jwt.token_in_blocklist_loader
    def check_if_token_in_blocklist(jwt_header, jwt_payload):
        if is_revoked(jwt_payload.get("jti")):
            return True
        # A ban has to take effect immediately, including for tokens already
        # issued, so this costs one indexed primary-key lookup per request.
        # (add_claims_to_jwt below is not in this path — flask-jwt-extended
        # only calls it when a token is created.)
        user = db.session.get(UserModel, int(jwt_payload["sub"]))
        return bool(user and user.is_banned)

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return (
            jsonify(
                {"description": "The token has been revoked.", "error": "token_revoked"}
            ),
            401,
        )

    @jwt.needs_fresh_token_loader
    def token_not_fresh_callback(jwt_header, jwt_payload):
        return (
            jsonify(
                {
                    "description": "The token is not fresh.",
                    "error": "fresh_token_required",
                }
            ),
            401,
        )

    @jwt.additional_claims_loader
    def add_claims_to_jwt(identity):
        user = db.session.get(UserModel, int(identity))
        # role travels in the token so customer/shopkeeper checks don't need a
        # database round trip on every request.
        return {
            "is_admin": bool(user and user.is_admin),
            "role": user.role if user else None,
        }

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return (
            jsonify({"message": "The token has expired.", "error": "token_expired"}),
            401,
        )

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return (
            jsonify(
                {"message": "Signature verification failed.", "error": "invalid_token"}
            ),
            401,
        )

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return (
            jsonify(
                {
                    "description": "Request does not contain an access token.",
                    "error": "authorization_required",
                }
            ),
            401,
        )

    api.register_blueprint(ItemBlueprint)
    api.register_blueprint(StoreBlueprint)
    api.register_blueprint(TagBlueprint)
    api.register_blueprint(UserBlueprint)
    api.register_blueprint(ReviewBlueprint)
    api.register_blueprint(OrderBlueprint)

    register_cli(app)

    # NOTE: schema creation is owned by Alembic, not by the app.
    # db.create_all() here would build tables without stamping alembic_version,
    # after which every `flask db upgrade` fails on already-existing tables.
    # Run migrations on deploy instead: `flask db upgrade && flask bootstrap-admin`.

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"}), 200

    @app.route("/config")
    def config():
        # Public by design: a Google client ID is not a secret, the frontend
        # needs it to render the sign-in button.
        return jsonify({"google_client_id": os.getenv("GOOGLE_CLIENT_ID", "")}), 200

    @app.route("/")
    def serve_frontend():
        return app.send_static_file("index.html")

    return app
