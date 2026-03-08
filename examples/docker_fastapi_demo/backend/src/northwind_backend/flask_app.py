from __future__ import annotations

from flask import Flask, send_file
from flask_cors import CORS
from safrs import SafrsApi

from .config import get_settings
from .db import create_runtime
from .models import EXPOSED_MODELS, EXPOSED_RESOURCE_NAMES


def create_flask_app() -> Flask:
    settings = get_settings()
    runtime = create_runtime(settings.db_path)

    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False
    CORS(app)

    with app.app_context():
        api = SafrsApi(
            app,
            host=settings.swagger_host,
            port=settings.swagger_port,
            prefix=settings.api_prefix,
            app_db=runtime.wrapper,
        )
        for model in EXPOSED_MODELS:
            api.expose_object(model)

    app.safrs_api = api
    app.safrs_runtime = runtime

    @app.teardown_request
    def _remove_session(_exc):
        runtime.session.remove()

    @app.get("/")
    def index() -> dict[str, object]:
        return {
            "project": "northwind",
            "framework": "flask",
            "api_root": settings.api_prefix,
            "admin_yaml": "/ui/admin/admin.yaml",
            "resources": EXPOSED_RESOURCE_NAMES,
        }

    @app.get("/healthz")
    def healthz() -> dict[str, object]:
        return {
            "status": "ok",
            "framework": "flask",
            "port": settings.port,
            "api_prefix": settings.api_prefix,
        }

    @app.get("/ui/admin/admin.yaml")
    def admin_yaml():
        return send_file(settings.admin_yaml_path, mimetype="text/yaml")

    return app
