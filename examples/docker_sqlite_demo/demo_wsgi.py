"""Gunicorn WSGI entrypoint (factory) for the sqlite-only demo.

This mirrors the `app:run_app()` pattern used in `thomaxxl/safrs-example`,
but runs the pythonanywhere-style demo using SQLite only (no DB containers).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from demo_app import build_sqlite_uri, create_app, start_api

_app = None


def run_app():
    """Gunicorn factory."""
    global _app
    if _app is not None:
        return _app

    sqlite_path = os.environ.get("SQLITE_PATH", "/data/safrs_demo.db")
    swagger_host = os.environ.get("SWAGGER_HOST", "localhost")
    swagger_port_raw = os.environ.get("SWAGGER_PORT")
    swagger_port: Optional[int] = int(swagger_port_raw) if swagger_port_raw else None

    flask_env = os.environ.get("FLASK_ENV", "development")
    debug = flask_env == "development"

    # Ensure sqlite path is absolute if it points to /data (nice for swagger editor link generation)
    sqlite_path_abs = str(Path(sqlite_path).expanduser())

    database_uri = build_sqlite_uri(sqlite_path_abs)

    app = create_app(database_uri=database_uri, debug=debug)

    # Used by the /swagger_editor redirect when local swagger-editor assets are missing
    if swagger_port is None:
        app.config["PUBLIC_SWAGGER_JSON_URL"] = f"http://{swagger_host}/api/swagger.json"
    else:
        app.config["PUBLIC_SWAGGER_JSON_URL"] = f"http://{swagger_host}:{swagger_port}/api/swagger.json"

    start_api(app, swagger_host=swagger_host, swagger_port=swagger_port)

    _app = app
    return _app
