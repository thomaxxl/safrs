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
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from safrs.fastapi.api import RelationshipItemMode, SafrsFastAPI

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


def _resolve_db_name(explicit_db_name: str | None = None) -> str:
    if explicit_db_name:
        return explicit_db_name
    env_db_name = os.environ.get("SAFRS_TMP_DB", "").strip()
    if env_db_name:
        return env_db_name
    return "tmp_fastapi.db"


def _resolve_db_path(explicit_db_name: str | None = None) -> Path:
    resolved_db_name = _resolve_db_name(explicit_db_name=explicit_db_name)
    db_name_path = Path(resolved_db_name).expanduser()
    if db_name_path.is_absolute():
        return db_name_path
    return _resolve_db_dir() / db_name_path


def create_app(db_name: str | None = None) -> FastAPI:
    db_path = _resolve_db_path(explicit_db_name=db_name)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if _should_reset_tmp_db() and db_path.exists():
        db_path.unlink()
    Session = create_session(db_path)
    wrapper = SAFRSDBWrapper(Session, Base)
    setattr(safrs, "DB", wrapper)
    seed_data(Session)

    app = FastAPI(
        title="SAFRS tmp FastAPI demo",
        description=DESCRIPTION,
        docs_url="/docs",
        redoc_url=None,
        #openapi_url="/swagger.json",
    )

    @app.middleware("http")
    async def remove_session_middleware(request: Any, call_next: Any) -> Any:
        try:
            return await call_next(request)
        finally:
            Session.remove()

    api = SafrsFastAPI(app, prefix=API_PREFIX, relationship_item_mode=RelationshipItemMode.HIDDEN)
    app.state.safrs_api = api
    for model in EXPOSED_MODELS:
        api.expose_object(model)

    @app.get("/", include_in_schema=False)
    def root() -> Any:
        return RedirectResponse(url=API_PREFIX)

    @app.get("/health", include_in_schema=False)
    def health() -> dict[str, Any]:
        return {"ok": True, "framework": "fastapi", "db": str(db_path), "api_prefix": API_PREFIX}

    @app.get("/seed", include_in_schema=False)
    def seed() -> dict[str, Any]:
        return build_seed_payload(Session)

    return app


if __name__ == "__main__":
    import uvicorn

    bind_host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    bind_port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    db_name = os.environ.get("SAFRS_TMP_DB", f"tmp_fastapi_{bind_port}.db")
    uvicorn.run(create_app(db_name=db_name), host=bind_host, port=bind_port)
