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
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from safrs.fastapi.api import SafrsFastAPI

from models import API_PREFIX, Base, DESCRIPTION, EXPOSED_MODELS, SAFRSDBWrapper, TMP_DIR, create_session, seed_data


def create_app(db_name: str = "tmp_fastapi.db") -> FastAPI:
    db_path = TMP_DIR / db_name
    Session = create_session(db_path)
    seed_data(Session)

    wrapper = SAFRSDBWrapper(Session, Base)
    setattr(safrs, "DB", wrapper)

    app = FastAPI(
        title="SAFRS tmp FastAPI demo",
        description=DESCRIPTION,
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/swagger.json",
    )

    @app.middleware("http")
    async def remove_session_middleware(request: Any, call_next: Any) -> Any:
        try:
            return await call_next(request)
        finally:
            Session.remove()

    api = SafrsFastAPI(app, prefix=API_PREFIX)
    app.state.safrs_api = api
    for model in EXPOSED_MODELS:
        api.expose_object(model)

    @app.get("/", include_in_schema=False)
    def root() -> Any:
        return RedirectResponse(url=API_PREFIX)

    @app.get("/health", include_in_schema=False)
    def health() -> dict[str, Any]:
        return {"ok": True, "framework": "fastapi", "db": str(db_path), "api_prefix": API_PREFIX}

    return app


if __name__ == "__main__":
    import uvicorn

    bind_host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    bind_port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    uvicorn.run(create_app(), host=bind_host, port=bind_port)
