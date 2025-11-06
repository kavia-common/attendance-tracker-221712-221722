from flask import request
from flask.views import MethodView
from flask_smorest import Blueprint
from marshmallow import Schema, fields, validate

from ..models import get_user_by_email, upsert_user


class UserSchema(Schema):
    email = fields.Email(required=True, description="Unique email for login")
    name = fields.String(required=True, description="Display name")
    role = fields.String(required=True, validate=validate.OneOf(["teacher", "student"]), description="Role of user")


blp = Blueprint(
    "Auth",
    "auth",
    url_prefix="/auth",
    description="Authentication endpoints (simple email-based for demo)",
)


@blp.route("/login")
class Login(MethodView):
    """Simple email-based login/upsert."""

    # PUBLIC_INTERFACE
    def post(self):
        """
        Authenticate or create a user.
        Returns the user object.
        """
        payload = request.get_json(force=True, silent=True) or {}
        errors = UserSchema().validate(payload)
        if errors:
            return {"errors": errors}, 400

        user = upsert_user(payload["email"], payload["name"], payload["role"])
        return {"user": user}, 200


@blp.route("/profile")
class Profile(MethodView):
    """Get user profile by email."""

    # PUBLIC_INTERFACE
    def get(self):
        """
        Get user by email.
        Query param: email
        """
        email = request.args.get("email")
        if not email:
            return {"message": "Email required"}, 400
        user = get_user_by_email(email)
        if not user:
            return {"message": "Not found"}, 404
        return {"user": user}, 200
