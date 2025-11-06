import os
from flask import Flask
from flask_cors import CORS
from flask_smorest import Api
from dotenv import load_dotenv

# Load environment variables if .env is present (non-destructive)
load_dotenv(override=False)

# Import blueprints
from .routes.health import blp as health_blp
from .routes.auth import blp as auth_blp
from .routes.classes import blp as classes_blp
from .routes.attendance import blp as attendance_blp

def _parse_cors_origins(value: str):
    """Parse CORS origins from env; supports '*' or comma-separated list."""
    if not value or value.strip() == "*":
        return "*"
    parts = [p.strip() for p in value.split(",") if p.strip()]
    return parts if parts else "*"

# Initialize app
app = Flask(__name__)
app.url_map.strict_slashes = False

# Secret key (if needed by sessions/extensions)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me-in-prod")

# CORS: allow all origins by default; override via CORS_ALLOW_ORIGINS
cors_origins = _parse_cors_origins(os.getenv("CORS_ALLOW_ORIGINS", "*"))
CORS(app, resources={r"/*": {"origins": cors_origins}})

# OpenAPI / Swagger config
app.config["API_TITLE"] = "Attendance Functions API"
app.config["API_VERSION"] = "v1"
app.config["OPENAPI_VERSION"] = "3.0.3"
# Serve swagger at /docs and spec at /openapi.json for external discovery
app.config["OPENAPI_URL_PREFIX"] = "/docs"
app.config["OPENAPI_SWAGGER_UI_PATH"] = ""
app.config["OPENAPI_SWAGGER_UI_URL"] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"
app.config["OPENAPI_JSON_PATH"] = "openapi.json"

# Smorest API
api = Api(app)

# Register blueprints
api.register_blueprint(health_blp)
api.register_blueprint(auth_blp)
api.register_blueprint(classes_blp)
api.register_blueprint(attendance_blp)
