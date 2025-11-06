from functools import wraps
from typing import Callable, Optional, Dict, Any

from flask import request, g, jsonify

from app.services.firebase_client import verify_id_token, get_user_roles_from_claims


def _extract_bearer_token() -> Optional[str]:
    """
    Extract Bearer token from the Authorization header.

    Header format: Authorization: Bearer <TOKEN>
    """
    authz = request.headers.get("Authorization", "")
    if not authz:
        return None
    parts = authz.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


# PUBLIC_INTERFACE
def firebase_auth_required(func: Callable):
    """Decorator to require a valid Firebase ID token.

    Attaches the following to flask.g on success:
      - g.firebase_claims: dict of decoded token claims
      - g.user_id: authenticated user's UID
      - g.roles: list of role strings (from custom claims or derived flags)

    Returns 401 JSON response when token is missing or invalid.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        token = _extract_bearer_token()
        if not token:
            return jsonify({"error": "Missing Authorization Bearer token"}), 401
        try:
            claims: Dict[str, Any] = verify_id_token(token)
            g.firebase_claims = claims
            g.user_id = claims.get("uid")
            g.roles = get_user_roles_from_claims(claims)
        except Exception as e:
            return jsonify({"error": "Invalid or expired token", "details": str(e)}), 401
        return func(*args, **kwargs)
    return wrapper
