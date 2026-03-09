#!/usr/bin/env python3
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
import safrs
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from safrs import SAFRSBase
from safrs.fastapi.api import SafrsFastAPI
from sqlalchemy import Column, ForeignKey, String, create_engine
from sqlalchemy.orm import declarative_base, relationship, scoped_session, sessionmaker

Base = declarative_base()

EXAMPLE_PREFIX = "/api_demo_jwt"
API_PREFIX = f"{EXAMPLE_PREFIX}/api"
DOCS_PATH = f"{EXAMPLE_PREFIX}/docs"
OPENAPI_PATH = f"{EXAMPLE_PREFIX}/openapi.json"
SWAGGER_ALIAS = f"{EXAMPLE_PREFIX}/swagger.json"
LOGIN_PATH = f"{EXAMPLE_PREFIX}/login"

JWT_SECRET = "demo-jwt-secret"
JWT_ALGORITHM = "HS256"
JWT_TTL_MINUTES = 60
PROTECTED_USER_PREFIX = f"{API_PREFIX}/Users"
DOCS_DESCRIPTION = """
JWT authentication example for SAFRS FastAPI.

- `POST /api_demo_jwt/login` with `{"username":"test","password":"test"}` to obtain a bearer token.
- `Item` endpoints are public.
- `User` endpoints under `/api_demo_jwt/api/Users` require `Authorization: Bearer <token>`.

Use the `Authorize` button in the docs to set the bearer token for protected `User` requests.
""".strip()


class _SAFRSDBWrapper:
    def __init__(self, session: Any, model: Any) -> None:
        self.session = session
        self.Model = model


class LoginRequest(BaseModel):
    username: str
    password: str


class Item(SAFRSBase, Base):
    __tablename__ = "Items"

    id = Column(String, primary_key=True)
    name = Column(String, default="")
    user_id = Column(String, ForeignKey("Users.id"))
    user = relationship("User", back_populates="items")


class User(SAFRSBase, Base):
    __tablename__ = "Users"

    id = Column(String, primary_key=True)
    username = Column(String(32), index=True)
    items = relationship("Item", back_populates="user", lazy="dynamic")

    @classmethod
    def filter(cls, *args: Any, **kwargs: Any) -> Any:
        _ = kwargs
        return cls.query.filter_by(username=args[0])


def create_access_token(username: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=JWT_TTL_MINUTES)).timestamp()),
    }
    return str(jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM))


def require_bearer_token(request: Request) -> str:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Unauthorized") from exc
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return subject


def install_custom_openapi(app: FastAPI) -> None:
    original_openapi = app.openapi

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema is not None:
            return app.openapi_schema

        schema = original_openapi()
        components = schema.setdefault("components", {})
        security_schemes = components.setdefault("securitySchemes", {})
        security_schemes["BearerAuth"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
        for path, path_item in schema.get("paths", {}).items():
            if not path.startswith(PROTECTED_USER_PREFIX):
                continue
            if not isinstance(path_item, dict):
                continue
            for operation in path_item.values():
                if isinstance(operation, dict):
                    operation["security"] = [{"BearerAuth": []}]

        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[assignment]


def create_app() -> FastAPI:
    database_uri = os.getenv("DEMO_JWT_DB_URI", "sqlite:////tmp/jwt_demo.sqlite")
    engine = create_engine(database_uri, future=True)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = scoped_session(session_factory)

    safrs.DB = _SAFRSDBWrapper(session, Base)

    Base.metadata.create_all(engine)
    if session.query(User).count() == 0:
        user = User(id="user2", username="user2")
        session.add(user)
        session.add(Item(id="item1", name="item test", user=user))
        session.commit()

    app = FastAPI(
        title="SAFRS JWT Authentication Example",
        description=DOCS_DESCRIPTION,
        docs_url=DOCS_PATH,
        redoc_url=None,
        openapi_url=OPENAPI_PATH,
    )

    @app.middleware("http")
    async def safrs_session_middleware(request: Request, call_next):
        try:
            return await call_next(request)
        finally:
            session.remove()

    api = SafrsFastAPI(app, prefix=API_PREFIX)
    api.expose_object(Item)
    api.expose_object(User, dependencies=[Depends(require_bearer_token)])

    install_custom_openapi(app)

    @app.get(EXAMPLE_PREFIX, include_in_schema=False)
    @app.get(EXAMPLE_PREFIX + "/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(url=DOCS_PATH, status_code=307)

    @app.get(SWAGGER_ALIAS, include_in_schema=False)
    def swagger_alias() -> dict[str, Any]:
        return app.openapi()

    @app.post(
        LOGIN_PATH,
        summary="Issue JWT access token",
        description="Use username `test` and password `test` to receive a bearer token.",
        tags=["Auth"],
    )
    def login(payload: LoginRequest) -> dict[str, str]:
        if payload.username != "test" or payload.password != "test":
            raise HTTPException(status_code=401, detail="Bad username or password")
        return {"access_token": create_access_token(payload.username)}

    return app


app = create_app()


def main() -> None:
    bind_host = os.getenv("DEMO_JWT_HOST", "127.0.0.1")
    bind_port = int(os.getenv("DEMO_JWT_PORT", "5001"))
    uvicorn.run(app, host=bind_host, port=bind_port, log_level="info")


if __name__ == "__main__":
    main()
