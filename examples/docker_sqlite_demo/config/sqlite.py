"""Optional config module (not required).

This exists to mirror the `CONFIG_MODULE` approach from `safrs-example`.
The demo itself reads environment variables directly, so you can ignore this file
unless you prefer config files.

Typical usage:
  export CONFIG_MODULE=examples/docker_sqlite_demo/config/sqlite.py
"""

import os
from pathlib import Path

FLASK_ENV = os.environ.get("FLASK_ENV", "development")
DEBUG = FLASK_ENV == "development"

SQLITE_PATH = os.environ.get("SQLITE_PATH", "/data/safrs_demo.db")
SQLALCHEMY_DATABASE_URI = f"sqlite:///{Path(SQLITE_PATH).expanduser()}"
SQLALCHEMY_TRACK_MODIFICATIONS = False

SWAGGER_HOST = os.environ.get("SWAGGER_HOST", "localhost")
SWAGGER_PORT = int(os.environ.get("SWAGGER_PORT", "1237"))
