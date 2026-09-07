"""Real SQLite requests with cold ORM sessions and deterministic SQL budgets."""

from __future__ import annotations

from dataclasses import dataclass
import json
from types import SimpleNamespace
from typing import Any

import pytest
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.orm import selectinload
from sqlalchemy.pool import StaticPool

import safrs
from safrs import SAFRSBase, SafrsApi


db = SQLAlchemy()
PARENTS = 80
CHILDREN = 12
LABELS = 8


class PerfParent(SAFRSBase, db.Model):
    __tablename__ = "perf_parents"
    _s_collection_name = "perf_parents"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), index=True)
    description = db.Column(db.Text)
    children = db.relationship("PerfChild", back_populates="parent")
    dynamic_children = db.relationship("PerfChild", lazy="dynamic", viewonly=True)
    labels = db.relationship("PerfLabel")


class PerfChild(SAFRSBase, db.Model):
    __tablename__ = "perf_children"
    _s_collection_name = "perf_children"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80))
    parent_id = db.Column(db.Integer, db.ForeignKey("perf_parents.id"), index=True)
    parent = db.relationship(PerfParent, back_populates="children")


class PerfLabel(SAFRSBase, db.Model):
    __tablename__ = "perf_labels"
    _s_collection_name = "perf_labels"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80))
    parent_id = db.Column(db.Integer, db.ForeignKey("perf_parents.id"), index=True)


def seed(engine: Any) -> None:
    db.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(PerfParent.__table__.insert(), [
            {"id": n, "name": f"parent-{n:03}", "description": "x" * 2048} for n in range(1, PARENTS + 1)
        ])
        for model, fanout in ((PerfChild, CHILDREN), (PerfLabel, LABELS)):
            conn.execute(model.__table__.insert(), [
                {"id": (n - 1) * fanout + k + 1, "name": f"item-{k:02}", "parent_id": n}
                for n in range(1, PARENTS + 1) for k in range(fanout)
            ])


@dataclass
class Harness:
    backend: str
    engine: Any
    client: Any
    database: Any
    app: Any

    def reset(self) -> None:
        if self.backend == "flask":
            with self.app.app_context():
                self.database.session.remove()
        else:
            self.database.session.remove()

    def get(self, path: str, params: dict[str, Any]) -> bytes:
        if self.backend == "flask":
            response = self.client.get(path, query_string=params)
            body = response.data
        else:
            response = self.client.get(path.rstrip("/"), params=params)
            assert not response.history, "Redirects must not contaminate request latency"
            body = response.content
        assert response.status_code == 200, body.decode()
        assert response.headers["content-type"].startswith("application/vnd.api+json")
        return body


@pytest.fixture(scope="module", params=["flask", "fastapi"])
def harness(request: pytest.FixtureRequest) -> Any:
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(safrs, "DB", safrs.DB)  # Flask registration updates this legacy global.
        patch.setattr(safrs.SAFRS, "OPTIMIZED_LOADING", True)
        patch.setattr(safrs.SAFRS, "DEFAULT_INCLUDED", "")
        if request.param == "flask":
            app = Flask(__name__)
            app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True, DEFAULT_INCLUDED="", OPTIMIZED_LOADING=True)
            db.init_app(app)
            with app.app_context():
                engine = db.engine
                seed(engine)
                api = SafrsApi(app, app_db=db, swaggerui_blueprint=False)
                for model in (PerfParent, PerfChild, PerfLabel):
                    api.expose_object(model)
            fixture = Harness("flask", engine, app.test_client(), db, app)
            try:
                yield fixture
            finally:
                fixture.reset()
                engine.dispose()
        else:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            from safrs.fastapi.api import SafrsFastAPI

            engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
            # Requests are serial. A fixed scope lets both test and worker thread
            # remove the same session between samples; it is not a server recipe.
            database = SimpleNamespace(
                session=scoped_session(sessionmaker(bind=engine), scopefunc=lambda: 1), Model=db.Model,
            )
            seed(engine)
            app = FastAPI()
            api = SafrsFastAPI(app, app_db=database)
            for model in (PerfParent, PerfChild, PerfLabel):
                api.expose_object(model)
            try:
                with TestClient(app) as client:
                    yield Harness("fastapi", engine, client, database, app)
            finally:
                database.session.remove()
                engine.dispose()


def request_observation(observe: Any, harness: Harness, path: str, params: dict[str, Any]) -> Any:
    return observe(
        harness.engine, lambda: harness.get(path, params), harness.reset,
        backend=harness.backend, path=path, params=params,
        parents=PARENTS, children_per_parent=CHILDREN, labels_per_parent=LABELS,
    )


@pytest.mark.parametrize("limit", [5, 25])
@pytest.mark.parametrize("variant", ["plain", "sparse", "filtered", "offset"])
def test_collection_budget(harness: Harness, observe: Any, limit: int, variant: str) -> None:
    params: dict[str, Any] = {"page[limit]": limit, "sort": "id"}
    total, offset = PARENTS, 0
    if variant == "sparse":
        params[f"fields[{PerfParent._s_type}]"] = "name"
    elif variant == "filtered":
        params["filter[name]"] = "parent-001"
        total = 1
    elif variant == "offset":
        params["page[offset]"] = offset = 50
    result = request_observation(observe, harness, "/perf_parents/", params)
    assert len(result.payload["data"]) == min(limit, total - offset)
    assert result.payload["meta"]["total"] == total
    assert [int(item["id"]) for item in result.payload["data"]] == list(range(offset + 1, min(offset + limit, total) + 1))
    assert not result.payload["included"]
    for sample in result.samples:
        assert sample.sql_count <= 2  # One scoped COUNT and one bounded page.
        assert sample.count_queries <= 1
        assert sample.orm_loads == len(result.payload["data"])
    if variant == "sparse":
        assert all(set(item["attributes"]) == {"name"} for item in result.payload["data"])


@pytest.mark.parametrize("limit", [5, 25])
@pytest.mark.parametrize("include", ["children", "children.parent", "children,labels", "dynamic_children"])
def test_include_budget(harness: Harness, observe: Any, limit: int, include: str) -> None:
    result = request_observation(observe, harness, "/perf_parents/", {"page[limit]": limit, "sort": "id", "include": include})
    assert len(result.payload["data"]) == limit
    assert result.payload["meta"]["total"] == PARENTS
    included = result.payload["included"]
    identities = {(item["type"], item["id"]) for item in included}
    assert len(identities) == len(included)
    # Included relationship limits inherit the top-level page limit.
    fanout = min(CHILDREN, limit) + (min(LABELS, limit) if include == "children,labels" else 0)
    assert len(included) == limit * fanout
    for sample in result.samples:
        budget = 2 + 3 * limit if include == "dynamic_children" else 2
        assert sample.sql_count <= budget
        assert sample.count_queries <= (1 + 2 * limit if include == "dynamic_children" else 1)
        loaded_fanout = fanout if include == "dynamic_children" else CHILDREN + (LABELS if include == "children,labels" else 0)
        assert sample.orm_loads == limit * (1 + loaded_fanout)


@pytest.mark.parametrize("relationship", ["children", "dynamic_children"])
def test_relationship_page_budget(harness: Harness, observe: Any, relationship: str) -> None:
    result = request_observation(observe, harness, f"/perf_parents/1/{relationship}", {"page[limit]": 5, "sort": "id"})
    assert [item["id"] for item in result.payload["data"]] == [str(n) for n in range(1, 6)]
    for sample in result.samples:
        # These ceilings expose existing work; they are intentionally not goals.
        budget = CHILDREN + 2 if harness.backend == "flask" and relationship == "children" else 3
        assert sample.sql_count <= budget
        assert sample.orm_loads <= 1 + CHILDREN


@pytest.mark.parametrize("limit", [5, 25])
@pytest.mark.parametrize("strategy", ["lazy", "selectin"])
def test_loader_comparison(harness: Harness, observe: Any, monkeypatch: pytest.MonkeyPatch, limit: int, strategy: str) -> None:
    """Compare optional strategies against the production joined-load document."""
    from safrs import jsonapi_filters

    params = {"page[limit]": limit, "sort": "id", "include": "children,labels"}
    harness.reset()
    expected = json.loads(harness.get("/perf_parents/", params))
    if strategy == "selectin":
        # Test-only prototype for sibling collections; no runtime strategy change.
        monkeypatch.setattr(jsonapi_filters, "joinedload", selectinload)
    else:
        monkeypatch.setattr(safrs.SAFRS, "OPTIMIZED_LOADING", False)
        if harness.backend == "flask":
            monkeypatch.setitem(harness.app.config, "OPTIMIZED_LOADING", False)
    result = request_observation(observe, harness, "/perf_parents/", params)
    # Included resource order is unspecified; compare every resource by identity.
    def normalized(document):
        return {**document, "included": sorted(document["included"], key=lambda item: (item["type"], item["id"]))}

    assert normalized(result.payload) == normalized(expected)
    for sample in result.samples:
        assert sample.sql_count <= (4 if strategy == "selectin" else 2 + 2 * limit)
        assert sample.orm_loads == limit * (1 + CHILDREN + LABELS)


@pytest.mark.parametrize("lazy", ["select", "joined", "subquery", "selectin", "dynamic", "noload", "raise"])
def test_loader_uses_mapper_metadata(monkeypatch: pytest.MonkeyPatch, lazy: str) -> None:
    """Real InstrumentedAttributes lack .lazy; mocks must not hide that fact."""
    from safrs.jsonapi_context import JsonApiContext, reset_jsonapi_context, set_jsonapi_context
    from safrs.jsonapi_filters import create_query
    from safrs.runtime import bind_db

    engine = create_engine("sqlite://")
    session = sessionmaker(bind=engine)()
    monkeypatch.setattr(safrs.SAFRS, "OPTIMIZED_LOADING", True)
    monkeypatch.setattr(PerfParent.children.property, "lazy", lazy)
    token = set_jsonapi_context(JsonApiContext(query_params={"include": "children"}))
    try:
        with bind_db(SimpleNamespace(session=session)):
            assert not hasattr(PerfParent.children, "lazy")
            sql = str(create_query(PerfParent).statement)
        assert ("LEFT OUTER JOIN perf_children" in sql) == (lazy in {"select", "joined", "subquery", "selectin"})
    finally:
        reset_jsonapi_context(token)
        session.close()
        engine.dispose()
