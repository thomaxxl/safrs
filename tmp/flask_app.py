#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
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

from models import API_PREFIX, Base, DESCRIPTION, EXPOSED_MODELS, SAFRSDBWrapper, TMP_DIR, build_seed_payload, create_session, seed_data


def _should_reset_tmp_db() -> bool:
    value = os.environ.get("SAFRS_TMP_RESET_DB", "1").strip().lower()
    return value not in ("0", "false", "no")


def _resolve_db_dir() -> Path:
    env_db_dir = os.environ.get("SAFRS_TMP_DB_DIR", "").strip()
    if not env_db_dir:
        return TMP_DIR
    db_dir = Path(env_db_dir).expanduser()
    if not db_dir.is_absolute():
        db_dir = TMP_DIR / db_dir
    return db_dir


def _resolve_db_name(port: int, explicit_db_name: str | None = None) -> str:
    if explicit_db_name:
        return explicit_db_name
    env_db_name = os.environ.get("SAFRS_TMP_DB", "").strip()
    if env_db_name:
        return env_db_name
    return f"tmp_flask_{port}.db"


def _resolve_db_path(port: int, explicit_db_name: str | None = None) -> Path:
    resolved_db_name = _resolve_db_name(port=port, explicit_db_name=explicit_db_name)
    db_name_path = Path(resolved_db_name).expanduser()
    if db_name_path.is_absolute():
        return db_name_path
    return _resolve_db_dir() / db_name_path


def create_app(host: str = "127.0.0.1", port: int = 5000, db_name: str | None = None) -> Flask:
    db_path = _resolve_db_path(port=port, explicit_db_name=db_name)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if _should_reset_tmp_db() and db_path.exists():
        db_path.unlink()

    Session = create_session(db_path)
    wrapper = SAFRSDBWrapper(Session, Base)
    setattr(safrs, "DB", wrapper)
    seed_data(Session)

    app = Flask("safrs-tmp-flask")
    app.secret_key = os.environ.get("SAFRS_TMP_SECRET_KEY", os.urandom(16).hex())
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

    @app.route("/seed", methods=["GET"])
    def seed() -> Any:
        return jsonify(build_seed_payload(Session))

    return app


if __name__ == "__main__":
    bind_host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    bind_port = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    flask_app = create_app(host=bind_host, port=bind_port)
    flask_app.run(host=bind_host, port=bind_port, threaded=False)
