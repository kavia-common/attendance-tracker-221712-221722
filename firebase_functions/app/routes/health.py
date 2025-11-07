from flask_smorest import Blueprint
from flask.views import MethodView

# Use proper import_name (__name__) and remove unsupported description kwarg
blp = Blueprint("Health Check", __name__, url_prefix="/")


@blp.route("/")
class HealthCheck(MethodView):
    def get(self):
        return {"message": "Healthy"}
