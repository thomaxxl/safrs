#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import safrs
from flask import Flask, jsonify, redirect
from flask_cors import CORS
from safrs import SAFRSAPI

from models import API_PREFIX, Base, DESCRIPTION, EXPOSED_MODELS, SAFRSDBWrapper, TMP_DIR, create_session, seed_data


def create_app(host: str = "127.0.0.1", port: int = 5000, db_name: str = "tmp_flask.db") -> Flask:
    db_path = TMP_DIR / db_name
    Session = create_session(db_path)
    seed_data(Session)

    wrapper = SAFRSDBWrapper(Session, Base)
    setattr(safrs, "DB", wrapper)

    app = Flask("safrs-tmp-flask")
    app.secret_key = "tmp-not-so-secret"
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    with app.app_context():
        api = SAFRSAPI(
            app,
            app_db=wrapper,
            host=host,
            port=port,
            prefix=API_PREFIX,
            description=DESCRIPTION,
            custom_swagger={"info": {"title": "SAFRS tmp Flask demo"}},
        )
        for model in EXPOSED_MODELS:
            api.expose_object(model)

    @app.teardown_appcontext
    def remove_session(_exc: Any) -> None:
        Session.remove()

    @app.route("/", methods=["GET"])
    def root() -> Any:
        return redirect(API_PREFIX)

    @app.route("/health", methods=["GET"])
    def health() -> Any:
        return jsonify({"ok": True, "framework": "flask", "db": str(db_path), "api_prefix": API_PREFIX})

    return app


if __name__ == "__main__":
    bind_host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    bind_port = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    flask_app = create_app(host=bind_host, port=bind_port)
    flask_app.run(host=bind_host, port=bind_port, threaded=False)
