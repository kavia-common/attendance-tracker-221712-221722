"""
Application entrypoint for firebase_functions container.

This file ensures the Flask app starts on 0.0.0.0:3001 so the container becomes healthy.
It supports two modes of running:
- Direct python execution: python run.py
- Flask CLI with FLASK_APP=run.py (it will still bind correctly if FLASK_RUN_HOST/FLASK_RUN_PORT are set)

PUBLIC_INTERFACE
"""
import os

# Load .env if present, but never fail if missing
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(override=False)
except Exception:
    pass

# Safe default for FLASK_ENV if not provided
os.environ.setdefault("FLASK_ENV", "production")

from app import app  # noqa: E402


def _get_host_port():
    """
    Determine host and port to bind to.
    Priority:
      1. env PORT if present (single source of truth provided by platform)
      2. Fallback to 3001

    Host always binds to 0.0.0.0 to be reachable from outside the container.
    """
    # Always bind to all interfaces in containerized environments
    host = "0.0.0.0"

    # Single source of truth: PORT env (platform may inject e.g., 3010)
    try:
        port_env = os.getenv("PORT")
        port = int(port_env) if port_env is not None else 3001
    except (TypeError, ValueError):
        port = 3001

    # Clear potential Flask CLI variables to avoid confusion if someone invokes flask run
    # This file uses app.run() directly, so these shouldn't matter, but clearing for safety.
    os.environ.pop("FLASK_RUN_PORT", None)
    os.environ.pop("FLASK_RUN_HOST", None)

    return host, port


if __name__ == "__main__":
    host, port = _get_host_port()
    # Explicit startup logging for observability
    try:
        import logging  # local import after LOG_LEVEL config in app.__init__
        logging.getLogger(__name__).info("Starting firebase_functions on %s:%s", host, port)
    except Exception:
        pass

    # Disable reloader in container environments to avoid double-start
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    # Bind to the resolved host/port
    app.run(host=host, port=port, debug=debug, use_reloader=False)
