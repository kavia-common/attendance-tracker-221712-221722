from flask_smorest import Blueprint
from flask.views import MethodView
from flask import g

from app.middleware.auth import firebase_auth_required

blp = Blueprint(
    "Auth",
    "auth",
    url_prefix="/auth",
    description="Authentication utilities and verification endpoints",
)


@blp.route("/verify")
class VerifyToken(MethodView):
    """Verify Firebase Auth token endpoint.

    GET /auth/verify
    Requires Authorization: Bearer <id_token> header.

    Returns:
        200: JSON with user_id and roles if token is valid.
        401: JSON error if token is missing/invalid.
    """
    decorators = [firebase_auth_required]

    def get(self):
        return {
            "message": "Token valid",
            "user_id": g.user_id,
            "roles": g.roles,
            "claims": g.firebase_claims,
        }, 200
