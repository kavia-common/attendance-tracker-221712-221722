"""
Application entrypoint for firebase_functions container.

This file ensures the Flask app starts on 0.0.0.0:3001 so the container becomes healthy.
It supports two modes of running:
- Direct python execution: python run.py
- Flask CLI with FLASK_APP=run.py (it will still bind correctly if FLASK_RUN_HOST/FLASK_RUN_PORT are set)

PUBLIC_INTERFACE
"""
import os
from app import app

def _get_host_port():
    """
    Determine host and port to bind to.
    Priority:
      1. Environment variables HOST/PORT if present
      2. Defaults: 0.0.0.0:3001
    """
    host = os.getenv("HOST", os.getenv("FLASK_RUN_HOST", "0.0.0.0"))
    try:
        port = int(os.getenv("PORT", os.getenv("FLASK_RUN_PORT", "3001")))
    except ValueError:
        port = 3001
    return host, port

if __name__ == "__main__":
    host, port = _get_host_port()
    # Disable reloader in container environments to avoid double-start
    app.run(host=host, port=port, debug=os.getenv("FLASK_DEBUG", "0") == "1", use_reloader=False)
