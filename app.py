from flask import Flask, jsonify
from flask_smorest import Api
from flask_jwt_extended import JWTManager
import os
from resources.ser import blp as UserBlueprint
from models.user import UserModel
from flask_migrate import Migrate
from blocklist import BLOCKLIST


from flask_cors import CORS  # type: ignore
from db import db
import models

from resources.item import blp as ItemBlueprint
from resources.store import blp as StoreBlueprint
from resources.ag import blp as TagBlueprint
from resources.review import blp as ReviewBlueprint
from resources.order import blp as OrderBlueprint


def create_app():
    # static_folder="." + static_url_path="" makes Flask serve any file
    # sitting in the project root (index.html, app.js, styles.css) directly
    # e.g. app.js is served at /app.js, styles.css at /styles.css
    app = Flask(__name__, static_folder=".", static_url_path="")

    app.config["PROPAGATE_EXCEPTIONS"] = True
    app.config["API_TITLE"] = "Stores REST API"
    app.config["API_VERSION"] = "v1"
    app.config["OPENAPI_VERSION"] = "3.0.3"
    app.config["OPENAPI_URL_PREFIX"] = "/api-docs"
    app.config["OPENAPI_SWAGGER_UI_PATH"] = "/swagger-ui"
    app.config["OPENAPI_SWAGGER_UI_URL"] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///data.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "dev-secret-change-in-production")

    db.init_app(app)
    migrate = Migrate(app, db)
    api = Api(app)
    CORS(app)

    jwt = JWTManager(app)

    @jwt.token_in_blocklist_loader
    def check_if_token_in_blocklist(jwt_header, jwt_payload):
        if jwt_payload["jti"] in BLOCKLIST:
            return True
        user = UserModel.query.get(int(jwt_payload["sub"]))
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
        user = UserModel.query.get(int(identity))
        if user and user.is_admin:
            return {"is_admin": True}
        return {"is_admin": False}

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

    # Create database tables if they don't exist yet. Without this, a fresh
    # deploy (fresh SQLite file, or fresh Postgres database) has no tables
    # at all, and every insert/query fails.
    with app.app_context():
       # db.create_all()

        # Ensure a permanent admin user always exists. Set ADMIN_USERNAME
        # and ADMIN_PASSWORD in Render's Environment tab. This runs on
        # every startup, so the admin survives database resets.
        admin_username = os.getenv("ADMIN_USERNAME")
        admin_password = os.getenv("ADMIN_PASSWORD")
        if admin_username and admin_password:
            from passlib.hash import pbkdf2_sha256
            existing = UserModel.query.filter_by(username=admin_username).first()
            if existing:
                if not existing.is_admin:
                    existing.is_admin = True
                    db.session.commit()
            else:
                admin_user = UserModel(
                    username=admin_username,
                    password=pbkdf2_sha256.hash(admin_password),
                    is_admin=True,
                )
                db.session.add(admin_user)
                db.session.commit()

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"}), 200

    @app.route("/config")
    def config():
        return jsonify({"google_client_id": os.getenv("GOOGLE_CLIENT_ID", "")}), 200

    # Serve the frontend at the root URL
    @app.route("/")
    def serve_frontend():
        return app.send_static_file("index.html")

    return app