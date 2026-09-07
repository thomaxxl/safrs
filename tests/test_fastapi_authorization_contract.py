"""Behavioral regressions for the explicit FastAPI authorization contract."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import anyio
import pytest
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Security
from fastapi.security import SecurityScopes
from fastapi.testclient import TestClient
from sqlalchemy import Column, ForeignKey, String, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, validates
from sqlalchemy.pool import StaticPool

import safrs
from safrs import SAFRSBase, jsonapi_rpc
from safrs.fastapi.api import SafrsFastAPI
from safrs.fastapi.authorization import AuthorizationContext


Base = declarative_base()


class _PermissionDescriptor:
    """Expose distinct class- and instance-level permission decisions."""

    def __init__(self, rule: Any) -> None:
        self.rule = rule

    def __get__(self, instance: Any, owner: Any) -> Any:
        subject = owner if instance is None else instance
        return lambda property_name, permission="r": self.rule(subject, property_name, permission)


class Parent(SAFRSBase, Base):
    __tablename__ = "auth_contract_parents"
    _s_collection_name = "ContractParents"
    _s_type = "ContractParent"
    allow_client_generated_ids = True
    _s_allow_add_rels = True
    id = Column(String, primary_key=True)
    name = Column(String, default="admin")
    children = relationship("Child", back_populates="parent")

    @validates("name")
    def validate_name(self, _key: str, value: str) -> str:
        if value == "rejected":
            raise ValueError("rejected value")
        return value

    @classmethod
    @jsonapi_rpc(http_methods=["POST", "GET"])
    def ping(cls) -> str:
        return "ok"

    @classmethod
    @jsonapi_rpc(http_methods=["POST"])
    def child_result(cls, shape: str = "object") -> Any:
        child = Child.get_instance("c1")
        child.name = "rpc changed"
        if shape == "document":
            return {"data": {"type": Child._s_type, "id": child.id, "attributes": {"name": child.name}}}
        if shape == "included":
            return {"data": None, "included": [child]}
        if shape == "list":
            return [Child.get_instance("c2"), child]
        return child

    @jsonapi_rpc(http_methods=["POST"])
    def instance_result(self) -> Any:
        return self.children

    @classmethod
    @jsonapi_rpc(http_methods=["POST"], valid_jsonapi=False)
    def raw_result(cls) -> Any:
        return {"outer": {"type": Child._s_type, "id": "c1", "attributes": {"name": "secret"}}}


class Child(SAFRSBase, Base):
    __tablename__ = "auth_contract_children"
    _s_collection_name = "ContractChildren"
    _s_type = "ContractChild"
    allow_client_generated_ids = True
    id = Column(String, primary_key=True)
    name = Column(String)
    parent_id = Column(String, ForeignKey("auth_contract_parents.id"))
    parent = relationship(Parent, back_populates="children")
    leaves = relationship("Leaf", back_populates="child")


class Leaf(SAFRSBase, Base):
    __tablename__ = "auth_contract_leaves"
    _s_collection_name = "ContractLeaves"
    _s_type = "ContractLeaf"
    id = Column(String, primary_key=True)
    child_id = Column(String, ForeignKey("auth_contract_children.id"))
    child = relationship(Child, back_populates="leaves")


@pytest.fixture
def database(monkeypatch: pytest.MonkeyPatch) -> Any:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    monkeypatch.setattr(safrs, "DB", SimpleNamespace(session=session, Model=Base))
    Base.metadata.create_all(engine)
    session.add_all([
        Parent(id="p1", name="original"), Parent(id="p2", name="empty"),
        Child(id="c1", name="secret", parent_id="p1"),
        Child(id="c2", name="public", parent_id="p1"),
        Leaf(id="l1", child_id="c1"),
    ])
    session.commit()
    yield session
    session.close()
    engine.dispose()


def document(model: Any, object_id: str, name: str = "changed") -> dict[str, Any]:
    return {"data": {"type": model._s_type, "id": object_id, "attributes": {"name": name}}}


def deny() -> None:
    raise HTTPException(403, "Policy denied")


def deny_child(model: Any, instance: Any, request: Request) -> bool:
    assert model is Child
    return instance.id != "c1"


def build(**kwargs: Any) -> tuple[FastAPI, SafrsFastAPI]:
    app = FastAPI()
    return app, SafrsFastAPI(app, cleanup_session=False, **kwargs)


@pytest.mark.parametrize(
    "params",
    [
        {"filter": "1"},
        {"filter": "[]"},
        {"filter": '[{"name":"name","op":"eq","val":"original"},null]'},
        {"filter": '{"name":"name","op":"in","val":"original"}'},
        {"filter[missing]": "value"},
        {"filter[]": "value"},
        {"filter[name]": ""},
    ],
)
def test_filter_validation_errors_are_jsonapi_400_documents(
    database: Any, params: dict[str, str]
) -> None:
    app, api = build()
    api.expose_object(Parent)

    response = TestClient(app).get("/ContractParents", params=params)

    assert response.status_code == 400
    assert "application/vnd.api+json" in response.headers["content-type"]
    error = response.json()["errors"][0]
    assert error["status"] == "400"
    assert error["title"] == "ValidationError"
    assert error["detail"]


def test_valid_bracket_filter_still_matches_typed_collection_rows(database: Any) -> None:
    app, api = build()
    api.expose_object(Parent)

    response = TestClient(app).get(
        "/ContractParents", params={"filter[name]": "original"}
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["data"]] == ["p1"]


@pytest.mark.parametrize("target_first", [False, True])
def test_public_parent_and_multihop_graph_are_not_globally_restricted(database: Any, target_first: bool) -> None:
    app, api = build()
    if target_first:
        api.expose_object(Leaf, read_dependencies=[deny])
    api.expose_object(Parent)
    api.expose_object(Child, read_dependencies=[deny])
    if not target_first:
        api.expose_object(Leaf, read_dependencies=[deny])
    client = TestClient(app)
    assert client.get("/ContractParents/p1").status_code == 200
    assert client.get("/ContractParents").status_code == 200
    assert client.post("/ContractParents/ping", json={}).status_code == 200
    assert client.patch("/ContractParents/p1", json=document(Parent, "p1")).status_code == 200
    assert client.post("/ContractParents", json=document(Parent, "new")).status_code == 201
    assert client.delete("/ContractParents/new").status_code == 204
    assert client.get("/ContractParents/p1/children").status_code == 403
    assert client.get("/ContractParents/p2/children").status_code == 403
    assert client.get("/ContractParents/p1?include=children").status_code == 403
    assert client.get("/ContractParents/p2?include=children").status_code == 403


def test_transitive_policy_is_checked_only_for_requested_include(database: Any) -> None:
    app, api = build()
    api.expose_object(Parent)
    api.expose_object(Child)
    client = TestClient(app)
    assert client.get("/ContractParents/p1").status_code == 200
    api.expose_object(Leaf, read_dependencies=[deny])
    assert client.get("/ContractParents/p1").status_code == 200
    assert client.get("/ContractParents/p1?include=children").status_code == 200
    assert client.get("/ContractParents/p1?include=children.leaves").status_code == 403


def test_ordinary_dependencies_body_state_and_yield_lifetimes_run_once(database: Any) -> None:
    events: list[str] = []
    requests: list[Request] = []

    async def audit(request: Request) -> None:
        events.append("audit")
        request.state.principal = "alice"
        assert (await request.json())["data"]["id"] == "new"
        requests.append(request)

    def sync_lifetime() -> Any:
        events.append("sync setup")
        yield
        events.append("sync teardown")

    async def async_lifetime() -> Any:
        events.append("async setup")
        yield
        events.append("async teardown")

    async def principal(request: Request) -> str:
        events.append("principal")
        assert request is requests[0]
        return request.state.principal

    def create(user: str = Depends(principal)) -> None:
        events.append("create")
        assert user == "alice"

    async def read(request: Request, user: str = Depends(principal)) -> None:
        events.append("read")
        assert request is requests[0] and request.method == "POST"
        assert user == "alice"
        assert (await request.json())["data"]["id"] == "new"

    app, api = build(dependencies=[audit, sync_lifetime, async_lifetime])
    api.expose_object(Parent, read_dependencies=[read], create_dependencies=[create])
    response = TestClient(app).post("/ContractParents", json=document(Parent, "new"))
    assert response.status_code == 201, response.text
    assert events == ["audit", "sync setup", "async setup", "principal", "create", "read", "async teardown", "sync teardown"]
    assert database.get(Parent, "new") is not None


@pytest.mark.parametrize("generator_kind", ["sync", "async"])
@pytest.mark.parametrize("deny_teardown", [False, True])
def test_authorization_generators_exit_before_commit(database: Any, generator_kind: str, deny_teardown: bool) -> None:
    events: list[str] = []

    def policy() -> Any:
        events.append("setup")
        yield "alice"
        events.append("teardown")
        if deny_teardown:
            raise HTTPException(403, "Late rejection")

    async def async_policy() -> Any:
        events.append("setup")
        yield "alice"
        events.append("teardown")
        if deny_teardown:
            raise HTTPException(403, "Late rejection")

    app, api = build()
    dependency = policy if generator_kind == "sync" else async_policy
    api.expose_object(Parent, create_dependencies=[dependency], read_dependencies=[dependency])
    response = TestClient(app).post("/ContractParents", json=document(Parent, "new"))
    assert response.status_code == (403 if deny_teardown else 201), response.text
    assert events == ["setup", "teardown"]
    database.expire_all()
    assert (database.get(Parent, "new") is None) == deny_teardown


@pytest.mark.parametrize("path", [
    "/ContractChildren", "/ContractChildren/c1", "/ContractParents/p1/children",
    "/ContractParents/p1?include=children",
])
def test_response_authorizer_receives_each_actual_child_and_denies_entire_document(database: Any, path: str) -> None:
    seen: list[str] = []

    def authorize(model: Any, instance: Any, request: Request) -> bool:
        assert model is Child and isinstance(instance, Child)
        seen.append(instance.id)
        return deny_child(model, instance, request)

    app, api = build()
    api.expose_object(Parent)
    api.expose_object(Child, response_authorizer=authorize)
    client = TestClient(app)
    response = client.get(path)
    assert response.status_code == 403, response.text
    assert "c1" in seen
    assert "data" not in response.json() and "included" not in response.json()
    assert client.get("/ContractChildren/c2").status_code == 200


@pytest.mark.parametrize("shape", ["object", "document", "included", "list", "instance"])
def test_rpc_resource_results_apply_target_object_policy_and_roll_back(database: Any, shape: str) -> None:
    app, api = build()
    api.expose_object(Parent)
    api.expose_object(Child, response_authorizer=deny_child)
    client = TestClient(app)
    response = client.post(
        "/ContractParents/p1/instance_result" if shape == "instance" else "/ContractParents/child_result",
        json={"meta": {"args": {} if shape == "instance" else {"shape": shape}}},
    )
    assert response.status_code == 403, response.text
    database.expire_all()
    assert database.get(Child, "c1").name == "secret"


def test_nested_raw_rpc_resource_representations_are_authorized(database: Any) -> None:
    app, api = build()
    api.expose_object(Parent)
    api.expose_object(Child, response_authorizer=deny_child)
    response = TestClient(app).post("/ContractParents/raw_result", json={})
    assert response.status_code == 403


def test_delete_permission_is_separate_from_read_permission(database: Any) -> None:
    app, api = build()
    api.expose_object(Parent, delete_dependencies=[deny])
    client = TestClient(app)
    assert client.get("/ContractParents/p2").status_code == 200
    assert client.delete("/ContractParents/p2").status_code == 403
    assert database.get(Parent, "p2") is not None


@pytest.mark.parametrize("method", ["post", "patch"])
def test_create_permission_never_grants_upsert_or_patch_permission(database: Any, method: str) -> None:
    app, api = build()
    api.expose_object(Parent, update_dependencies=[deny])
    client = TestClient(app)
    assert client.post("/ContractParents", json=document(Parent, "new")).status_code == 201
    path = "/ContractParents" if method == "post" else "/ContractParents/p1"
    response = getattr(client, method)(path, json=document(Parent, "p1"))
    assert response.status_code == 403
    database.expire_all()
    assert database.get(Parent, "p1").name == "original"


def test_bulk_create_upsert_mix_rolls_back_all_rows_on_update_denial(database: Any) -> None:
    app, api = build()
    api.expose_object(Parent, update_dependencies=[deny])
    response = TestClient(app).post("/ContractParents", json={"data": [
        document(Parent, "new")["data"], document(Parent, "p1")["data"],
    ]})
    assert response.status_code == 403
    database.expire_all()
    assert database.get(Parent, "new") is None
    assert database.get(Parent, "p1").name == "original"


def test_upsert_only_uses_update_policy_and_works_without_patch_route(database: Any, monkeypatch: Any) -> None:
    monkeypatch.setattr(Parent, "http_methods", ["GET", "POST"])
    app, api = build()
    api.expose_object(Parent, create_dependencies=[deny])
    client = TestClient(app)
    assert client.post("/ContractParents", json=document(Parent, "p1")).status_code == 200
    assert client.post("/ContractParents", json=document(Parent, "new")).status_code == 403
    assert client.patch("/ContractParents/p1", json=document(Parent, "p1")).status_code == 405
    database.expire_all()
    assert database.get(Parent, "p1").name == "changed"


def test_nested_upsert_uses_target_update_policy(database: Any) -> None:
    app, api = build()
    api.expose_object(Parent)
    api.expose_object(Child, update_dependencies=[deny])
    payload = document(Parent, "new")
    payload["data"]["relationships"] = {"children": {"data": [document(Child, "c1")["data"]]}}
    response = TestClient(app).post("/ContractParents", json=payload)
    assert response.status_code == 403, response.text
    database.expire_all()
    assert database.get(Parent, "new") is None
    assert database.get(Child, "c1").name == "secret"


@pytest.mark.parametrize("allowed", [False, True])
def test_nested_post_automatically_includes_authorized_resources(database: Any, allowed: bool) -> None:
    seen: list[str] = []

    def authorize(model: Any, instance: Any, request: Request) -> bool:
        assert model is Child
        seen.append(instance.id)
        return allowed

    app, api = build()
    api.expose_object(Parent)
    api.expose_object(Child, response_authorizer=authorize)
    payload = document(Parent, "new")
    payload["data"]["relationships"] = {"children": {"data": [document(Child, "new-child")["data"]]}}
    response = TestClient(app).post("/ContractParents", json=payload)
    assert response.status_code == (201 if allowed else 403), response.text
    assert seen == ["new-child"]
    database.expire_all()
    if allowed:
        assert {item["id"] for item in response.json()["included"]} == {"new-child"}
    else:
        assert database.get(Parent, "new") is None
        assert database.get(Child, "new-child") is None


def test_security_subdependency_overrides_apply_to_response_checks(database: Any) -> None:
    calls: list[str] = []

    def principal() -> str:
        raise AssertionError("overridden dependency must not run")

    async def replacement(security_scopes: SecurityScopes, x_user: str = Header()) -> str:
        assert security_scopes.scopes == ["read"]
        calls.append(x_user)
        return x_user

    def read(user: str = Depends(principal)) -> None:
        if user != "alice":
            raise HTTPException(403)

    app, api = build()
    app.dependency_overrides[principal] = replacement
    api.expose_object(Parent, read_dependencies=[Security(read, scopes=["read"])])
    client = TestClient(app)
    response = client.post("/ContractParents", headers={"x-user": "alice"}, json=document(Parent, "new"))
    assert response.status_code == 201, response.text
    denied = client.patch("/ContractParents/p1", headers={"x-user": "bob"}, json=document(Parent, "p1"))
    assert denied.status_code == 403
    assert calls == ["alice", "bob"]


def test_async_callable_response_authorizer_and_global_model_policies_are_additive(database: Any) -> None:
    calls: list[str] = []

    async def global_read(request: Request) -> None:
        calls.append("global")

    class Authorize:
        async def __call__(self, model: Any, instance: Any, request: Request) -> bool:
            assert model is Parent and request.method == "POST"
            calls.append(instance.id)
            return False

    app, api = build(read_dependencies=[global_read])
    api.expose_object(Parent, response_authorizer=Authorize())
    response = TestClient(app).post("/ContractParents", json=document(Parent, "new"))
    assert response.status_code == 403
    assert calls == ["global", "new"]
    database.expire_all()
    assert database.get(Parent, "new") is None


def test_concurrent_policies_do_not_change_or_deadlock_default_worker_limiter() -> None:
    async def exercise() -> None:
        default_limiter = anyio.to_thread.current_default_thread_limiter()
        original = default_limiter.total_tokens
        default_limiter.total_tokens = 1
        app = FastAPI()
        limiter = anyio.CapacityLimiter(2)
        seen: list[str] = []

        def policy(request: Request) -> None:
            seen.append(request.headers["x-user"])

        async def one(user: str) -> None:
            request = Request({"type": "http", "method": "POST", "path": "/", "query_string": b"", "headers": [(b"x-user", user.encode())]})
            state = AuthorizationContext(request, app, limiter)
            async with state.stack:
                await anyio.to_thread.run_sync(lambda: state.run(state.check, [Depends(policy)]))

        try:
            with anyio.fail_after(5):
                async with anyio.create_task_group() as group:
                    for user in ("alice", "bob", "carol"):
                        group.start_soon(one, user)
            assert sorted(seen) == ["alice", "bob", "carol"]
            assert default_limiter.total_tokens == 1
        finally:
            default_limiter.total_tokens = original

    asyncio.run(exercise())


def test_relationship_write_permission_blocks_direct_and_nested_mutation(
    database: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    def permission(_owner: Any, property_name: str, permission: str = "r") -> bool:
        return not (property_name == "children" and permission == "w")

    monkeypatch.setattr(Parent, "_s_check_perm", _PermissionDescriptor(permission))
    app, api = build()
    api.expose_object(Parent)
    api.expose_object(Child)
    client = TestClient(app)
    linkage = {"data": [{"type": Child._s_type, "id": "c2"}]}

    direct = client.patch("/ContractParents/p2/children", json=linkage)
    nested_payload = document(Parent, "new")
    nested_payload["data"]["relationships"] = {
        "children": {"data": [document(Child, "new-child")["data"]]}
    }
    nested = client.post("/ContractParents", json=nested_payload)

    assert direct.status_code == 403, direct.text
    assert nested.status_code == 403, nested.text
    database.expire_all()
    assert database.get(Child, "c2").parent_id == "p1"
    assert database.get(Parent, "new") is None


def test_constructor_validator_failure_cannot_fall_through_to_default(database: Any) -> None:
    app, api = build()
    api.expose_object(Parent)
    response = TestClient(app).post(
        "/ContractParents", json=document(Parent, "rejected-row", "rejected")
    )
    assert response.status_code == 400, response.text
    database.expire_all()
    assert database.get(Parent, "rejected-row") is None


def test_query_scope_precedes_fastapi_count_sort_and_pagination(
    database: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    def scope(cls: Any, query: Any) -> Any:
        return query.filter(cls.id == "p2")

    monkeypatch.setattr(Parent, "_s_query_scope", classmethod(scope))
    app, api = build()
    api.expose_object(Parent)
    response = TestClient(app).get("/ContractParents?page[offset]=0&page[limit]=1")
    assert response.status_code == 200, response.text
    assert response.json()["meta"]["total"] == 1
    assert [item["id"] for item in response.json()["data"]] == ["p2"]


def test_fastapi_sort_rejects_row_dependent_field_permissions(
    database: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    def permission(owner: Any, property_name: str, permission: str = "r") -> bool:
        if isinstance(owner, Parent) and owner.id == "p1" and property_name == "name":
            return False
        return True

    monkeypatch.setattr(Parent, "_s_check_perm", _PermissionDescriptor(permission))
    app, api = build()
    api.expose_object(Parent)
    client = TestClient(app)
    assert client.get("/ContractParents?sort=name").status_code == 400
    assert client.get("/ContractParents?sort=-name").status_code == 400


def test_fastapi_request_body_limit_rejects_oversized_payload(
    database: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(safrs.SAFRS, "MAX_REQUEST_BODY_BYTES", 128)
    app, api = build()
    api.expose_object(Parent)
    response = TestClient(app).post(
        "/ContractParents", json=document(Parent, "large", "x" * 300)
    )
    assert response.status_code == 413, response.text
    assert database.get(Parent, "large") is None


def test_fastapi_instances_keep_their_captured_database_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    first_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    second_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(first_engine)
    Base.metadata.create_all(second_engine)
    first_session = sessionmaker(bind=first_engine, expire_on_commit=False)()
    second_session = sessionmaker(bind=second_engine, expire_on_commit=False)()
    first_session.add(Parent(id="same", name="first"))
    second_session.add(Parent(id="same", name="second"))
    first_session.commit()
    second_session.commit()

    monkeypatch.setattr(safrs, "DB", SimpleNamespace(session=first_session, Model=Base))
    first_app = FastAPI()
    first_api = SafrsFastAPI(
        first_app, cleanup_session=False,
        app_db=SimpleNamespace(session=first_session, Model=Base),
    )
    first_api.expose_object(Parent)
    monkeypatch.setattr(safrs, "DB", SimpleNamespace(session=second_session, Model=Base))
    second_app = FastAPI()
    second_api = SafrsFastAPI(
        second_app, cleanup_session=False,
        app_db=SimpleNamespace(session=second_session, Model=Base),
    )
    second_api.expose_object(Parent)

    assert TestClient(first_app).get("/ContractParents/same").json()["data"]["attributes"]["name"] == "first"
    assert TestClient(second_app).get("/ContractParents/same").json()["data"]["attributes"]["name"] == "second"
    first_session.close()
    second_session.close()
    first_engine.dispose()
    second_engine.dispose()
