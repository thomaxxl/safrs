"""SEC-06 regression tests: authorization-aware schema/documentation
exposure and static documentation samples.

Covers:
- ``docs_decorators`` (Flask) / ``docs_dependencies`` (FastAPI) protect
  swagger.json, the Swagger UI, the ALS schema and the FastAPI docs routes.
- Configured documentation protection remains active at DEBUG log level.
- Public specs never contain live database values: id examples are derived
  from static column metadata only (``_s_sample_id`` / ``SAFRSID.sample_id``).
- A warning is emitted (once) when models carry SAFRS authorization
  policies but the documentation routes stay public.
"""

from __future__ import annotations

import json
import logging
from functools import wraps
from typing import Any

import pytest
from flask import Flask, abort
from flask_sqlalchemy import SQLAlchemy

import safrs
from safrs import SAFRSBase, SafrsApi


def _deny_access(function: Any) -> Any:
    @wraps(function)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        abort(401)

    return wrapped


# ---------------------------------------------------------------------------
# Flask
# ---------------------------------------------------------------------------

flask_db = SQLAlchemy()


class _FlaskDocsNote(SAFRSBase, flask_db.Model):  # type: ignore[name-defined]
    __tablename__ = "docs_security_notes"

    id = flask_db.Column(flask_db.Integer, primary_key=True)
    title = flask_db.Column(flask_db.String(120), nullable=False, default="")


def _build_flask_app(expose_method_decorators: Any = None, **init_kwargs: Any) -> tuple[Flask, Any]:
    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    flask_db.init_app(app)
    with app.app_context():
        flask_db.create_all()
        flask_db.session.add(_FlaskDocsNote(id=1, title="LIVE-SECRET-XYZ"))
        flask_db.session.commit()
        api = SafrsApi(app, host="localhost", prefix="/api", **init_kwargs)
        if expose_method_decorators is None:
            api.expose_object(_FlaskDocsNote)
        else:
            api.expose_object(_FlaskDocsNote, method_decorators=expose_method_decorators)
        api.expose_als_schema(api_root="/api", schema_loc="/als-schema")
    return app, api


def test_flask_docs_routes_are_protected() -> None:
    app, _ = _build_flask_app(docs_decorators=[_deny_access])
    client = app.test_client()

    for path in ("/api/swagger.json", "/api/swagger.html", "/api/als-schema", "/api/"):
        response = client.get(path)
        assert response.status_code == 401, path

    # Data routes are not affected by docs protection.
    assert client.get("/api/docs_security_notes/").status_code == 200


def test_flask_docs_decorators_remain_active_in_debug_mode() -> None:
    original_level = safrs.log.getEffectiveLevel()
    safrs.log.setLevel(logging.DEBUG)
    try:
        app, _ = _build_flask_app(docs_decorators=[_deny_access])
    finally:
        safrs.log.setLevel(original_level)
    client = app.test_client()

    for path in ("/api/swagger.json", "/api/als-schema"):
        assert client.get(path).status_code == 401, path


def test_flask_swagger_samples_do_not_read_live_data() -> None:
    app, _ = _build_flask_app()
    spec = app.test_client().get("/api/swagger.json").get_data(as_text=True)

    # The seeded row's value must not leak into the public spec.
    assert "LIVE-SECRET-XYZ" not in spec
    # Static placeholder instead of a live row id (integer PK -> "0").
    assert '"default": "0"' in spec or '"example": "0"' in spec


def test_flask_no_docs_warning_when_protected_or_no_policies(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Protected docs: no warning even though the model has no policy.
    app, _ = _build_flask_app(docs_decorators=[_deny_access])
    with caplog.at_level(logging.WARNING):
        app.test_client().get("/api/swagger.json")
    assert not [r for r in caplog.records if "documentation routes" in r.getMessage()]

    # Public docs but no model with a SAFRS authorization policy: no warning.
    app2, _ = _build_flask_app()
    with caplog.at_level(logging.WARNING):
        app2.test_client().get("/api/docs_security_notes/")
    assert not [r for r in caplog.records if "documentation routes" in r.getMessage()]


def test_flask_public_docs_warning_for_policy_models(caplog: pytest.LogCaptureFixture) -> None:
    """A model exposed with method_decorators on a public-docs app must
    trigger a single warning naming the model."""
    app, _ = _build_flask_app(expose_method_decorators=[_deny_access])

    with caplog.at_level(logging.WARNING):
        first = app.test_client().get("/api/docs_security_notes/")
        second = app.test_client().get("/api/docs_security_notes/")
        assert first.status_code == 401
        assert second.status_code == 401

    warnings = [
        record
        for record in caplog.records
        if record.levelno == logging.WARNING and "documentation routes" in record.getMessage()
    ]
    assert len(warnings) == 1
    assert "docs_security_notes" in warnings[0].getMessage()


# ---------------------------------------------------------------------------
# FastAPI
# ---------------------------------------------------------------------------

fastapi_tests = pytest.importorskip("fastapi")
from fastapi import Depends, FastAPI, Header, HTTPException, Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import Column, Integer, String  # noqa: E402
from sqlalchemy.orm import declarative_base  # noqa: E402

from safrs.fastapi.api import SafrsFastAPI  # noqa: E402

FastBase = declarative_base()


class _FastDocsNote(SAFRSBase, FastBase):  # type: ignore[misc]
    __tablename__ = "docs_security_fastapi_notes"
    _s_type = "FastDocsNote"
    _s_collection_name = "FastDocsNotes"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False, default="")


def _require_user(request: Request) -> None:
    raise HTTPException(status_code=401, detail="Unauthorized")


def _require_user_no_arg() -> None:
    raise HTTPException(status_code=401, detail="Unauthorized")


def test_fastapi_docs_routes_are_protected() -> None:
    app = FastAPI()
    SafrsFastAPI(app, prefix="/api", docs_dependencies=[Depends(_require_user)])

    client = TestClient(app)
    for path in ("/openapi.json", "/docs", "/redoc", "/swagger.json"):
        response = client.get(path)
        assert response.status_code == 401, path

    # Zero-argument dependencies are supported too.
    app2 = FastAPI()
    SafrsFastAPI(app2, prefix="/api", docs_dependencies=[Depends(_require_user_no_arg)])
    assert TestClient(app2).get("/openapi.json").status_code == 401


def test_fastapi_docs_dependencies_remain_active_in_debug_mode() -> None:
    original_level = safrs.log.getEffectiveLevel()
    safrs.log.setLevel(logging.DEBUG)
    try:
        app = FastAPI()
        SafrsFastAPI(app, prefix="/api", docs_dependencies=[Depends(_require_user)])
    finally:
        safrs.log.setLevel(original_level)

    client = TestClient(app)
    for path in ("/openapi.json", "/docs"):
        assert client.get(path).status_code == 401, path


def test_fastapi_docs_use_native_dependency_resolution_and_cleanup() -> None:
    events: list[str] = []

    def principal(x_user: str = Header()) -> str:
        events.append(f"principal:{x_user}")
        return x_user

    def replacement() -> str:
        events.append("override")
        return "alice"

    def authorize(user: str = Depends(principal)) -> Any:
        events.append(f"setup:{user}")
        if user != "alice":
            raise HTTPException(status_code=403)
        yield
        events.append("teardown")

    app = FastAPI()
    app.dependency_overrides[principal] = replacement
    SafrsFastAPI(app, docs_dependencies=[Depends(authorize)])
    response = TestClient(app).get("/openapi.json")

    assert response.status_code == 200
    assert events == ["override", "setup:alice", "teardown"]


def test_fastapi_openapi_uses_static_id_samples() -> None:
    app = FastAPI()
    api = SafrsFastAPI(app, prefix="/api")
    # No database is wired up at all: any attempt to read live rows for
    # documentation samples would fail loudly instead of leaking data.
    api.expose_object(_FastDocsNote)

    spec = app.openapi()
    serialized = json.dumps(spec)
    # String PK without declared sample/default -> empty static placeholder.
    assert '"LIVE"' not in serialized
