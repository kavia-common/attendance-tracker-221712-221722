from flask import Flask
from flask_cors import CORS
from flask_smorest import Api

from .routes.health import blp as health_blp
from .routes.auth import blp as auth_blp
from .services.firebase_client import initialize_firebase_app

# Initialize Flask app and API docs
app = Flask(__name__)
app.url_map.strict_slashes = False

# Allow all origins by default (can be restricted via env later)
CORS(app, resources={r"/*": {"origins": "*"}})

# OpenAPI / Swagger configuration
app.config["API_TITLE"] = "My Flask API"
app.config["API_VERSION"] = "v1"
app.config["OPENAPI_VERSION"] = "3.0.3"
app.config["OPENAPI_URL_PREFIX"] = "/docs"
app.config["OPENAPI_SWAGGER_UI_PATH"] = ""
app.config["OPENAPI_SWAGGER_UI_URL"] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"

# Initialize Firebase Admin at startup so errors surface early
try:
    initialize_firebase_app()
except Exception as e:
    # Do not crash app initialization to allow health checks; clients will still get 401s at auth endpoints.
    # Log the error and continue; proper credentials must be provided via env variables.
    app.logger.warning(f"Firebase Admin initialization skipped/failed: {e}")

# Register API with blueprints
api = Api(app, spec_kwargs={"info": {"description": "Backend for attendance tracker with Firebase Auth middleware."}})
api.register_blueprint(health_blp)
api.register_blueprint(auth_blp)
