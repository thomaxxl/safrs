from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("fastapi")
from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.routing import APIRoute
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base, relationship

from safrs import SAFRSBase, jsonapi_rpc
from safrs.fastapi.api import SafrsFastAPI


Base = declarative_base()


class _DependencyParent(SAFRSBase, Base):
    __tablename__ = "fastapi_dependency_parents"
    _s_type = "DependencyParent"
    _s_collection_name = "DependencyParents"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    children = relationship("_DependencyChild", back_populates="parent")

    @staticmethod
    def _s_sample_id() -> str:
        return "1"

    @staticmethod
    def _s_sample_dict() -> dict[str, Any]:
        return {"id": 1, "name": "parent"}

    @classmethod
    @jsonapi_rpc(http_methods=["GET"])
    def class_ping(cls) -> dict[str, Any]:
        return {"meta": {"ok": True}}

    @jsonapi_rpc(http_methods=["POST"])
    def instance_ping(self) -> dict[str, Any]:
        return {"meta": {"ok": True}}


class _DependencyChild(SAFRSBase, Base):
    __tablename__ = "fastapi_dependency_children"
    _s_type = "DependencyChild"
    _s_collection_name = "DependencyChildren"

    id = Column(Integer, primary_key=True)
    parent_id = Column(Integer, ForeignKey("fastapi_dependency_parents.id"))
    parent = relationship(_DependencyParent, back_populates="children")

    @staticmethod
    def _s_sample_id() -> str:
        return "1"

    @staticmethod
    def _s_sample_dict() -> dict[str, Any]:
        return {"id": 1, "parent_id": 1}


def _require_user() -> None:
    raise HTTPException(status_code=401, detail="Unauthorized")


def _model_routes(app: FastAPI) -> list[APIRoute]:
    return [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/DependencyParents")
    ]


def _assert_dependency_protects_all_model_routes(app: FastAPI) -> None:
    routes = _model_routes(app)
    exposed_operations = {
        (method, route.path)
        for route in routes
        for method in route.methods
        if route.include_in_schema
    }
    assert {
        ("GET", "/api/DependencyParents"),
        ("POST", "/api/DependencyParents"),
        ("GET", "/api/DependencyParents/{object_id}"),
        ("PATCH", "/api/DependencyParents/{object_id}"),
        ("DELETE", "/api/DependencyParents/{object_id}"),
        ("GET", "/api/DependencyParents/{object_id}/children"),
        ("POST", "/api/DependencyParents/{object_id}/children"),
        ("GET", "/api/DependencyParents/class_ping"),
        ("POST", "/api/DependencyParents/{object_id}/instance_ping"),
    } <= exposed_operations
    assert routes
    assert all(
        _require_user in {dependency.call for dependency in route.dependant.dependencies}
        for route in routes
    )


def test_global_dependencies_protect_crud_relationship_and_rpc_routes() -> None:
    app = FastAPI()
    api = SafrsFastAPI(app, prefix="/api", dependencies=[Depends(_require_user)])

    api.expose_object(_DependencyParent)

    _assert_dependency_protects_all_model_routes(app)


def test_per_model_dependencies_protect_crud_relationship_and_rpc_routes() -> None:
    app = FastAPI()
    api = SafrsFastAPI(app, prefix="/api")

    api.expose_object(_DependencyParent, dependencies=[Depends(_require_user)])

    _assert_dependency_protects_all_model_routes(app)


def test_security_dependencies_are_preserved() -> None:
    app = FastAPI()
    api = SafrsFastAPI(app, prefix="/api")
    dependency = Security(_require_user, scopes=["read"])

    api.expose_object(_DependencyParent, dependencies=[dependency])

    for route in _model_routes(app):
        route_dependency = next(
            item for item in route.dependant.dependencies if item.call is _require_user
        )
        assert route_dependency.own_oauth_scopes == ["read"]


def test_model_decorators_are_rejected() -> None:
    class _DecoratedModel:
        decorators = [lambda function: function]

    api = SafrsFastAPI(FastAPI())

    with pytest.raises(
        NotImplementedError,
        match=(
            r"^FastAPI does not support Model\.decorators\. "
            r"Use dependencies=\[Depends\(\.\.\.\)\] instead\.$"
        ),
    ):
        api.expose_object(_DecoratedModel)
