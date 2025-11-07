import json
import os
from app import app  # import your Flask app; api may not exist if smorest fallback engaged

openapi_spec = None
try:
    from app import api  # type: ignore  # api may be None
except Exception:
    api = None  # type: ignore

with app.app_context():
    if api is not None and getattr(api, "spec", None) is not None:
        # flask-smorest stores the spec in api.spec
        openapi_spec = api.spec.to_dict()
    else:
        # Minimal fallback spec if smorest Api is not available
        openapi_spec = {
            "openapi": "3.0.3",
            "info": {"title": app.config.get("API_TITLE", "My Flask API"), "version": app.config.get("API_VERSION", "v1")},
            "paths": {
                "/": {
                    "get": {
                        "responses": {"200": {"description": "Healthy"}},
                        "tags": ["Health"],
                    }
                }
            },
            "tags": [{"name": "Health", "description": ""}],
            "components": {},
        }

    output_dir = "interfaces"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "openapi.json")

    with open(output_path, "w") as f:
        json.dump(openapi_spec, f, indent=2)
