# attendance-tracker-221712-221722

Backend (firebase_functions) quickstart:
- Required env:
  - JWT_SECRET: secret for signing JWTs (set any non-empty string for local testing)
  - Optional: POSTGRES_* if you want DB-backed features; otherwise endpoints that need DB will return 503.
- Install deps: pip install -r firebase_functions/requirements.txt
- Run: python firebase_functions/run.py
- Verify:
  - GET http://0.0.0.0:3001/ -> {"message":"Healthy"}
  - GET http://0.0.0.0:3001/healthz -> {"message":"Healthy"}
  - OpenAPI docs served under prefix configured by OPENAPI_URL_PREFIX (default /docs) via flask-smorest.

Port and readiness:
- The app binds to host 0.0.0.0 and port taken from PORT environment variable if set (e.g., platform-provided 3010), otherwise defaults to 3001.
- Any FLASK_RUN_HOST/FLASK_RUN_PORT settings are ignored by the entrypoint; do not rely on flask run. Use `python firebase_functions/run.py`.
- Readiness endpoints available at "/" and "/healthz".

Startup resilience:
- The app now loads .env if present (via python-dotenv) but does not fail if missing.
- A minimal fallback health route is always registered at "/" so the container becomes ready even if flask-smorest fails to initialize.
- Blueprints are registered via flask_smorest.Api when possible. If an AttributeError or version mismatch occurs, the app falls back to app.register_blueprint for stability.
- The entrypoint binds to 0.0.0.0 on PORT (default 3001), with safe FLASK_ENV defaults, and without the reloader for containerized runs.

Notes:
- All blueprints use flask_smorest.Blueprint and are registered on a flask_smorest.Api instance to avoid AttributeError due to mixed blueprint types when available.
- If you encounter a mismatch, ensure Flask==3.1.* and flask-smorest==0.45.* remain pinned in firebase_functions/requirements.txt.