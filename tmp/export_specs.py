#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import safrs
from safrs.base import SAFRSBase

TMP_DIR = Path(__file__).resolve().parent
FLASK_SPEC_PATH = TMP_DIR / "flask.swagger.json"
FASTAPI_SPEC_PATH = TMP_DIR / "fastapi.openapi.json"


def _cleanup_session(db_wrapper: Any) -> None:
    session = getattr(db_wrapper, "session", None)
    if session is not None and hasattr(session, "remove"):
        session.remove()


def _clear_safrs_type_cache() -> None:
    cache_clear = getattr(SAFRSBase._safrs_subclasses, "cache_clear", None)
    if callable(cache_clear):
        cache_clear()


def export_specs() -> tuple[Path, Path]:
    # Import app factories lazily so test collection does not load tmp models.
    from fastapi_app import create_app as create_fastapi_app
    from flask_app import create_app as create_flask_app

    original_db = getattr(safrs, "DB", None)
    flask_spec: Dict[str, Any] = {}
    fastapi_spec: Dict[str, Any] = {}
    try:
        _clear_safrs_type_cache()
        flask_app = create_flask_app()
        with flask_app.test_client() as client:
            flask_data = client.get("/api/swagger.json").get_json()
        if isinstance(flask_data, dict):
            flask_spec = flask_data
        if not isinstance(flask_spec, dict):
            raise RuntimeError("Failed to load Flask swagger spec from /api/swagger.json")
        _cleanup_session(getattr(safrs, "DB", None))

        fastapi_app = create_fastapi_app()
        fastapi_spec = fastapi_app.openapi()
        _cleanup_session(getattr(safrs, "DB", None))
    finally:
        _clear_safrs_type_cache()
        setattr(safrs, "DB", original_db)

    FLASK_SPEC_PATH.write_text(json.dumps(flask_spec, indent=2, sort_keys=True), encoding="utf-8")
    FASTAPI_SPEC_PATH.write_text(json.dumps(fastapi_spec, indent=2, sort_keys=True), encoding="utf-8")
    return FLASK_SPEC_PATH, FASTAPI_SPEC_PATH


if __name__ == "__main__":
    flask_path, fastapi_path = export_specs()
    print(f"wrote {flask_path}")
    print(f"wrote {fastapi_path}")
