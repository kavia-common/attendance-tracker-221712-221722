from flask_smorest import Blueprint
from flask.views import MethodView

blp = Blueprint("Healt Check", "health check", url_prefix="/", description="Health check route")


@blp.route("/")
class HealthCheck(MethodView):
    # PUBLIC_INTERFACE
    def get(self):
        """Simple health check endpoint."""
        return {"message": "Healthy"}
