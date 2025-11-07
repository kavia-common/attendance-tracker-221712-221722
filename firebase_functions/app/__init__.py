import logging
import os
from flask import Flask
from flask_cors import CORS
from flask_smorest import Api

# Import routes
from .routes.health import blp as health_blp
from .auth import blp as auth_blp

# Import DB helpers
from .db import init_engine, init_session_factory, test_connection

# Configure basic logging format early
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s"
)

# Initialize Flask app
app = Flask(__name__)
app.url_map.strict_slashes = False

# Load base config and OpenAPI/Swagger UI settings
app.config["API_TITLE"] = os.getenv("API_TITLE", "My Flask API")
app.config["API_VERSION"] = os.getenv("API_VERSION", "v1")
app.config["OPENAPI_VERSION"] = "3.0.3"
app.config["OPENAPI_URL_PREFIX"] = os.getenv("OPENAPI_URL_PREFIX", "/docs")
app.config["OPENAPI_SWAGGER_UI_PATH"] = ""
app.config["OPENAPI_SWAGGER_UI_URL"] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"

# Enable CORS - allow all origins by default; customize via CORS_ORIGINS env if needed
cors_origins = os.getenv("CORS_ORIGINS", "*")
CORS(app, resources={r"/*": {"origins": cors_origins}})

# Initialize API
api = Api(app)

# Register blueprints
api.register_blueprint(health_blp)
api.register_blueprint(auth_blp)

# Placeholder: register additional blueprints here as the app grows
# from .routes.students import blp as students_blp
# api.register_blueprint(students_blp)

# Initialize database engine and session factory at startup and test connectivity
try:
    engine = init_engine(
        echo=os.getenv("SQL_ECHO", "false").lower() == "true",
        pool_pre_ping=True,
        pool_size=int(os.getenv("SQL_POOL_SIZE", "5")),
        max_overflow=int(os.getenv("SQL_MAX_OVERFLOW", "10")),
    )
    if engine is None:
        logging.warning("Database engine not initialized. Check POSTGRES_* environment variables.")
    else:
        # Initialize session factory
        init_session_factory()

        # Test connection and log the result
        result = test_connection()
        level = logging.INFO if result.get("ok") else logging.WARNING
        logging.log(level, "Startup DB check: %s", result.get("message"))
except Exception as exc:
    # Graceful error handling: do not crash app initialization, just log the error
    logging.exception("Unexpected error during DB initialization: %s", exc)
