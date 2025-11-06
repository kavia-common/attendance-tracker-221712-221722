from flask import Flask
from flask_cors import CORS
from flask_smorest import Api

# Import blueprints
from .routes.health import blp as health_blp
from .routes.auth import blp as auth_blp
from .routes.classes import blp as classes_blp
from .routes.attendance import blp as attendance_blp

# Initialize app
app = Flask(__name__)
app.url_map.strict_slashes = False

# CORS: allow all origins for demo; in production, restrict to frontend domain(s)
CORS(app, resources={r"/*": {"origins": "*"}})

# OpenAPI / Swagger config
app.config["API_TITLE"] = "Attendance Functions API"
app.config["API_VERSION"] = "v1"
app.config["OPENAPI_VERSION"] = "3.0.3"
app.config["OPENAPI_URL_PREFIX"] = "/docs"
app.config["OPENAPI_SWAGGER_UI_PATH"] = ""
app.config["OPENAPI_SWAGGER_UI_URL"] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"

# Smorest API
api = Api(app)

# Register blueprints
api.register_blueprint(health_blp)
api.register_blueprint(auth_blp)
api.register_blueprint(classes_blp)
api.register_blueprint(attendance_blp)
