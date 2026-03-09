#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Run:
  pip install -e . "fastapi[standard]"
  python examples/mini_fastapi_app.py

Then open:
  http://127.0.0.1:8000/docs
  http://127.0.0.1:8000/swagger.json
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any

import safrs
from safrs import SAFRSBase

from fastapi import FastAPI
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker

import uvicorn

from safrs.fastapi.api import SafrsFastAPI


Base = declarative_base()
HERE = Path(__file__).resolve().parent


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
    logging.getLogger("uvicorn").setLevel(level)
    logging.getLogger("uvicorn.error").setLevel(level)
    logging.getLogger("uvicorn.access").setLevel(level)


class User(SAFRSBase, Base):
    __tablename__ = "Users"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String)


class _SAFRSDBWrapper(object):
    """
    Enough of the Flask-SQLAlchemy interface for SAFRS internals:
    - .session (SQLAlchemy Session / scoped_session)
    - .Model (Declarative base class) used by SAFRSBase.__init__()
    """
    def __init__(self, session: Any, model: Any) -> None:
        self.session = session
        self.Model = model


def create_app(port: int = 8000) -> FastAPI:
    engine = create_engine("sqlite:///./mini_fastapi.db", future=True)
    SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Session = scoped_session(SessionFactory)

    # Tell SAFRS where the DB/session lives
    safrs.DB = _SAFRSDBWrapper(Session, Base)

    # Create tables + seed
    Base.metadata.create_all(engine)
    if Session.query(User).count() == 0:
        Session.add(User(name="test", email="email@x.org"))
        Session.commit()

    app = FastAPI(title="SAFRS FastAPI mini app", debug=_debug_enabled())

    # Make sure sessions are cleaned up
    @app.middleware("http")
    async def safrs_session_middleware(request, call_next):
        try:
            return await call_next(request)
        finally:
            Session.remove()

    # Register SAFRS-like routes under FastAPI
    api = SafrsFastAPI(app)
    api.expose_object(User)

    # Compatibility alias: tests in safrs-example call /swagger.json
    @app.get("/swagger.json", include_in_schema=False)
    def swagger_json():
        return app.openapi()

    @app.get("/", include_in_schema=False)
    def root():
        return {"status": "ok", "docs": "/docs", "openapi": "/openapi.json"}

    safrs.log.info("Initialized mini_fastapi_app on http://127.0.0.1:%s", port)

    return app


def _create_app_from_env() -> FastAPI:
    try:
        port = int(str(os.environ.get("SAFRS_APP_PORT", "8000")))
    except ValueError:
        port = 8000
    return create_app(port=port)


if __name__ != "__main__":
    app = _create_app_from_env()

if __name__ == "__main__":
    bind_host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    bind_port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    log_level = _resolve_log_level()
    reload_enabled = _reload_enabled()
    os.environ["SAFRS_APP_PORT"] = str(bind_port)
    _configure_runtime_logging(log_level)
    safrs.log.info(
        "Starting mini_fastapi_app on http://%s:%s (debug=%s reload=%s)",
        bind_host,
        bind_port,
        log_level <= int(logging.DEBUG),
        reload_enabled,
    )
    uvicorn.run(
        f"{Path(__file__).stem}:_create_app_from_env",
        factory=True,
        host=bind_host,
        port=bind_port,
        log_level="debug" if log_level <= logging.DEBUG else "info",
        access_log=True,
        reload=reload_enabled,
        reload_dirs=[str(HERE)] if reload_enabled else None,
    )
