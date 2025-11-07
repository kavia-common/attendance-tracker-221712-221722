from flask_smorest import Blueprint
from flask.views import MethodView

# Simple health blueprint mounted at root. Avoid spaces in blueprint name for cleaner docs/tagging.
blp = Blueprint("Health", __name__, url_prefix="/")

# PUBLIC_INTERFACE
@blp.route("/")
class HealthCheck(MethodView):
    """Health check endpoint. Returns 200 with a simple JSON payload to signal readiness."""
    def get(self):
        return {"message": "Healthy"}, 200
