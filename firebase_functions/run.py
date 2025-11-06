import os

from dotenv import load_dotenv

from app import app
from app.db import ensure_schema

# Load environment variables if .env is present
load_dotenv(override=False)

# Ensure database schema is created at startup (idempotent)
try:
    ensure_schema()
except Exception as e:
    # Don't crash local dev if DB is not yet available; log to console.
    print(f"Warning: could not ensure schema at startup: {e}")

if __name__ == "__main__":
    # Bind to 0.0.0.0 for containerized environments and use PORT if provided
    port = int(os.getenv("PORT", "3001"))
    app.run(host="0.0.0.0", port=port)
