import os
import datetime
import logging
from dataclasses import dataclass
from functools import wraps
from typing import Any, Dict, Optional, Tuple

from flask import Blueprint, request, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash
import jwt

# In-memory user store for demo purposes.
# Replace with DB integration later.
# Structure: { email: {"password_hash": str, "role": str, "created_at": iso } }
_USERS: Dict[str, Dict[str, Any]] = {}

# Configure Blueprint
blp = Blueprint(
    "Auth",
    __name__,
    url_prefix="/auth",
    description="Authentication routes for signup, login, and JWT issuance",
)

# Helpers and configurations
@dataclass
class JwtConfig:
    secret: str
    algo: str
    exp_minutes: int

    @staticmethod
    def from_env() -> "JwtConfig":
        """
        Load JWT config from environment variables.
        Requires JWT_SECRET and TOKEN_EXP_MIN (default 60).
        """
        secret = os.getenv("JWT_SECRET")
        if not secret:
            raise RuntimeError("Missing JWT_SECRET environment variable.")
        exp = int(os.getenv("TOKEN_EXP_MIN", "60"))
        return JwtConfig(secret=secret, algo="HS256", exp_minutes=exp)


def _issue_token(sub: str, role: str, extra: Optional[Dict[str, Any]] = None) -> str:
    """
    Internal helper to issue a JWT token.
    """
    cfg = JwtConfig.from_env()
    now = datetime.datetime.utcnow()
    payload: Dict[str, Any] = {
        "sub": sub,
        "role": role,
        "iat": now,
        "nbf": now,
        "exp": now + datetime.timedelta(minutes=cfg.exp_minutes),
    }
    if extra:
        payload.update(extra)
    token = jwt.encode(payload, cfg.secret, algorithm=cfg.algo)
    # PyJWT returns str in v2+
    return token


def _verify_token(token: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Verify JWT token and return (is_valid, payload, error_message).
    """
    try:
        cfg = JwtConfig.from_env()
        payload = jwt.decode(token, cfg.secret, algorithms=[cfg.algo])
        return True, payload, None
    except jwt.ExpiredSignatureError:
        return False, None, "Token has expired."
    except jwt.InvalidTokenError as exc:
        return False, None, f"Invalid token: {exc}"
    except Exception as exc:
        logging.exception("Unexpected error verifying token: %s", exc)
        return False, None, "Unexpected token verification error."


# PUBLIC_INTERFACE
def jwt_required(f):
    """Decorator to enforce that a valid JWT is present in the Authorization header as Bearer token."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"message": "Missing or malformed Authorization header."}), 401
        token = auth_header.split(" ", 1)[1].strip()
        ok, payload, err = _verify_token(token)
        if not ok or not payload:
            return jsonify({"message": err or "Unauthorized"}), 401
        # Attach identity to request context
        g.jwt = payload
        g.user_email = payload.get("sub")
        g.user_role = payload.get("role")
        return f(*args, **kwargs)
    return wrapper


# PUBLIC_INTERFACE
def roles_required(*roles: str):
    """Decorator to restrict access to users with any of the specified roles."""
    def decorator(f):
        @wraps(f)
        @jwt_required
        def wrapper(*args, **kwargs):
            role = getattr(g, "user_role", None)
            if role not in roles:
                return jsonify({"message": "Forbidden: insufficient role."}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator


def _validate_signup_payload(data: Dict[str, Any]) -> Optional[str]:
    if not isinstance(data, dict):
        return "Invalid JSON."
    if not data.get("email"):
        return "Email is required."
    if not data.get("password"):
        return "Password is required."
    if not data.get("role"):
        return "Role is required."
    if data["role"] not in ("student", "teacher", "admin"):
        return "Role must be one of: student, teacher, admin."
    return None


def _validate_login_payload(data: Dict[str, Any]) -> Optional[str]:
    if not isinstance(data, dict):
        return "Invalid JSON."
    if not data.get("email"):
        return "Email is required."
    if not data.get("password"):
        return "Password is required."
    return None


@blp.route("/signup", methods=["POST"])
def signup():
    """
    Signup endpoint to create a user and return a JWT.

    Request JSON:
      - email: string (required)
      - password: string (required)
      - role: string in ["student","teacher","admin"] (required)

    Returns:
      { "token": "<jwt>", "expires_in": minutes, "role": role, "email": email }
    """
    try:
        data = request.get_json(silent=True) or {}
        error = _validate_signup_payload(data)
        if error:
            return jsonify({"message": error}), 400

        email = data["email"].strip().lower()
        if email in _USERS:
            return jsonify({"message": "User already exists."}), 409

        password_hash = generate_password_hash(data["password"])
        role = data["role"]
        _USERS[email] = {
            "password_hash": password_hash,
            "role": role,
            "created_at": datetime.datetime.utcnow().isoformat(),
        }

        token = _issue_token(sub=email, role=role)
        exp_min = JwtConfig.from_env().exp_minutes
        return jsonify({
            "token": token,
            "expires_in": exp_min,
            "role": role,
            "email": email,
        }), 201
    except RuntimeError as cfg_err:
        return jsonify({"message": str(cfg_err)}), 500
    except Exception as exc:
        logging.exception("Signup failed: %s", exc)
        return jsonify({"message": "Internal server error"}), 500


@blp.route("/login", methods=["POST"])
def login():
    """
    Login endpoint to authenticate a user and return a JWT.

    Request JSON:
      - email: string (required)
      - password: string (required)

    Returns:
      { "token": "<jwt>", "expires_in": minutes, "role": role, "email": email }
    """
    try:
        data = request.get_json(silent=True) or {}
        error = _validate_login_payload(data)
        if error:
            return jsonify({"message": error}), 400

        email = data["email"].strip().lower()
        user = _USERS.get(email)
        if not user:
            return jsonify({"message": "Invalid credentials."}), 401
        if not check_password_hash(user["password_hash"], data["password"]):
            return jsonify({"message": "Invalid credentials."}), 401

        token = _issue_token(sub=email, role=user["role"])
        exp_min = JwtConfig.from_env().exp_minutes
        return jsonify({
            "token": token,
            "expires_in": exp_min,
            "role": user["role"],
            "email": email,
        }), 200
    except RuntimeError as cfg_err:
        return jsonify({"message": str(cfg_err)}), 500
    except Exception as exc:
        logging.exception("Login failed: %s", exc)
        return jsonify({"message": "Internal server error"}), 500


@blp.route("/me", methods=["GET"])
@jwt_required
def me():
    """
    Fetch current user info from JWT.
    Requires Authorization: Bearer <token>
    """
    return jsonify({
        "email": getattr(g, "user_email", None),
        "role": getattr(g, "user_role", None),
        "jwt": getattr(g, "jwt", {}),
    }), 200


@blp.route("/admin/ping", methods=["GET"])
@roles_required("admin")
def admin_ping():
    """
    Example protected route requiring 'admin' role.
    """
    return jsonify({"message": "admin pong"}), 200
