#!/usr/bin/env python
import logging
import os
import sys
from typing import Any
# run:
# $ FLASK_APP=mini_app flask run
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import safrs
from safrs import SAFRSBase, SafrsApi

db = SQLAlchemy()


def _is_truthy_env(value: str | None) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _parse_log_level_value(value: str | None) -> int | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    try:
        return int(normalized)
    except ValueError:
        upper = normalized.upper()
        if upper in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            return int(getattr(logging, upper))
    return None


def _resolve_log_level() -> int:
    loglevel_env = os.environ.get("LOGLEVEL")
    parsed_loglevel = _parse_log_level_value(loglevel_env)
    if parsed_loglevel is not None:
        return parsed_loglevel

    debug_env = os.environ.get("DEBUG")
    if debug_env is not None:
        parsed_debug = _parse_log_level_value(debug_env)
        if parsed_debug is not None:
            return parsed_debug
        if _is_truthy_env(debug_env):
            return int(logging.DEBUG)
        return int(logging.INFO)

    if _is_truthy_env(os.environ.get("FLASK_DEBUG")):
        return int(logging.DEBUG)
    return int(logging.INFO)


def _debug_enabled() -> bool:
    return _resolve_log_level() <= int(logging.DEBUG)


def _reload_enabled() -> bool:
    if _is_truthy_env(os.environ.get("SAFRS_DISABLE_RELOAD")):
        return False
    return _debug_enabled()


def _configure_runtime_logging(level: int) -> None:
    if not logging.getLogger().handlers:
        logging.basicConfig(level=level, format="[%(asctime)s] %(levelname)s: %(message)s")

    safrs.log.setLevel(level)
    if not safrs.log.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s"))
        safrs.log.addHandler(handler)
    safrs.log.propagate = False
    logging.getLogger("werkzeug").setLevel(level)


class User(SAFRSBase, db.Model):
    """
    description: My User description
    """

    __tablename__ = "Users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    email = db.Column(db.String)


def create_api(app: Any, host: Any='127.0.0.1', port: Any=5000, prefix: Any='') -> Any:
    api = SafrsApi(app, host=host, port=port, prefix=prefix)
    api.expose_object(User)
    User(name="test", email="email@x.org") # this will automatically commit the user!
    safrs.log.info("Initialized mini_app API: http://%s:%s/%s", host, port, prefix)


def create_app(host: Any='127.0.0.1', port: Any=5000) -> Any:
    app = Flask("demo_app")
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite:///")
    db.init_app(app)
    with app.app_context():
        db.create_all()
        create_api(app, host, port)
    return app


if __name__ != "__main__":
    app = create_app()

if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    log_level = _resolve_log_level()
    _configure_runtime_logging(log_level)
    app = create_app(host=host, port=port)
    safrs.log.info(
        "Starting mini_app on http://%s:%s (debug=%s reload=%s)",
        host,
        port,
        log_level <= int(logging.DEBUG),
        _reload_enabled(),
    )
    app.run(
        host=host,
        port=port,
        debug=(log_level <= int(logging.DEBUG)),
        use_reloader=_reload_enabled(),
    )
