from __future__ import annotations

import os
from typing import Any, Callable

import safrs
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from safrs.fastapi.api import SafrsFastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker


class _SAFRSDBWrapper:
    def __init__(self, session: Any, model: Any) -> None:
        self.session = session
        self.Model = model


def create_example_app(
    *,
    title: str,
    description: str,
    example_prefix: str,
    base_model: Any,
    database_uri: str,
    seed_data: Callable[[Any], None],
    expose: Callable[[SafrsFastAPI], None],
) -> FastAPI:
    engine = create_engine(database_uri, future=True)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = scoped_session(session_factory)

    safrs.DB = _SAFRSDBWrapper(session, base_model)
    base_model.metadata.create_all(engine)
    seed_data(session)

    api_prefix = f"{example_prefix}/api"
    docs_path = f"{example_prefix}/docs"
    openapi_path = f"{example_prefix}/openapi.json"
    swagger_alias = f"{example_prefix}/swagger.json"

    app = FastAPI(
        title=title,
        description=description,
        docs_url=docs_path,
        redoc_url=None,
        openapi_url=openapi_path,
    )

    @app.middleware("http")
    async def safrs_session_middleware(request: Request, call_next):
        try:
            return await call_next(request)
        finally:
            session.remove()

    api = SafrsFastAPI(app, prefix=api_prefix)
    expose(api)

    @app.get(example_prefix, include_in_schema=False)
    @app.get(example_prefix + "/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(url=docs_path, status_code=307)

    @app.get(swagger_alias, include_in_schema=False)
    def swagger_json_alias() -> dict[str, Any]:
        return app.openapi()

    return app


def run_example(app_factory: Callable[[], FastAPI], *, host_env: str, port_env: str, default_port: int) -> None:
    host = os.getenv(host_env, "127.0.0.1")
    port = int(os.getenv(port_env, str(default_port)))
    uvicorn.run(app_factory(), host=host, port=port, log_level="info")
