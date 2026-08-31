"""SEC-02 regression tests: per-target-row authorization for relationship
linkage, nested writes, include traversal and cascade deletes.

A caller who may edit a parent must not be able to link, unlink, traverse,
update, or cascade-delete a target row that the target's object-level
policy denies.

Two policy styles are covered per adapter:
- an object-level model hook (``_s_check_instance_access``);
- the target's instance-GET route policy (Flask decorators / FastAPI
  dependencies), replayed with the target row's id.
"""

from __future__ import annotations

from functools import wraps
from typing import Any

import pytest
from flask import Flask, abort
from flask_sqlalchemy import SQLAlchemy

import safrs
from safrs import SAFRSBase, SafrsApi
from safrs.errors import UnAuthorizedError

JSONAPI_HEADERS = {"Content-Type": "application/vnd.api+json"}

# ---------------------------------------------------------------------------
# Flask
# ---------------------------------------------------------------------------

flask_db = SQLAlchemy()
_FLASK_DENIED: set[int] = set()


class _TargetParent(SAFRSBase, flask_db.Model):  # type: ignore[name-defined]
    __tablename__ = "sec02_target_parents"
    _s_type = "TargetParent"

    id = flask_db.Column(flask_db.Integer, primary_key=True)
    title = flask_db.Column(flask_db.String(120), nullable=False, default="")
    audit_child_id = flask_db.Column(flask_db.Integer, flask_db.ForeignKey("sec02_target_children.id"))
    children = flask_db.relationship(
        "_TargetChild",
        back_populates="parent",
        cascade="all, delete-orphan",
        foreign_keys="_TargetChild.parent_id",
    )
    audit_child = flask_db.relationship(
        "_TargetChild",
        back_populates="auditing_parent",
        uselist=False,
        foreign_keys=[audit_child_id],
    )


class _TargetChild(SAFRSBase, flask_db.Model):  # type: ignore[name-defined]
    __tablename__ = "sec02_target_children"
    _s_type = "TargetChild"

    id = flask_db.Column(flask_db.Integer, primary_key=True)
    secret = flask_db.Column(flask_db.String(120), nullable=False, default="")
    parent_id = flask_db.Column(flask_db.Integer, flask_db.ForeignKey("sec02_target_parents.id"))
    _s_upsert = True
    allow_client_generated_ids = True
    parent = flask_db.relationship("_TargetParent", back_populates="children", foreign_keys=[parent_id])
    auditing_parent = flask_db.relationship(
        "_TargetParent", back_populates="audit_child",
        foreign_keys="_TargetParent.audit_child_id",
    )

    def _s_check_instance_access(self: Any, action: str = "read") -> bool:
        if self.id in _FLASK_DENIED:
            raise UnAuthorizedError(f"child {self.id} denied for {action}")
        return True


def _build_flask_app() -> Flask:
    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    flask_db.init_app(app)
    with app.app_context():
        flask_db.create_all()
        flask_db.session.add_all(
            [
                _TargetParent(id=1, title="one"),
                _TargetParent(id=2, title="two"),
                _TargetChild(id=1, secret="s1", parent_id=1),
                _TargetChild(id=2, secret="s2", parent_id=1),
                _TargetChild(id=3, secret="s3", parent_id=2),
            ]
        )
        flask_db.session.get(_TargetParent, 1).audit_child_id = 1
        flask_db.session.commit()
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False, app_db=flask_db)
        api.expose_object(_TargetParent)
        api.expose_object(_TargetChild)
    return app


@pytest.fixture(autouse=True)
def _reset_flask_denied() -> Any:
    _FLASK_DENIED.clear()
    yield
    _FLASK_DENIED.clear()


def test_flask_linkage_denies_target_rows_denied_by_object_hook() -> None:
    app = _build_flask_app()
    _FLASK_DENIED.add(1)
    client = app.test_client()

    # to-many add
    add = client.patch(
        "/sec02_target_parents/2/children",
        json={"data": [{"type": "TargetChild", "id": "1"}]},
        headers=JSONAPI_HEADERS,
    )
    assert add.status_code == 403
    post = client.post(
        "/sec02_target_parents/2/children",
        json={"data": [{"type": "TargetChild", "id": "1"}]},
        headers=JSONAPI_HEADERS,
    )
    assert post.status_code == 403
    with app.app_context():
        assert flask_db.session.get(_TargetChild, 1).parent_id == 1

    # to-many removal of a denied member
    remove = client.delete(
        "/sec02_target_parents/1/children",
        json={"data": [{"type": "TargetChild", "id": "1"}]},
        headers=JSONAPI_HEADERS,
    )
    assert remove.status_code == 403
    with app.app_context():
        assert flask_db.session.get(_TargetChild, 1).parent_id == 1

    # to-one set and clear of a denied target
    set_one = client.patch(
        "/sec02_target_parents/2/audit_child",
        json={"data": {"type": "TargetChild", "id": "1"}},
        headers=JSONAPI_HEADERS,
    )
    assert set_one.status_code == 403
    clear_one = client.patch(
        "/sec02_target_parents/1/audit_child",
        json={"data": None},
        headers=JSONAPI_HEADERS,
    )
    assert clear_one.status_code == 403
    with app.app_context():
        assert flask_db.session.get(_TargetParent, 1).audit_child_id == 1


def test_flask_replacement_denies_when_a_removed_member_is_denied() -> None:
    app = _build_flask_app()
    _FLASK_DENIED.add(1)
    client = app.test_client()

    # Replacing [1, 2] with [2] removes denied child 1 -> denied as a whole.
    response = client.patch(
        "/sec02_target_parents/1/children",
        json={"data": [{"type": "TargetChild", "id": "2"}]},
        headers=JSONAPI_HEADERS,
    )
    assert response.status_code == 403
    with app.app_context():
        parent = flask_db.session.get(_TargetParent, 1)
        assert sorted(child.id for child in parent.children) == [1, 2]


def test_flask_nested_write_denies_target_rows() -> None:
    app = _build_flask_app()
    _FLASK_DENIED.add(1)
    client = app.test_client()

    # Nested upsert: the payload names an existing child by id and rewrites
    # its attributes, so the child row's object-level policy applies.
    response = client.post(
        "/sec02_target_parents/",
        headers=JSONAPI_HEADERS,
        json={
            "data": {
                "type": "TargetParent",
                "attributes": {"title": "new"},
                "relationships": {
                    "children": {
                        "data": [
                            {"type": "TargetChild", "id": "1", "attributes": {"secret": "hijacked"}}
                        ]
                    }
                },
            }
        },
    )
    assert response.status_code == 403
    with app.app_context():
        assert flask_db.session.get(_TargetChild, 1).secret == "s1"
        assert flask_db.session.query(_TargetParent).filter_by(title="new").first() is None
        assert flask_db.session.query(_TargetChild).count() == 3


def test_flask_include_omits_denied_target_rows() -> None:
    app = _build_flask_app()
    _FLASK_DENIED.add(1)
    client = app.test_client()

    response = client.get("/sec02_target_parents/1/", query_string={"include": "children"})
    assert response.status_code == 200
    payload = response.get_json()
    included_ids = {item["id"] for item in payload.get("included", [])}
    assert included_ids == {"2"}

    allowed = client.get("/sec02_target_parents/2/", query_string={"include": "children"})
    assert {item["id"] for item in allowed.get_json()["included"]} == {"3"}


def test_flask_direct_read_denies_denied_rows() -> None:
    app = _build_flask_app()
    _FLASK_DENIED.add(1)
    client = app.test_client()

    denied = client.get("/sec02_target_children/1/")
    assert denied.status_code == 403
    allowed = client.get("/sec02_target_children/2/")
    assert allowed.status_code == 200


def test_flask_cascade_delete_denies_when_a_doomed_row_is_denied() -> None:
    app = _build_flask_app()
    _FLASK_DENIED.add(1)
    client = app.test_client()

    response = client.delete("/sec02_target_parents/1/")
    assert response.status_code == 403
    with app.app_context():
        assert flask_db.session.get(_TargetParent, 1) is not None
        assert flask_db.session.get(_TargetChild, 1) is not None
        assert flask_db.session.get(_TargetChild, 2) is not None


def test_flask_allowed_target_rows_keep_working() -> None:
    app = _build_flask_app()
    client = app.test_client()

    response = client.patch(
        "/sec02_target_parents/2/children",
        json={"data": [{"type": "TargetChild", "id": "2"}]},
        headers=JSONAPI_HEADERS,
    )
    assert response.status_code == 200
    with app.app_context():
        assert flask_db.session.get(_TargetChild, 2).parent_id == 2

    include = client.get("/sec02_target_parents/1/", query_string={"include": "children"})
    assert {item["id"] for item in include.get_json()["included"]} == {"1"}


def test_flask_row_aware_get_decorator_denies_target_rows() -> None:
    """The target's instance-GET policy is replayed with the target row's id
    in the view kwargs (row-aware decorators see the target, not the parent)."""

    def make_row_denier(child_id: int) -> Any:
        def decorator(function: Any) -> Any:
            @wraps(function)
            def wrapped(*args: Any, **kwargs: Any) -> Any:
                if str(kwargs.get(_TargetChild._s_object_id, "")) == str(child_id):
                    abort(401)
                return function(*args, **kwargs)

            return wrapped

        return decorator

    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    flask_db.init_app(app)
    with app.app_context():
        flask_db.create_all()
        flask_db.session.add_all(
            [
                _TargetParent(id=1, title="one"),
                _TargetParent(id=2, title="two"),
                _TargetChild(id=1, secret="s1", parent_id=1),
                _TargetChild(id=3, secret="s3", parent_id=2),
            ]
        )
        flask_db.session.commit()
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False, app_db=flask_db)
        api.expose_object(_TargetParent)
        api.expose_object(_TargetChild, method_decorators={"get": [make_row_denier(1)]})
    client = app.test_client()

    denied = client.patch(
        "/sec02_target_parents/2/children",
        json={"data": [{"type": "TargetChild", "id": "1"}]},
        headers=JSONAPI_HEADERS,
    )
    assert denied.status_code == 401
    allowed = client.post(
        "/sec02_target_parents/1/children",
        json={"data": [{"type": "TargetChild", "id": "3"}]},
        headers=JSONAPI_HEADERS,
    )
    assert allowed.status_code in (200, 204)
    with app.app_context():
        assert flask_db.session.get(_TargetChild, 3).parent_id == 1


# ---------------------------------------------------------------------------
# FastAPI
# ---------------------------------------------------------------------------

fastapi_tests = pytest.importorskip("fastapi")
from fastapi import Depends, FastAPI, HTTPException, Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import Column, ForeignKey, Integer, String  # noqa: E402
from sqlalchemy.orm import declarative_base, relationship, scoped_session, sessionmaker  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from safrs.fastapi.api import SafrsFastAPI  # noqa: E402

FastBase = declarative_base()
_FASTAPI_DENIED: set[int] = set()


class _FastTargetParent(SAFRSBase, FastBase):  # type: ignore[misc]
    __tablename__ = "sec02_fast_target_parents"
    _s_type = "FastTargetParent"
    _s_collection_name = "FastTargetParents"

    id = Column(Integer, primary_key=True)
    children = relationship("_FastTargetChild", back_populates="parent", cascade="all, delete-orphan")


class _FastTargetChild(SAFRSBase, FastBase):  # type: ignore[misc]
    __tablename__ = "sec02_fast_target_children"
    _s_type = "FastTargetChild"
    _s_collection_name = "FastTargetChildren"

    id = Column(Integer, primary_key=True)
    secret = Column(String, nullable=False, default="")
    parent_id = Column(Integer, ForeignKey("sec02_fast_target_parents.id"))
    _s_upsert = True
    allow_client_generated_ids = True
    parent = relationship(_FastTargetParent, back_populates="children")

    def _s_check_instance_access(self: Any, action: str = "read") -> bool:
        if self.id in _FASTAPI_DENIED:
            raise UnAuthorizedError(f"child {self.id} denied for {action}")
        return True


def _require_child_row(request: Request) -> None:
    """Row-aware dependency: denies the specific target row 1 on GET.

    Reads the id from the request path (the instance route ends with the
    object id), which is how per-row policies observe the target row. The
    check is scoped to the child collection because the dependency is
    applied to related routes as well.
    """
    path = str(request.url.path).rstrip("/")
    if not path.startswith("/FastTargetChildren"):
        return
    path_id = path.rsplit("/", 1)[-1]
    if path_id == "1":
        raise HTTPException(status_code=403, detail="Row forbidden")


@pytest.fixture()
def fastapi_app() -> Any:
    original_db = safrs.DB
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))

    class DBWrapper:
        def __init__(self) -> None:
            self.session = session
            self.Model = FastBase

    safrs.DB = DBWrapper()
    _FASTAPI_DENIED.clear()
    FastBase.metadata.create_all(engine)
    try:
        session.add_all(
            [
                _FastTargetParent(id=1),
                _FastTargetParent(id=2),
                _FastTargetChild(id=1, secret="s1", parent_id=1),
                _FastTargetChild(id=2, secret="s2", parent_id=1),
                _FastTargetChild(id=3, secret="s3", parent_id=2),
            ]
        )
        session.commit()
        app = FastAPI()
        api = SafrsFastAPI(app, cleanup_session=False)
        api.expose_object(_FastTargetParent)
        api.expose_object(_FastTargetChild, dependencies=[Depends(_require_child_row)])
        yield app
    finally:
        _FASTAPI_DENIED.clear()
        session.remove()
        FastBase.metadata.drop_all(engine)
        safrs.DB = original_db


def test_fastapi_linkage_denies_target_rows_denied_by_dependency(fastapi_app: Any) -> None:
    client = TestClient(fastapi_app)

    add = client.patch(
        "/FastTargetParents/2/children",
        json={"data": [{"type": "FastTargetChild", "id": "1"}]},
        headers=JSONAPI_HEADERS,
    )
    assert add.status_code == 403
    remove = client.request(
        "DELETE",
        "/FastTargetParents/1/children",
        json={"data": [{"type": "FastTargetChild", "id": "1"}]},
        headers=JSONAPI_HEADERS,
    )
    assert remove.status_code == 403
    child = safrs.DB.session.get(_FastTargetChild, 1)
    assert child.parent_id == 1


def test_fastapi_allowed_target_rows_keep_working(fastapi_app: Any) -> None:
    client = TestClient(fastapi_app)
    response = client.patch(
        "/FastTargetParents/2/children",
        json={"data": [{"type": "FastTargetChild", "id": "2"}]},
        headers=JSONAPI_HEADERS,
    )
    assert response.status_code == 200
    assert safrs.DB.session.get(_FastTargetChild, 2).parent_id == 2


def test_fastapi_include_omits_denied_target_rows(fastapi_app: Any) -> None:
    _FASTAPI_DENIED.add(1)
    client = TestClient(fastapi_app)
    response = client.get("/FastTargetParents/1", params={"include": "children"})
    assert response.status_code == 200
    included_ids = {item["id"] for item in response.json().get("included", [])}
    assert included_ids == {"2"}


def test_fastapi_direct_read_denies_denied_rows(fastapi_app: Any) -> None:
    _FASTAPI_DENIED.add(1)
    client = TestClient(fastapi_app)
    assert client.get("/FastTargetChildren/1").status_code == 403
    assert client.get("/FastTargetChildren/2").status_code == 200


def test_fastapi_cascade_delete_denies_when_a_doomed_row_is_denied(fastapi_app: Any) -> None:
    _FASTAPI_DENIED.add(1)
    client = TestClient(fastapi_app)
    response = client.delete("/FastTargetParents/1")
    assert response.status_code == 403
    assert safrs.DB.session.get(_FastTargetParent, 1) is not None
    assert safrs.DB.session.get(_FastTargetChild, 1) is not None
    assert safrs.DB.session.get(_FastTargetChild, 2) is not None


def test_fastapi_nested_write_denies_target_rows(fastapi_app: Any) -> None:
    _FASTAPI_DENIED.add(1)
    client = TestClient(fastapi_app)
    response = client.post(
        "/FastTargetParents",
        json={
            "data": {
                "type": "FastTargetParent",
                "attributes": {},
                "relationships": {
                    "children": {
                        "data": [
                            {"type": "FastTargetChild", "id": "1", "attributes": {"secret": "hijacked"}}
                        ]
                    }
                },
            }
        },
        headers=JSONAPI_HEADERS,
    )
    assert response.status_code == 403
    assert safrs.DB.session.get(_FastTargetChild, 1).secret == "s1"
