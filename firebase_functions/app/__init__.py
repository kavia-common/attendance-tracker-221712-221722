import logging
import os
from flask import Flask, jsonify
from flask_cors import CORS

# Load .env if present without failing if missing
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(override=False)
except Exception:
    # Do not fail if python-dotenv is not installed or any error occurs
    pass

# Configure basic logging format early
def _resolve_log_level(value: str) -> int:
    """Resolve LOG_LEVEL from env which may be provided as lower-case string."""
    if isinstance(value, str):
        return getattr(logging, value.upper(), logging.INFO)
    if isinstance(value, int):
        return value
    return logging.INFO

logging.basicConfig(
    level=_resolve_log_level(os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

# Initialize Flask app
app = Flask(__name__)
app.url_map.strict_slashes = False

# Minimal fallback health route to guarantee readiness even if smorest fails
@app.get("/")
def root_health():
    """Fallback health route to ensure container readiness even if extensions fail."""
    return jsonify({"message": "Healthy"}), 200

# Load base config and OpenAPI/Swagger UI settings (used if smorest is available)
app.config["API_TITLE"] = os.getenv("API_TITLE", "My Flask API")
app.config["API_VERSION"] = os.getenv("API_VERSION", "v1")
app.config["OPENAPI_VERSION"] = "3.0.3"
app.config["OPENAPI_URL_PREFIX"] = os.getenv("OPENAPI_URL_PREFIX", "/docs")
app.config["OPENAPI_SWAGGER_UI_PATH"] = ""
app.config["OPENAPI_SWAGGER_UI_URL"] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"

# Enable CORS - allow all origins by default; customize via CORS_ORIGINS env if needed
cors_origins = os.getenv("CORS_ORIGINS", "*")
CORS(app, resources={r"/*": {"origins": cors_origins}})

# Import DB helpers
from .db import init_engine, init_session_factory, test_connection  # noqa: E402

# Try to import flask_smorest and blueprints; if anything fails, we keep the fallback health route active
api = None
try:
    from flask_smorest import Api, Blueprint  # type: ignore

    # Import routes that define smorest.Blueprint instances
    from .routes.health import blp as health_blp  # noqa: E402
    from .auth import blp as auth_blp  # noqa: E402
    from .routes.classes import blp as classes_blp  # noqa: E402

    def _is_smorest_blueprint(obj) -> bool:
        # Guard against non-smorest blueprints; ensures attribute presence
        try:
            return isinstance(obj, Blueprint)
        except Exception:
            return False

    smorest_blueprints = [health_blp, auth_blp, classes_blp]
    only_smorest = all(_is_smorest_blueprint(bp) for bp in smorest_blueprints)

    if only_smorest:
        try:
            api = Api(app)
            for bp in smorest_blueprints:
                api.register_blueprint(bp)
        except AttributeError as e:
            # Handle potential flask-smorest / Flask version mismatch by falling back to direct app registration
            logging.warning("flask-smorest Api registration failed (%s). Falling back to Flask app.register_blueprint.", e)
            for bp in smorest_blueprints:
                try:
                    app.register_blueprint(bp)
                except Exception as re:
                    logging.exception("Failed to register blueprint on app: %s", re)
        except Exception as e:
            # Any other unexpected error; fallback to direct app registration
            logging.warning("Unexpected error registering blueprints via Api (%s). Falling back to Flask app.register_blueprint.", e)
            for bp in smorest_blueprints:
                try:
                    app.register_blueprint(bp)
                except Exception as re:
                    logging.exception("Failed to register blueprint on app: %s", re)
    else:
        # Mixed blueprint types detected; directly register on Flask app for stability
        logging.warning("Detected non-smorest blueprint(s). Registering directly on Flask app.")
        for bp in smorest_blueprints:
            try:
                app.register_blueprint(bp)
            except Exception as re:
                logging.exception("Failed to register blueprint on app: %s", re)

except Exception as exc:
    # If importing flask_smorest or blueprints failed, keep fallback health at '/' so startup never crashes
    logging.warning("Smorest or blueprint import failed; running with fallback health route only. Error: %s", exc)

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
        # Test connection and log the result but never fail startup
        result = test_connection()
        level = logging.INFO if result.get("ok") else logging.WARNING
        logging.log(level, "Startup DB check: %s", result.get("message"))
except Exception as exc:
    # Graceful error handling: do not crash app initialization, just log the error
    logging.exception("Unexpected error during DB initialization: %s", exc)
