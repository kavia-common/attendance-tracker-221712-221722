import os
import json
import logging
from typing import Optional, Dict, Any

import firebase_admin
from firebase_admin import credentials, auth

# Module-level logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _load_credentials_from_env() -> Optional[credentials.Certificate]:
    """
    Try to obtain Firebase Admin credentials from environment variables.

    Priority:
    1) FIREBASE_SERVICE_ACCOUNT_JSON: JSON string with service account.
    2) GOOGLE_APPLICATION_CREDENTIALS: Path to service account JSON file.

    Returns:
        credentials.Certificate or None if not available.
    """
    # Try JSON string first
    svc_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    if svc_json:
        try:
            data = json.loads(svc_json)
            logger.info("Initializing Firebase Admin using FIREBASE_SERVICE_ACCOUNT_JSON.")
            return credentials.Certificate(data)
        except json.JSONDecodeError as e:
            logger.error("Invalid FIREBASE_SERVICE_ACCOUNT_JSON: %s", e)

    # Fall back to file path
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if cred_path and os.path.isfile(cred_path):
        logger.info("Initializing Firebase Admin using GOOGLE_APPLICATION_CREDENTIALS file.")
        return credentials.Certificate(cred_path)

    logger.warning(
        "No Firebase service account found. Set FIREBASE_SERVICE_ACCOUNT_JSON or GOOGLE_APPLICATION_CREDENTIALS."
    )
    return None


def initialize_firebase_app() -> firebase_admin.App:
    """
    Initialize and return the global Firebase Admin app if not already initialized.

    Returns:
        firebase_admin.App: Initialized Firebase Admin app instance.

    Raises:
        RuntimeError: If credentials are not available.
    """
    if firebase_admin._apps:
        # Already initialized
        return firebase_admin.get_app()

    cred = _load_credentials_from_env()
    if not cred:
        raise RuntimeError(
            "Firebase Admin credentials not found. Provide either FIREBASE_SERVICE_ACCOUNT_JSON "
            "or GOOGLE_APPLICATION_CREDENTIALS."
        )

    app = firebase_admin.initialize_app(cred)
    logger.info("Firebase Admin initialized.")
    return app


# PUBLIC_INTERFACE
def verify_id_token(id_token: str) -> Dict[str, Any]:
    """Verify a Firebase ID token and return the decoded claims.

    This function requires Firebase Admin to be initialized. Use FIREBASE_SERVICE_ACCOUNT_JSON (JSON string)
    or GOOGLE_APPLICATION_CREDENTIALS (file path) environment variables to provide credentials.

    Args:
        id_token: The Firebase Authentication ID token string (from Authorization: Bearer <token>)

    Returns:
        dict: Decoded token claims including 'uid' and any custom claims.

    Raises:
        ValueError: If token is missing or invalid.
        firebase_admin._auth_utils.InvalidIdTokenError: For invalid tokens.
        firebase_admin._auth_utils.ExpiredIdTokenError: For expired tokens.
    """
    initialize_firebase_app()
    if not id_token:
        raise ValueError("ID token is required")
    decoded = auth.verify_id_token(id_token)
    return decoded


# PUBLIC_INTERFACE
def get_user_roles_from_claims(claims: Dict[str, Any]) -> Any:
    """Extract roles from token claims if present.

    Args:
        claims: Decoded Firebase ID token claims.

    Returns:
        Any: The 'roles' field from custom claims, or [] when not set.
    """
    # Firebase custom claims are usually under the claim keys directly.
    # For example {'admin': True} or {'roles': ['teacher']}. We prioritize 'roles'.
    roles = claims.get("roles")
    if roles is None:
        # Fallback: try some common custom claim patterns
        # Convert boolean admin/editor flags into a list if present
        computed_roles = []
        for key in ("admin", "teacher", "student", "editor", "viewer"):
            if claims.get(key) is True:
                computed_roles.append(key)
        roles = computed_roles
    return roles or []
