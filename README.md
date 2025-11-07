# attendance-tracker-221712-221722

Backend (firebase_functions) quickstart:
- Required env:
  - JWT_SECRET: secret for signing JWTs (set any non-empty string for local testing)
  - Optional: POSTGRES_* if you want DB-backed features; otherwise endpoints that need DB will return 503.
- Install deps: pip install -r firebase_functions/requirements.txt
- Run: python firebase_functions/run.py
- Verify:
  - GET http://0.0.0.0:3001/ -> {"message":"Healthy"}
  - OpenAPI docs served under prefix configured by OPENAPI_URL_PREFIX (default /docs) via flask-smorest.
  
Notes:
- All blueprints use flask_smorest.Blueprint and are registered on a flask_smorest.Api instance to avoid AttributeError due to mixed blueprint types.
- If you encounter a mismatch, ensure Flask==3.1.* and flask-smorest==0.45.* remain pinned in firebase_functions/requirements.txt.