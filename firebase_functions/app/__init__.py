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


# PUBLIC_INTERFACE
def create_app():
    """Create and configure the Flask application.

    This factory builds the app, attaches unconditional health endpoints at "/" and "/healthz",
    attempts to register smorest blueprints when available, and performs non-fatal DB initialization.
    It does not start the server; run.py will call app.run().
    """
    app = Flask(__name__)
    app.url_map.strict_slashes = False

    # Log intended bind target (for observability when runners just import app)
    try:
        _host = "0.0.0.0"
        _port_env = os.getenv("PORT")
        _port = int(_port_env) if _port_env is not None and _port_env.isdigit() else 3001
        logging.getLogger("startup").info(
            "App initialized. Intended bind host=%s port=%s (PORT=%s)", _host, _port, _port_env
        )
    except Exception:
        pass

    # Unconditional health endpoints (not behind smorest) so readiness always works
    @app.get("/")
    def root_health():
        """Fallback health route to ensure container readiness even if extensions fail."""
        return jsonify({"message": "Healthy"}), 200

    @app.get("/healthz")
    def healthz():
        """Simple healthz endpoint mirroring root health for readiness probes."""
        return jsonify({"message": "Healthy"}), 200

    # Base config and OpenAPI/Swagger UI settings (used if smorest is available)
    app.config["API_TITLE"] = os.getenv("API_TITLE", "My Flask API")
    app.config["API_VERSION"] = os.getenv("API_VERSION", "v1")
    app.config["OPENAPI_VERSION"] = "3.0.3"
    app.config["OPENAPI_URL_PREFIX"] = os.getenv("OPENAPI_URL_PREFIX", "/docs")
    app.config["OPENAPI_SWAGGER_UI_PATH"] = ""
    app.config["OPENAPI_SWAGGER_UI_URL"] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"

    # Expose a resilient OpenAPI JSON regardless of smorest availability
    @app.get("/openapi.json")
    def openapi_json():
        """Serve OpenAPI specification JSON. Falls back to minimal spec if smorest is unavailable."""
        try:
            api = getattr(app, "api", None)
            if api is not None and getattr(api, "spec", None) is not None:
                return api.spec.to_dict(), 200
        except Exception:
            # ignore and fall back
            pass
        # Fallback minimal spec that documents health endpoints
        return {
            "openapi": app.config["OPENAPI_VERSION"],
            "info": {"title": app.config["API_TITLE"], "version": app.config["API_VERSION"]},
            "paths": {
                "/": {"get": {"responses": {"200": {"description": "Healthy"}}, "tags": ["Health"]}},
                "/healthz": {"get": {"responses": {"200": {"description": "Healthy"}}, "tags": ["Health"]}},
            },
            "tags": [{"name": "Health", "description": ""}],
            "components": {},
        }, 200

    # Provide a minimal fallback for /docs when smorest UI is unavailable
    @app.get("/docs")
    def docs_fallback():
        """Serve a minimal docs page or let smorest handle if registered."""
        # If smorest registered UI under this path, it will take precedence; otherwise return minimal HTML
        return (
            "<!DOCTYPE html>"
            "<html><head><title>API Docs</title></head>"
            "<body>"
            "<h1>API Documentation</h1>"
            "<p>If the Swagger UI is not shown by flask-smorest, you can download the OpenAPI spec: "
            '<a href="/openapi.json">/openapi.json</a></p>'
            "<p>This instance serves Swagger UI from CDN when flask-smorest is active.</p>"
            "</body></html>",
            200,
            {"Content-Type": "text/html; charset=utf-8"},
        )

    # Enable CORS - allow all origins by default; customize via CORS_ORIGINS env if needed
    cors_origins = os.getenv("CORS_ORIGINS", "*")
    CORS(app, resources={r"/*": {"origins": cors_origins}})

    # Lazy import DB helpers inside factory to avoid import-time side effects
    try:
        from .db import init_engine, init_session_factory, test_connection  # type: ignore

        # Initialize database engine and session factory at startup and test connectivity,
        # but never fail startup if configuration is missing or connection fails.
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
                init_session_factory()
                result = test_connection()
                level = logging.INFO if result.get("ok") else logging.WARNING
                logging.log(level, "Startup DB check: %s", result.get("message"))
        except Exception as exc:
            logging.exception("Unexpected error during DB initialization: %s", exc)
    except Exception as exc:
        # If DB module cannot be imported, continue without DB
        logging.warning("DB helpers import failed; continuing without DB. Error: %s", exc)

    # Try to import flask_smorest and blueprints; if anything fails, keep fallback health routes active
    app.api = None  # type: ignore[attr-defined]
    try:
        from flask_smorest import Api, Blueprint  # type: ignore

        # Import routes that define smorest.Blueprint instances
        from .routes.health import blp as health_blp  # noqa: E402
        from .auth import blp as auth_blp  # noqa: E402
        from .routes.classes import blp as classes_blp  # noqa: E402

        def _is_smorest_blueprint(obj) -> bool:
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
                app.api = api  # type: ignore[attr-defined]
            except AttributeError as e:
                logging.warning(
                    "flask-smorest Api registration failed (%s). Falling back to Flask app.register_blueprint.", e
                )
                for bp in smorest_blueprints:
                    try:
                        app.register_blueprint(bp)
                    except Exception as re:
                        logging.exception("Failed to register blueprint on app: %s", re)
            except Exception as e:
                logging.warning(
                    "Unexpected error registering blueprints via Api (%s). Falling back to Flask app.register_blueprint.", e
                )
                for bp in smorest_blueprints:
                    try:
                        app.register_blueprint(bp)
                    except Exception as re:
                        logging.exception("Failed to register blueprint on app: %s", re)
        else:
            logging.warning("Detected non-smorest blueprint(s). Registering directly on Flask app.")
            for bp in smorest_blueprints:
                try:
                    app.register_blueprint(bp)
                except Exception as re:
                    logging.exception("Failed to register blueprint on app: %s", re)
    except Exception as exc:
        logging.warning(
            "Smorest or blueprint import failed; running with fallback health routes only. Error: %s", exc
        )

    return app


# Backward compatibility: create a module-level app instance for scripts that expect `from app import app`.
# This does not start the server; it simply constructs the application once.
app = create_app()
