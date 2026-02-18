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

from typing import Any

import safrs
from safrs import SAFRSBase

from fastapi import FastAPI
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker

import uvicorn

from safrs.fastapi.api import SafrsFastAPI


Base = declarative_base()


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


def create_app() -> FastAPI:
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

    app = FastAPI(title="SAFRS FastAPI mini app")

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

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)

