"""Contract tests for the optional SQL-backed authorization registry."""

from __future__ import annotations

from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace
from typing import Any, AsyncIterator

import pytest
from fastapi import FastAPI, Header
from fastapi.testclient import TestClient
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, ForeignKey, Integer, String, create_engine, event, select, text
from sqlalchemy.orm import aliased, declarative_base, relationship, sessionmaker
from sqlalchemy.pool import StaticPool

import safrs
from safrs import (
    AuthContext,
    AuthorizationRegistry,
    SAFRSBase,
    SafrsApi,
    authorization_safe,
    jsonapi_attr,
    jsonapi_rpc,
)
from safrs.errors import NotFoundError, UnAuthorizedError, ValidationError
from safrs.fastapi.api import SafrsFastAPI


JSONAPI_HEADERS = {
    "Accept": "application/vnd.api+json",
    "Content-Type": "application/vnd.api+json",
}


def _document(Model: type[Any], object_id: str, **attributes: Any) -> dict[str, Any]:
    return {
        "data": {
            "type": Model._s_type,
            "id": object_id,
            "attributes": attributes,
        }
    }


def test_registry_sql_decisions_fields_subject_union_and_lifecycle() -> None:
    Base = declarative_base()

    class Document(SAFRSBase, Base):
        __tablename__ = "registry_core_documents"
        id = Column(Integer, primary_key=True)
        tenant_id = Column(Integer, nullable=False)
        title = Column(String)
        secret = Column(String)

    registry = AuthorizationRegistry(metadata=Base.metadata)
    registry.register(Document, key="core.document", tenant_column=Document.tenant_id)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    session.add_all(
        [
            Document(id=1, tenant_id=7, title="one", secret="s1"),
            Document(id=2, tenant_id=7, title="two", secret="s2"),
            Document(id=3, tenant_id=8, title="other", secret="s3"),
        ]
    )
    session.commit()

    registry.grant(
        session,
        scope_key="tenant:7",
        subject_key="user:alice",
        Model=Document,
        action="read",
        object_id=1,
        tenant_id="7",
    )
    registry.grant(
        session,
        scope_key="tenant:7",
        subject_key="group:staff",
        Model=Document,
        action="read",
        object_id=2,
        tenant_id="7",
    )
    registry.grant(
        session,
        scope_key="tenant:7",
        subject_key="group:staff",
        Model=Document,
        action="read",
        field="title",
    )
    registry.grant(
        session,
        scope_key="tenant:7",
        subject_key="user:alice",
        Model=Document,
        action="read",
        object_id=1,
        field="secret",
        tenant_id="7",
    )
    registry.grant(
        session,
        scope_key="tenant:7",
        subject_key="group:staff",
        Model=Document,
        action="read",
        object_id=3,
        tenant_id="8",
    )
    context = AuthContext("tenant:7", ("user:alice", "group:staff"), "7")

    visible = registry.scope_query(context, Document, session.query(Document)).all()
    title_visible = registry.scope_query(
        context, Document, session.query(Document), fields=["title"]
    ).all()
    secret_visible = registry.scope_query(
        context, Document, session.query(Document), fields=["secret"]
    ).all()
    assert [row.id for row in visible] == [1, 2]
    assert [row.id for row in title_visible] == [1, 2]
    assert [row.id for row in secret_visible] == [1]
    assert registry.scope_query(None, Document, session.query(Document)).count() == 0

    masks = registry.readable_fields(session, context, Document, visible)
    assert masks["id:1"] == frozenset({"title", "secret"})
    assert masks["id:2"] == frozenset({"title"})
    registry.require(session, context, visible[0], "read", ["secret"])
    with pytest.raises(NotFoundError):
        registry.require(session, context, visible[1], "read", ["secret"])

    assert registry.grant(
        session,
        scope_key="tenant:7",
        subject_key="user:alice",
        Model=Document,
        action="update",
        object_id=1,
        tenant_id="7",
    )
    assert not registry.grant(
        session,
        scope_key="tenant:7",
        subject_key="user:alice",
        Model=Document,
        action="update",
        object_id=1,
        tenant_id="7",
    )
    registry.grant(
        session,
        scope_key="tenant:7",
        subject_key="user:alice",
        Model=Document,
        action="update",
        object_id=1,
        field="title",
        tenant_id="7",
    )
    registry.require(session, context, visible[0], "update", ["title"])
    with pytest.raises(UnAuthorizedError):
        registry.require(session, context, visible[0], "update", ["secret"])

    registry.grant(
        session,
        scope_key="tenant:7",
        subject_key="user:alice",
        Model=Document,
        action="delete",
        object_id=1,
        tenant_id="7",
    )
    registry.delete_instance_grants(session, visible[0])
    assert session.execute(
        select(registry.table.c.id).where(registry.table.c.object_key == "id:1")
    ).all() == []
    session.close()
    engine.dispose()


def test_registry_create_validation_freeze_and_unsupported_identity() -> None:
    Base = declarative_base()

    class Item(SAFRSBase, Base):
        __tablename__ = "registry_create_items"
        id = Column(String, primary_key=True)
        name = Column(String)

    class Composite(SAFRSBase, Base):
        __tablename__ = "registry_composites"
        left = Column(Integer, primary_key=True)
        right = Column(Integer, primary_key=True)

    class UnsafeSerializer(SAFRSBase, Base):
        __tablename__ = "registry_unsafe_serializers"
        id = Column(Integer, primary_key=True)

        def to_dict(self: Any) -> dict[str, Any]:
            return {"unsafe": self.id}

    class SafeSerializer(SAFRSBase, Base):
        __tablename__ = "registry_safe_serializers"
        id = Column(Integer, primary_key=True)

        @authorization_safe
        def to_dict(self: Any) -> dict[str, Any]:
            return {}

    registry = AuthorizationRegistry(metadata=Base.metadata, max_subjects=2)
    registry.register(Item, key="core.item")
    with pytest.raises(TypeError):
        registry.register(Composite, key="core.composite")
    with pytest.raises(TypeError):
        registry.register(UnsafeSerializer, key="core.unsafe")
    registry.register(SafeSerializer, key="core.safe")
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    context = AuthContext("app", ("user:creator",))
    registry.grant(
        session,
        scope_key="app",
        subject_key="user:creator",
        Model=Item,
        action="create",
    )
    registry.grant(
        session,
        scope_key="app",
        subject_key="user:creator",
        Model=Item,
        action="create",
        field="name",
    )
    registry.require_create(session, context, Item, ["name"], {"name": "ok"})
    with pytest.raises(ValidationError):
        registry.require_create(session, context, Item, ["unknown"], {"unknown": "x"})
    with pytest.raises(UnAuthorizedError):
        registry.validate_context(AuthContext("app", ("a", "b", "c")))
    with pytest.raises(UnAuthorizedError):
        registry.scope_query(context, Item, session.query(Item).limit(1))
    registry.freeze()
    with pytest.raises(RuntimeError):
        registry.register(Item, key="other")
    session.close()
    engine.dispose()


def test_registry_alias_tenant_create_revocation_and_validation() -> None:
    Base = declarative_base()

    class TenantItem(SAFRSBase, Base):
        __tablename__ = "registry_tenant_items"
        id = Column(Integer, primary_key=True)
        tenant_id = Column(Integer, nullable=False)
        title = Column(String)

    with pytest.raises(ValueError):
        AuthorizationRegistry(table_name="invalid-name")
    with pytest.raises(ValueError):
        AuthorizationRegistry(max_subjects=0)

    registry = AuthorizationRegistry(metadata=Base.metadata)
    registry.register(TenantItem, key="tenant.item", tenant_column=TenantItem.tenant_id)
    with pytest.raises(ValueError):
        registry.register(TenantItem, key="tenant.item.again")
    assert registry.registrations == {TenantItem: "tenant.item"}

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    item = TenantItem(id=1, tenant_id=7, title="visible")
    session.add(item)
    session.commit()
    context = registry.validate_context(
        AuthContext("tenant:7", ("user:alice", "user:alice"), "7")
    )
    assert context == AuthContext("tenant:7", ("user:alice",), "7")
    assert registry.validate_context(None) is None
    with pytest.raises(TypeError):
        registry.validate_context(object())
    with pytest.raises(TypeError):
        registry.validate_context(AuthContext("tenant:7", "user:alice", "7"))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        registry.validate_context(AuthContext("", ("user:alice",), "7"))
    with pytest.raises(ValueError):
        registry.validate_context(AuthContext("x" * 256, ("user:alice",), "7"))

    for field in (None, "title"):
        registry.grant(
            session,
            scope_key="tenant:7",
            subject_key="user:alice",
            Model=TenantItem,
            action="read",
            object_id=1 if field is None else None,
            field=field,
            tenant_id="7" if field is None else None,
        )
    session.commit()
    ItemAlias = aliased(TenantItem)
    visible_aliases = registry.scope_query(
        context, ItemAlias, session.query(ItemAlias), fields=["title"]
    ).all()
    assert [row.id for row in visible_aliases] == [1]
    registry.require(session, context, item, "read", ["title"])

    for field in (None, "tenant_id", "title"):
        registry.grant(
            session,
            scope_key="tenant:7",
            subject_key="user:alice",
            Model=TenantItem,
            action="create",
            field=field,
        )
    registry.require_create(
        session,
        context,
        TenantItem,
        ["tenant_id", "title"],
        {"tenant_id": 7, "title": "new"},
    )
    with pytest.raises(UnAuthorizedError):
        registry.require_create(
            session,
            context,
            TenantItem,
            ["tenant_id", "title"],
            {"tenant_id": 8, "title": "wrong tenant"},
        )
    with pytest.raises(UnAuthorizedError):
        registry.require_create(session, context, TenantItem, ["title"], {"title": "missing"})
    with pytest.raises(ValueError):
        registry.grant(
            session,
            scope_key="tenant:7",
            subject_key="user:alice",
            Model=TenantItem,
            action="read",
            object_id=999,
            tenant_id="7",
        )
    with pytest.raises(ValueError):
        registry.grant(
            session,
            scope_key="tenant:7",
            subject_key="user:alice",
            Model=TenantItem,
            action="create",
            object_id=1,
            tenant_id="7",
        )
    with pytest.raises(ValueError):
        registry.revoke(
            session,
            scope_key="",
            subject_key="user:alice",
            Model=TenantItem,
            action="read",
            object_id=1,
        )

    assert registry.revoke(
        session,
        scope_key="tenant:7",
        subject_key="user:alice",
        Model=TenantItem,
        action="read",
        object_id=1,
    ) == 1
    session.commit()
    session.close()
    fresh_session = Session()
    assert registry.scope_query(context, TenantItem, fresh_session.query(TenantItem)).all() == []
    fresh_session.close()
    engine.dispose()


def test_sqlite_concurrent_grant_cannot_outlive_target_delete(tmp_path: Path) -> None:
    Base = declarative_base()

    class Resource(SAFRSBase, Base):
        __tablename__ = "registry_lifecycle_resources"
        id = Column(Integer, primary_key=True)

    registry = AuthorizationRegistry(metadata=Base.metadata)
    registry.register(Resource, key="lifecycle.resource")
    database_path = tmp_path / "authorization-lifecycle.sqlite"
    engine = create_engine(
        f"sqlite:///{database_path}", connect_args={"check_same_thread": False, "timeout": 5}
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    seed = Session()
    seed.add(Resource(id=1))
    seed.commit()
    seed.close()

    deleting = Session()
    registry.serialize_sqlite_write(deleting)
    target = deleting.get(Resource, 1)
    assert target is not None
    registry.delete_instance_grants(deleting, target)
    deleting.delete(target)
    deleting.flush()

    started = Event()
    outcome: list[str] = []

    def grant_concurrently() -> None:
        granting = Session()
        started.set()
        try:
            registry.grant(
                granting,
                scope_key="app",
                subject_key="user:alice",
                Model=Resource,
                action="read",
                object_id=1,
            )
            granting.commit()
            outcome.append("granted")
        except ValueError:
            granting.rollback()
            outcome.append("missing")
        finally:
            granting.close()

    worker = Thread(target=grant_concurrently)
    worker.start()
    assert started.wait(timeout=2)
    deleting.commit()
    worker.join(timeout=5)
    assert not worker.is_alive()
    assert outcome == ["missing"]
    verification = Session()
    assert verification.get(Resource, 1) is None
    assert verification.execute(select(registry.table.c.id)).all() == []
    verification.close()
    engine.dispose()


def test_registry_performance_fixture_uses_bounded_page_queries_and_index() -> None:
    Base = declarative_base()

    class Resource(SAFRSBase, Base):
        __tablename__ = "registry_performance_resources"
        id = Column(Integer, primary_key=True)
        title = Column(String)

    registry = AuthorizationRegistry(metadata=Base.metadata)
    registry.register(Resource, key="performance.resource")
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.execute(
        Resource.__table__.insert(),
        [{"id": resource_id, "title": f"resource-{resource_id}"} for resource_id in range(1, 10_001)],
    )
    grant_rows = [
        {
            "scope_key": "performance",
            "subject_key": f"group:{group_id}",
            "model_key": "performance.resource",
            "object_key": f"id:{resource_id}",
            "field_key": "",
            "action": "read",
        }
        for resource_id in range(1, 10_001)
        for group_id in range(5)
    ]
    grant_rows.append(
        {
            "scope_key": "performance",
            "subject_key": "group:0",
            "model_key": "performance.resource",
            "object_key": "",
            "field_key": "title",
            "action": "read",
        }
    )
    session.execute(registry.table.insert(), grant_rows)
    session.commit()
    context = AuthContext("performance", ("group:0",))
    scoped = registry.scope_query(context, Resource, session.query(Resource))
    page_statement = scoped.order_by(Resource.id).limit(50).statement
    compiled = str(
        page_statement.compile(engine, compile_kwargs={"literal_binds": True})
    )
    plan = session.execute(text("EXPLAIN QUERY PLAN " + compiled)).all()
    assert any("safrs_auth_grant" in str(row) and "INDEX" in str(row) for row in plan)

    statements: list[str] = []

    def count_statement(
        _connection: Any,
        _cursor: Any,
        statement: str,
        _parameters: Any,
        _context: Any,
        _executemany: bool,
    ) -> None:
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", count_statement)
    assert scoped.count() == 10_000
    page = scoped.order_by(Resource.id).limit(50).all()
    masks = registry.readable_fields(session, context, Resource, page)
    event.remove(engine, "before_cursor_execute", count_statement)
    assert len(page) == 50
    assert all(fields == frozenset({"title"}) for fields in masks.values())
    assert len(statements) == 3
    session.close()
    engine.dispose()


def _build_flask_registry_app() -> tuple[Flask, SQLAlchemy, type[Any], type[Any], AuthorizationRegistry]:
    db = SQLAlchemy()
    getter_calls: list[int] = []

    class Document(SAFRSBase, db.Model):
        __tablename__ = "registry_flask_documents"
        allow_client_generated_ids = True
        _s_upsert = True
        id = db.Column(db.Integer, primary_key=True)
        title = db.Column(db.String)
        secret = db.Column(db.String)

        @jsonapi_attr
        def dangerous(self: Any) -> str:
            getter_calls.append(self.id)
            return "must-not-run-without-a-field-grant"

        @classmethod
        @jsonapi_rpc(http_methods=["POST"])
        def mutate(cls: Any) -> str:
            cls.get_instance(1).title = "rpc-mutated"
            return "changed"

    class Child(SAFRSBase, db.Model):
        __tablename__ = "registry_flask_children"
        id = db.Column(db.Integer, primary_key=True)
        document_id = db.Column(db.Integer, db.ForeignKey("registry_flask_documents.id"))
        name = db.Column(db.String)

    Document.children = db.relationship(Child, backref="document")

    app = Flask("authorization-registry-flask")
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    db.init_app(app)
    registry = AuthorizationRegistry(metadata=db.metadata)
    registry.register(Document, key="flask.document")
    registry.register(Child, key="flask.child")

    def principal() -> AuthContext:
        user = request.headers.get("x-user", "anonymous")
        groups = ("group:staff",) if user == "alice" else ()
        return AuthContext("app", (f"user:{user}", *groups))

    with app.app_context():
        db.create_all()
        db.session.add_all(
            [
                Document(id=1, title="one", secret="alpha"),
                Document(id=2, title="two", secret="beta"),
                Child(id=10, document_id=1, name="visible-child"),
                Child(id=11, document_id=1, name="hidden-child"),
            ]
        )
        db.session.commit()
        for object_id, subject in ((1, "user:alice"), (2, "group:staff")):
            registry.grant(
                db.session,
                scope_key="app",
                subject_key=subject,
                Model=Document,
                action="read",
                object_id=object_id,
            )
        registry.grant(
            db.session,
            scope_key="app",
            subject_key="group:staff",
            Model=Document,
            action="read",
            field="title",
        )
        registry.grant(
            db.session,
            scope_key="app",
            subject_key="user:alice",
            Model=Document,
            action="read",
            object_id=1,
            field="secret",
        )
        registry.grant(
            db.session,
            scope_key="app",
            subject_key="user:alice",
            Model=Document,
            action="read",
            object_id=1,
            field="children",
        )
        registry.grant(
            db.session,
            scope_key="app",
            subject_key="user:alice",
            Model=Child,
            action="read",
            object_id=10,
        )
        registry.grant(
            db.session,
            scope_key="app",
            subject_key="user:alice",
            Model=Child,
            action="read",
            object_id=10,
            field="name",
        )
        for field in (None, "name", "document"):
            registry.grant(
                db.session,
                scope_key="app",
                subject_key="user:charlie",
                Model=Child,
                action="read",
                object_id=10,
                field=field,
            )
        db.session.commit()
        api = SafrsApi(
            app,
            host="localhost",
            swaggerui_blueprint=False,
            app_db=db,
            authorization=registry,
            principal_provider=principal,
        )
        api.expose_object(Document)
        api.expose_object(Child)
    setattr(app, "getter_calls", getter_calls)
    return app, db, Document, Child, registry


def test_flask_registry_rows_fields_filters_relationships_and_default_deny() -> None:
    app, _db, Document, _Child, _registry = _build_flask_registry_app()
    client = app.test_client()
    collection = f"/{Document._s_collection_name}/"

    response = client.get(collection, headers={"x-user": "alice"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["meta"]["total"] == 2
    assert [item["id"] for item in body["data"]] == ["1", "2"]
    assert body["data"][0]["attributes"] == {"title": "one", "secret": "alpha"}
    assert body["data"][1]["attributes"] == {"title": "two"}
    assert getattr(app, "getter_calls") == []

    hidden_filter = client.get(
        collection,
        headers={"x-user": "alice"},
        query_string={"filter[secret]": "beta"},
    )
    assert hidden_filter.status_code == 200
    assert hidden_filter.get_json()["data"] == []
    secret_sort = client.get(
        collection, headers={"x-user": "alice"}, query_string={"sort": "secret"}
    )
    assert [item["id"] for item in secret_sort.get_json()["data"]] == ["1"]

    included = client.get(
        f"{collection}1/",
        headers={"x-user": "alice"},
        query_string={"include": "children"},
    )
    assert included.status_code == 200
    included_body = included.get_json()
    assert [item["id"] for item in included_body["included"]] == ["10"]
    assert included_body["data"]["relationships"]["children"]["meta"]["total"] == 1

    relationship_response = client.get(
        f"{collection}1/children", headers={"x-user": "alice"}
    )
    assert relationship_response.status_code == 200
    assert relationship_response.get_json()["meta"]["total"] == 1
    assert [item["id"] for item in relationship_response.get_json()["data"]] == ["10"]
    assert client.get(
        f"{collection}1/children/11", headers={"x-user": "alice"}
    ).status_code == 404
    assert client.get(
        f"{collection}2/children", headers={"x-user": "alice"}
    ).status_code == 404

    to_one = client.get(
        f"/{_Child._s_collection_name}/10/",
        headers={"x-user": "charlie"},
        query_string={"include": "document"},
    )
    assert to_one.status_code == 200
    assert to_one.get_json()["data"]["relationships"]["document"]["data"] is None
    assert to_one.get_json().get("included", []) == []

    denied = client.get(collection, headers={"x-user": "bob"})
    assert denied.status_code == 200
    assert denied.get_json()["data"] == []
    assert client.get(f"{collection}1/", headers={"x-user": "bob"}).status_code == 404


def test_flask_registry_write_upsert_rpc_and_relationship_barriers() -> None:
    app, db, Document, Child, registry = _build_flask_registry_app()
    with app.app_context():
        for field in (None, "title"):
            registry.grant(
                db.session,
                scope_key="app",
                subject_key="user:alice",
                Model=Document,
                action="update",
                object_id=1,
                field=field,
            )
        for field in (None, "document_id"):
            registry.grant(
                db.session,
                scope_key="app",
                subject_key="user:alice",
                Model=Child,
                action="update",
                object_id=10,
                field=field,
            )
        for field in (None, "title"):
            registry.grant(
                db.session,
                scope_key="app",
                subject_key="user:creator",
                Model=Document,
                action="create",
                field=field,
            )
        registry.grant(
            db.session,
            scope_key="app",
            subject_key="user:alice",
            Model=Document,
            action="delete",
            object_id=1,
        )
        db.session.commit()

    client = app.test_client()
    collection = f"/{Document._s_collection_name}/"
    upsert = client.post(
        collection,
        headers={**JSONAPI_HEADERS, "x-user": "alice"},
        json=_document(Document, "1", title="updated"),
    )
    assert upsert.status_code == 200
    denied_field = client.patch(
        f"{collection}1/",
        headers={**JSONAPI_HEADERS, "x-user": "alice"},
        json=_document(Document, "1", secret="changed"),
    )
    assert denied_field.status_code == 403
    denied_same_value = client.patch(
        f"{collection}1/",
        headers={**JSONAPI_HEADERS, "x-user": "alice"},
        json=_document(Document, "1", secret="alpha"),
    )
    assert denied_same_value.status_code == 403

    denied_bulk = client.post(
        collection,
        headers={**JSONAPI_HEADERS, "x-user": "creator"},
        json={
            "data": [
                _document(Document, "3", title="must-roll-back")["data"],
                _document(Document, "1", title="not-authorized-to-upsert")["data"],
            ]
        },
    )
    assert denied_bulk.status_code == 403

    denied_create_response = client.post(
        collection,
        headers={**JSONAPI_HEADERS, "x-user": "creator"},
        json=_document(Document, "3", title="created"),
    )
    assert denied_create_response.status_code == 403

    rpc = client.post(
        f"{collection}mutate",
        headers={**JSONAPI_HEADERS, "x-user": "alice"},
        json={"meta": {"args": {}}},
    )
    assert rpc.status_code == 403

    relationship = client.post(
        f"{collection}1/children",
        headers={**JSONAPI_HEADERS, "x-user": "alice"},
        json={"data": [{"type": Child._s_type, "id": "11"}]},
    )
    assert relationship.status_code == 403
    scalar_fk = client.patch(
        f"/{Child._s_collection_name}/10/",
        headers={**JSONAPI_HEADERS, "x-user": "alice"},
        json=_document(Child, "10", document_id=2),
    )
    assert scalar_fk.status_code == 403
    cascade_delete = client.delete(f"{collection}1/", headers={"x-user": "alice"})
    assert cascade_delete.status_code == 403
    with app.app_context():
        assert db.session.get(Document, 1).title == "updated"
        assert db.session.get(Document, 1).secret == "alpha"
        assert db.session.get(Child, 10).document_id == 1
        assert db.session.get(Child, 11).document_id == 1
        assert db.session.get(Document, 3) is None


def test_flask_registry_create_response_and_delete_cleanup_are_atomic() -> None:
    app, db, Document, _Child, registry = _build_flask_registry_app()
    with app.app_context():
        for action, field, object_id in (
            ("create", None, None),
            ("create", "title", None),
            ("read", None, None),
            ("read", "title", None),
            ("delete", None, 2),
        ):
            registry.grant(
                db.session,
                scope_key="app",
                subject_key="user:owner",
                Model=Document,
                action=action,
                object_id=object_id,
                field=field,
            )
        db.session.commit()

    client = app.test_client()
    collection = f"/{Document._s_collection_name}/"
    created = client.post(
        collection,
        headers={**JSONAPI_HEADERS, "x-user": "owner"},
        json=_document(Document, "3", title="created"),
    )
    assert created.status_code == 201
    deleted = client.delete(f"{collection}2/", headers={"x-user": "owner"})
    assert deleted.status_code == 204
    with app.app_context():
        assert db.session.get(Document, 3).title == "created"
        assert db.session.get(Document, 2) is None
        assert db.session.execute(
            select(registry.table.c.id).where(
                registry.table.c.model_key == "flask.document",
                registry.table.c.object_key == "id:2",
            )
        ).all() == []


def test_flask_registry_after_create_bootstraps_grants_in_same_transaction() -> None:
    app, db, Document, _Child, registry = _build_flask_registry_app()

    def bootstrap(
        active_registry: AuthorizationRegistry,
        session: Any,
        context: AuthContext,
        instance: Any,
    ) -> None:
        bootstrap_fields = (
            ("title",)
            if context.subject_keys[0] == "user:deny-bootstrap"
            else (None, "title")
        )
        for field in bootstrap_fields:
            active_registry.grant(
                session,
                scope_key=context.scope_key,
                subject_key=context.subject_keys[0],
                Model=Document,
                action="read",
                object_id=instance.id,
                field=field,
            )

    registry.after_create = bootstrap
    with app.app_context():
        for subject in ("user:bootstrap", "user:deny-bootstrap"):
            for field in (None, "title"):
                registry.grant(
                    db.session,
                    scope_key="app",
                    subject_key=subject,
                    Model=Document,
                    action="create",
                    field=field,
                )
        db.session.commit()

    denied = app.test_client().post(
        f"/{Document._s_collection_name}/",
        headers={**JSONAPI_HEADERS, "x-user": "deny-bootstrap"},
        json=_document(Document, "5", title="must-roll-back"),
    )
    assert denied.status_code == 403

    response = app.test_client().post(
        f"/{Document._s_collection_name}/",
        headers={**JSONAPI_HEADERS, "x-user": "bootstrap"},
        json=_document(Document, "4", title="bootstrapped"),
    )
    assert response.status_code == 201
    assert response.get_json()["data"]["attributes"] == {"title": "bootstrapped"}
    with app.app_context():
        assert db.session.get(Document, 4).title == "bootstrapped"
        assert db.session.get(Document, 5) is None
        assert db.session.execute(
            select(registry.table.c.id).where(
                registry.table.c.subject_key == "user:deny-bootstrap",
                registry.table.c.object_key == "id:5",
            )
        ).all() == []
        fields = db.session.execute(
            select(registry.table.c.field_key).where(
                registry.table.c.subject_key == "user:bootstrap",
                registry.table.c.object_key == "id:4",
                registry.table.c.action == "read",
            )
        ).scalars().all()
        assert set(fields) == {"", "title"}


def test_unregistered_parent_does_not_bypass_registered_relationship_target() -> None:
    db = SQLAlchemy()

    class PublicParent(SAFRSBase, db.Model):
        __tablename__ = "registry_public_parents"
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String)

    class ProtectedChild(SAFRSBase, db.Model):
        __tablename__ = "registry_protected_children"
        id = db.Column(db.Integer, primary_key=True)
        parent_id = db.Column(
            db.Integer, db.ForeignKey("registry_public_parents.id"), nullable=False
        )
        name = db.Column(db.String)

    class PublicPointer(SAFRSBase, db.Model):
        __tablename__ = "registry_public_pointers"
        id = db.Column(db.Integer, primary_key=True)
        protected_child_id = db.Column(
            db.Integer, db.ForeignKey("registry_protected_children.id"), nullable=False
        )
        label = db.Column(db.String)

        @jsonapi_attr
        def child_alias(self: Any) -> int:
            return self.protected_child_id

        @child_alias.setter
        def child_alias(self: Any, value: int) -> None:
            self.protected_child_id = value

    PublicParent.children = db.relationship(ProtectedChild, backref="parent")
    PublicPointer.protected_child = db.relationship(ProtectedChild)
    app = Flask("authorization-registry-traversal")
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    db.init_app(app)
    registry = AuthorizationRegistry(metadata=db.metadata)
    registry.register(ProtectedChild, key="traversal.child")

    def principal() -> AuthContext:
        return AuthContext("app", ("user:alice",))

    with app.app_context():
        db.create_all()
        db.session.add(PublicParent(id=1, name="public"))
        db.session.add_all(
            [
                ProtectedChild(id=1, parent_id=1, name="visible"),
                ProtectedChild(id=2, parent_id=1, name="hidden"),
            ]
        )
        db.session.add(PublicPointer(id=1, protected_child_id=1, label="pointer"))
        db.session.commit()
        for field in (None, "name"):
            registry.grant(
                db.session,
                scope_key="app",
                subject_key="user:alice",
                Model=ProtectedChild,
                action="read",
                object_id=1,
                field=field,
            )
        db.session.commit()
        api = SafrsApi(
            app,
            host="localhost",
            swaggerui_blueprint=False,
            app_db=db,
            authorization=registry,
            principal_provider=principal,
        )
        api.expose_object(PublicParent)
        api.expose_object(ProtectedChild)
        api.expose_object(PublicPointer)

    public_response = app.test_client().get(f"/{PublicParent._s_collection_name}/1/")
    assert public_response.status_code == 200
    assert public_response.get_json()["data"]["attributes"] == {"name": "public"}
    response = app.test_client().get(
        f"/{PublicParent._s_collection_name}/1/", query_string={"include": "children"}
    )
    assert response.status_code == 200
    body = response.get_json()
    assert [item["id"] for item in body["included"]] == ["1"]
    assert body["data"]["relationships"]["children"]["meta"]["total"] == 1

    delete_parent = app.test_client().delete(f"/{PublicParent._s_collection_name}/1/")
    assert delete_parent.status_code == 403
    mutate_pointer = app.test_client().patch(
        f"/{PublicPointer._s_collection_name}/1/",
        headers=JSONAPI_HEADERS,
        json=_document(PublicPointer, "1", protected_child_id=2),
    )
    assert mutate_pointer.status_code == 403
    mutate_pointer_alias = app.test_client().patch(
        f"/{PublicPointer._s_collection_name}/1/",
        headers=JSONAPI_HEADERS,
        json=_document(PublicPointer, "1", child_alias=2),
    )
    assert mutate_pointer_alias.status_code == 403
    with app.app_context():
        assert db.session.get(PublicParent, 1) is not None
        assert db.session.get(PublicPointer, 1).protected_child_id == 1


FastBase = declarative_base()


class FastDocument(SAFRSBase, FastBase):
    __tablename__ = "registry_fastapi_documents"
    allow_client_generated_ids = True
    _s_upsert = True
    id = Column(String, primary_key=True)
    title = Column(String)
    secret = Column(String)

    @classmethod
    @jsonapi_rpc(http_methods=["POST"])
    def mutate(cls: Any) -> str:
        cls.get_instance("one").title = "rpc-mutated"
        return "changed"


class FastChild(SAFRSBase, FastBase):
    __tablename__ = "registry_fastapi_children"
    id = Column(String, primary_key=True)
    document_id = Column(
        String, ForeignKey("registry_fastapi_documents.id"), nullable=False
    )
    name = Column(String)


FastDocument.children = relationship(FastChild, backref="document")


@pytest.fixture
def fastapi_registry_app(monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, Any, AuthorizationRegistry]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    database = SimpleNamespace(session=session, Model=FastBase, metadata=FastBase.metadata)
    monkeypatch.setattr(safrs, "DB", database)
    registry = AuthorizationRegistry(metadata=FastBase.metadata)
    registry.register(FastDocument, key="fastapi.document")
    registry.register(FastChild, key="fastapi.child")
    FastBase.metadata.create_all(engine)
    session.add_all(
        [
            FastDocument(id="one", title="one", secret="alpha"),
            FastDocument(id="two", title="two", secret="beta"),
            FastChild(id="child-one", document_id="one", name="visible child"),
            FastChild(id="child-two", document_id="one", name="hidden child"),
        ]
    )
    session.commit()
    for object_id in ("one", "two"):
        registry.grant(
            session,
            scope_key="app",
            subject_key="user:alice",
            Model=FastDocument,
            action="read",
            object_id=object_id,
        )
    registry.grant(
        session,
        scope_key="app",
        subject_key="user:alice",
        Model=FastDocument,
        action="read",
        field="title",
    )
    registry.grant(
        session,
        scope_key="app",
        subject_key="user:alice",
        Model=FastDocument,
        action="read",
        object_id="one",
        field="secret",
    )
    registry.grant(
        session,
        scope_key="app",
        subject_key="user:alice",
        Model=FastDocument,
        action="read",
        object_id="one",
        field="children",
    )
    for field in (None, "name"):
        registry.grant(
            session,
            scope_key="app",
            subject_key="user:alice",
            Model=FastChild,
            action="read",
            object_id="child-one",
            field=field,
        )
    for field in (None, "title"):
        registry.grant(
            session,
            scope_key="app",
            subject_key="user:alice",
            Model=FastDocument,
            action="update",
            object_id="one",
            field=field,
        )
    for action, field, object_id in (
        ("create", None, None),
        ("create", "title", None),
        ("read", None, None),
        ("read", "title", None),
        ("delete", None, "two"),
    ):
        registry.grant(
            session,
            scope_key="app",
            subject_key="user:owner",
            Model=FastDocument,
            action=action,
            object_id=object_id,
            field=field,
        )
    session.commit()

    principal_events: list[str] = []

    async def principal(
        x_user: str = Header(default="anonymous"),
    ) -> AsyncIterator[AuthContext]:
        principal_events.append(f"setup:{x_user}")
        try:
            yield AuthContext("app", (f"user:{x_user}",))
        finally:
            principal_events.append(f"teardown:{x_user}")

    app = FastAPI()
    api = SafrsFastAPI(
        app,
        app_db=database,
        authorization=registry,
        principal_dependency=principal,
    )
    api.expose_object(FastDocument)
    api.expose_object(FastChild)
    app.state.principal_events = principal_events
    client = TestClient(app)
    yield client, session, registry
    client.close()
    session.close()
    engine.dispose()


def test_fastapi_registry_read_filter_upsert_and_rpc(
    fastapi_registry_app: tuple[TestClient, Any, AuthorizationRegistry],
) -> None:
    client, session, _registry = fastapi_registry_app
    collection = f"/{FastDocument._s_collection_name}/"
    response = client.get(collection, headers={"x-user": "alice"})
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 2
    assert body["data"][0]["attributes"] == {"title": "one", "secret": "alpha"}
    assert body["data"][1]["attributes"] == {"title": "two"}
    assert client.app.state.principal_events == ["setup:alice", "teardown:alice"]
    assert client.get(collection, headers={"x-user": "bob"}).json()["data"] == []

    filtered = client.get(
        collection,
        headers={"x-user": "alice"},
        params={"filter[secret]": "beta"},
    )
    assert filtered.status_code == 200
    assert filtered.json()["data"] == []

    related = client.get(
        f"{collection}one/children", headers={"x-user": "alice"}
    )
    assert related.status_code == 200
    assert related.json()["meta"]["total"] == 1
    assert [item["id"] for item in related.json()["data"]] == ["child-one"]
    relationship_write = client.post(
        f"{collection}one/children",
        headers={**JSONAPI_HEADERS, "x-user": "alice"},
        json={"data": [{"type": FastChild._s_type, "id": "child-two"}]},
    )
    assert relationship_write.status_code == 403

    upsert = client.post(
        collection,
        headers={**JSONAPI_HEADERS, "x-user": "alice"},
        json=_document(FastDocument, "one", title="updated"),
    )
    assert upsert.status_code == 200
    denied = client.patch(
        f"{collection}one/",
        headers={**JSONAPI_HEADERS, "x-user": "alice"},
        json=_document(FastDocument, "one", secret="changed"),
    )
    assert denied.status_code == 403
    rpc = client.post(
        f"{collection}mutate",
        headers={**JSONAPI_HEADERS, "x-user": "alice"},
        json={"meta": {"args": {}}},
    )
    assert rpc.status_code == 403
    created = client.post(
        collection,
        headers={**JSONAPI_HEADERS, "x-user": "owner"},
        json=_document(FastDocument, "three", title="created"),
    )
    assert created.status_code == 201
    deleted = client.delete(f"{collection}two/", headers={"x-user": "owner"})
    assert deleted.status_code == 204
    session.expire_all()
    assert session.get(FastDocument, "one").title == "updated"
    assert session.get(FastDocument, "one").secret == "alpha"
    assert session.get(FastDocument, "three").title == "created"
    assert session.get(FastDocument, "two") is None
    assert session.execute(
        select(_registry.table.c.id).where(
            _registry.table.c.model_key == "fastapi.document",
            _registry.table.c.object_key == "id:two",
        )
    ).all() == []
