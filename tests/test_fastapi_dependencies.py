from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("fastapi")
from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.routing import APIRoute
from sqlalchemy import Column, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, relationship, scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool

import safrs
from safrs import SAFRSBase, jsonapi_rpc
from safrs.fastapi.api import JSONAPIHTTPError, SafrsFastAPI


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


def _require_child_user() -> None:
    raise HTTPException(status_code=403, detail="Child unauthorized")


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


def test_write_responses_replay_get_dependencies_and_roll_back() -> None:
    secure_base = declarative_base()

    class ProtectedResource(SAFRSBase, secure_base):
        __tablename__ = "fastapi_read_protected_resources"
        _s_type = "ReadProtectedResource"
        _s_collection_name = "ReadProtectedResources"
        allow_client_generated_ids = True

        id = Column(String, primary_key=True)
        name = Column(String)

        @classmethod
        @jsonapi_rpc(http_methods=["POST"])
        def first_resource(cls) -> Any:
            return cls.query.order_by(cls.id).first()

    class ProtectedParent(SAFRSBase, secure_base):
        __tablename__ = "fastapi_read_protected_parents"
        _s_type = "ReadProtectedParent"
        _s_collection_name = "ReadProtectedParents"

        id = Column(Integer, primary_key=True)
        children = relationship("ProtectedChild", back_populates="parent")

    class ProtectedChild(SAFRSBase, secure_base):
        __tablename__ = "fastapi_read_protected_children"
        _s_type = "ReadProtectedChild"
        _s_collection_name = "ReadProtectedChildren"

        id = Column(Integer, primary_key=True)
        parent_id = Column(Integer, ForeignKey("fastapi_read_protected_parents.id"))
        parent = relationship(ProtectedParent, back_populates="children")

    class DBWrapper:
        def __init__(self, session: Any) -> None:
            self.session = session
            self.Model = secure_base

    original_db = safrs.DB
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Session = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))
    safrs.DB = DBWrapper(Session)
    secure_base.metadata.create_all(engine)
    dependency_calls: list[tuple[str, str, str]] = []

    async def load_principal(request: Request) -> str:
        return request.headers.get("x-principal", "")

    async def require_read_access(
        request: Request,
        principal: str = Security(load_principal, scopes=["read"]),
    ) -> None:
        dependency_calls.append((request.method, request.url.path, principal))
        if principal != "alice":
            raise HTTPException(status_code=401, detail="Authentication required")
        if request.method == "GET":
            raise HTTPException(status_code=403, detail="Read forbidden")

    try:
        Session.add_all(
            [
                ProtectedResource(id="existing", name="original"),
                ProtectedParent(id=1),
                ProtectedChild(id=1),
            ]
        )
        Session.commit()

        app = FastAPI()
        api = SafrsFastAPI(app, cleanup_session=False)
        dependency = Depends(require_read_access)
        api.expose_object(ProtectedResource, dependencies=[dependency])
        api.expose_object(ProtectedParent, dependencies=[dependency])
        api.expose_object(ProtectedChild)

        def write_request(method: str, path: str) -> Request:
            return Request(
                {
                    "type": "http",
                    "app": app,
                    "method": method,
                    "path": path,
                    "raw_path": path.encode(),
                    "query_string": b"",
                    "headers": [(b"x-principal", b"alice")],
                    "scheme": "http",
                    "server": ("testserver", 80),
                },
            )

        with pytest.raises(HTTPException) as create_error:
            api._post_collection(ProtectedResource)(
                write_request("POST", "/ReadProtectedResources"),
                {
                    "data": {
                        "type": "ReadProtectedResource",
                        "id": "new",
                        "attributes": {"name": "created"},
                    }
                },
            )
        assert create_error.value.status_code == 403

        with pytest.raises(HTTPException) as upsert_error:
            api._post_collection(ProtectedResource)(
                write_request("POST", "/ReadProtectedResources"),
                {
                    "data": {
                        "type": "ReadProtectedResource",
                        "id": "existing",
                        "attributes": {"name": "upserted"},
                    }
                },
            )
        assert upsert_error.value.status_code == 403

        with pytest.raises(HTTPException) as patch_error:
            api._patch_instance(ProtectedResource)(
                "existing",
                write_request("PATCH", "/ReadProtectedResources/existing"),
                {
                    "data": {
                        "type": "ReadProtectedResource",
                        "id": "existing",
                        "attributes": {"name": "patched"},
                    }
                },
            )
        assert patch_error.value.status_code == 403

        with pytest.raises(HTTPException) as rpc_error:
            api._dispatch_rpc_call(
                ProtectedResource,
                "first_resource",
                write_request("POST", "/ReadProtectedResources/first_resource"),
                class_level=True,
                payload={},
            )
        assert rpc_error.value.status_code == 403

        with pytest.raises(HTTPException) as relationship_error:
            api._patch_relationship(ProtectedParent, "children")(
                "1",
                write_request("PATCH", "/ReadProtectedParents/1/children"),
                {"data": [{"type": "ReadProtectedChild", "id": "1"}]},
            )
        assert relationship_error.value.status_code == 403

        Session.expire_all()
        assert Session.get(ProtectedResource, "new") is None
        assert Session.get(ProtectedResource, "existing").name == "original"
        assert Session.get(ProtectedChild, 1).parent_id is None
        assert dependency_calls
        assert {method for method, _path, _principal in dependency_calls} == {"GET"}
        assert ("GET", "/ReadProtectedResources/new", "alice") in dependency_calls
        assert ("GET", "/ReadProtectedResources/existing", "alice") in dependency_calls
        # SEC-02: the relationship write is denied by the target row's own
        # instance-GET replay (which runs before the relationship's response
        # authorization).
        assert ("GET", "/ReadProtectedChildren/1", "alice") in dependency_calls
    finally:
        Session.remove()
        secure_base.metadata.drop_all(engine)
        safrs.DB = original_db


@pytest.mark.parametrize("target_first", [False, True])
def test_target_dependencies_protect_related_model_routes_regardless_of_exposure_order(target_first: bool) -> None:
    app = FastAPI()
    api = SafrsFastAPI(app, prefix="/api")

    if target_first:
        api.expose_object(_DependencyChild, dependencies=[Depends(_require_child_user)])
        api.expose_object(_DependencyParent)
    else:
        api.expose_object(_DependencyParent)
        api.expose_object(_DependencyChild, dependencies=[Depends(_require_child_user)])

    parent_routes = _model_routes(app)
    assert parent_routes
    assert all(
        _require_child_user in {dependency.call for dependency in route.dependant.dependencies}
        for route in parent_routes
    )


def test_shared_related_dependency_is_not_duplicated() -> None:
    app = FastAPI()
    api = SafrsFastAPI(app, prefix="/api")
    dependency = Depends(_require_user)

    api.expose_object(_DependencyParent, dependencies=[dependency])
    api.expose_object(_DependencyChild, dependencies=[dependency])

    for route in _model_routes(app):
        calls = [item.call for item in route.dependant.dependencies]
        assert calls.count(_require_user) == 1


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


def test_target_http_methods_restrict_fastapi_relationship_routes() -> None:
    restricted_base = declarative_base()

    class RestrictedParent(SAFRSBase, restricted_base):
        __tablename__ = "fastapi_restricted_method_parents"
        _s_type = "RestrictedParent"
        _s_collection_name = "RestrictedParents"

        id = Column(Integer, primary_key=True)
        children = relationship("RestrictedChild", back_populates="parent")

    class RestrictedChild(SAFRSBase, restricted_base):
        __tablename__ = "fastapi_restricted_method_children"
        _s_type = "RestrictedChild"
        _s_collection_name = "RestrictedChildren"
        http_methods = ["GET"]

        id = Column(Integer, primary_key=True)
        parent_id = Column(Integer, ForeignKey("fastapi_restricted_method_parents.id"))
        parent = relationship(RestrictedParent, back_populates="children")

    app = FastAPI()
    api = SafrsFastAPI(app, prefix="/api")
    api.expose_object(RestrictedParent)
    api.expose_object(RestrictedChild)

    relationship_routes = [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path == "/api/RestrictedParents/{object_id}/children"
    ]
    assert relationship_routes
    assert {method for route in relationship_routes for method in route.methods} == {"GET"}


def test_fastapi_bulk_and_include_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    api = SafrsFastAPI(app, prefix="/api")
    monkeypatch.setattr("safrs.SAFRS.MAX_BULK_ITEMS", 1)
    monkeypatch.setattr("safrs.SAFRS.MAX_INCLUDE_DEPTH", 1)
    monkeypatch.setattr("safrs.SAFRS.MAX_INCLUDE_PATHS", 1)

    with pytest.raises(JSONAPIHTTPError) as bulk_error:
        api._coerce_post_items(
            _DependencyParent,
            {
                "data": [
                    {"type": _DependencyParent._s_type},
                    {"type": _DependencyParent._s_type},
                ]
            },
        )
    assert bulk_error.value.status_code == 400

    deep_request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/DependencyParents",
            "query_string": b"include=children.parent",
            "headers": [],
        }
    )
    with pytest.raises(JSONAPIHTTPError) as include_error:
        api._parse_include_paths(_DependencyParent, deep_request)
    assert include_error.value.status_code == 400

    class Query:
        applied_limit: int | None = None

        def limit(self, value: int) -> "Query":
            self.applied_limit = value
            return self

        def all(self) -> list[int]:
            return [1, 2, 3][: self.applied_limit]

    query = Query()
    assert api._iter_related_items(query, limit=1) == [1]
    assert query.applied_limit == 1


def test_fastapi_default_pagination_and_empty_method_policy_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = SafrsFastAPI(FastAPI(), prefix="/api")
    monkeypatch.setattr("safrs.SAFRS.DEFAULT_PAGE_LIMIT", 2)

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/DependencyParents",
            "query_string": b"",
            "headers": [],
        }
    )

    class NoMethods:
        http_methods: list[str] = []

    assert api._apply_pagination([1, 2, 3], request) == [1, 2]
    assert api._model_http_methods(NoMethods) == set()
