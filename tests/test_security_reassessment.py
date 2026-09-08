"""Regression coverage for the 2026-09 security reassessment."""

from __future__ import annotations

import pickle
import logging
from http import HTTPStatus
from typing import Any

import pytest
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, select
from sqlalchemy.ext.hybrid import hybrid_method

from safrs import SAFRSBase, SafrsApi, jsonapi_filter_fields, jsonapi_rpc
from safrs.api_doc import parse_object_doc
from safrs.base import run_instance_access_check
from safrs.errors import GenericError, log_integrity_error_details
from safrs.safrs_types import JSONType
from safrs.swagger_doc import apply_fstring


JSONAPI_HEADERS = {
    "Accept": "application/vnd.api+json",
    "Content-Type": "application/vnd.api+json",
}


def _document(model: type[Any], resource_id: str, **attributes: Any) -> dict[str, Any]:
    return {
        "data": {
            "type": model._s_type,
            "id": resource_id,
            "attributes": attributes,
        }
    }


def test_flask_response_authorizer_covers_collection_bulk_and_rpc_rollback() -> None:
    db = SQLAlchemy()

    class ProtectedResult(SAFRSBase, db.Model):
        __tablename__ = "security_reassessment_results"
        allow_client_generated_ids = True

        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String)

        @classmethod
        @jsonapi_rpc(http_methods=["POST"])
        def mutate_and_return(cls: Any) -> Any:
            row = cls.get_instance(1)
            row.name = "changed"
            return row

    def authorize(_model: Any, instance: Any, _request: Any) -> bool:
        return instance.name != "secret" and instance.id != 1

    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    db.init_app(app)
    with app.app_context():
        db.create_all()
        db.session.add_all(
            [ProtectedResult(id=1, name="original"), ProtectedResult(id=2, name="public")]
        )
        db.session.commit()
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False, app_db=db)
        api.expose_object(ProtectedResult, response_authorizer=authorize)

    client = app.test_client()
    collection = f"/{ProtectedResult._s_collection_name}/"
    assert client.get(collection, query_string={"page[offset]": 1, "page[limit]": 1}).status_code == 403

    bulk = client.post(
        collection,
        headers=JSONAPI_HEADERS,
        json={
            "data": [
                _document(ProtectedResult, "3", name="public")["data"],
                _document(ProtectedResult, "4", name="secret")["data"],
            ]
        },
    )
    assert bulk.status_code == 403

    rpc = client.post(
        f"/{ProtectedResult._s_collection_name}/mutate_and_return",
        headers=JSONAPI_HEADERS,
        json={"meta": {"args": {}}},
    )
    assert rpc.status_code == 403
    with app.app_context():
        assert db.session.get(ProtectedResult, 1).name == "original"
        assert db.session.get(ProtectedResult, 3) is None
        assert db.session.get(ProtectedResult, 4) is None


def test_query_scope_runs_before_count_sort_and_pagination() -> None:
    db = SQLAlchemy()

    class ScopedRow(SAFRSBase, db.Model):
        __tablename__ = "security_reassessment_scoped_rows"

        id = db.Column(db.Integer, primary_key=True)
        label = db.Column(db.String)

        @classmethod
        def _s_query_scope(cls: Any, query: Any) -> Any:
            return query.filter(cls.id > 1)

    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    db.init_app(app)
    with app.app_context():
        db.create_all()
        db.session.add_all([ScopedRow(id=1, label="hidden"), ScopedRow(id=2, label="public")])
        db.session.commit()
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False, app_db=db)
        api.expose_object(ScopedRow)

    payload = app.test_client().get(f"/{ScopedRow._s_collection_name}/").get_json()
    assert payload["meta"]["total"] == 1
    assert [item["id"] for item in payload["data"]] == ["2"]


def test_sort_rejects_class_and_row_protected_fields() -> None:
    db = SQLAlchemy()

    class SortPolicyRow(SAFRSBase, db.Model):
        __tablename__ = "security_reassessment_sort_rows"

        id = db.Column(db.Integer, primary_key=True)
        public = db.Column(db.String)
        secret = db.Column(db.String)

        @hybrid_method
        def _s_check_perm(self: Any, property_name: str, permission: str = "r") -> bool:
            return not (property_name == "secret" and permission == "r" and self.id == 1)

        @_s_check_perm.expression
        def _s_check_perm(cls: Any, property_name: str, permission: str = "r") -> bool:
            return True

    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    db.init_app(app)
    with app.app_context():
        db.create_all()
        db.session.add_all(
            [SortPolicyRow(id=1, public="a", secret="z"), SortPolicyRow(id=2, public="b", secret="a")]
        )
        db.session.commit()
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False, app_db=db)
        api.expose_object(SortPolicyRow)

    client = app.test_client()
    collection = f"/{SortPolicyRow._s_collection_name}/"
    assert client.get(collection, query_string={"sort": "secret"}).status_code == 400
    assert client.get(collection, query_string={"sort": "-secret"}).status_code == 400


def test_custom_filters_require_and_enforce_declared_read_fields() -> None:
    db = SQLAlchemy()

    class CustomFilterRow(SAFRSBase, db.Model):
        __tablename__ = "security_reassessment_custom_filter_rows"

        id = db.Column(db.Integer, primary_key=True)
        secret = db.Column(db.String)

        @classmethod
        @jsonapi_filter_fields("secret")
        def filter(cls: Any, _raw: str) -> Any:
            return cls._s_query.filter(cls.secret == "hidden")

    CustomFilterRow.__table__.c.secret.permissions = "w"
    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    db.init_app(app)
    with app.app_context():
        db.create_all()
        db.session.add(CustomFilterRow(id=1, secret="hidden"))
        db.session.commit()
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False, app_db=db)
        api.expose_object(CustomFilterRow)

    response = app.test_client().get(
        f"/{CustomFilterRow._s_collection_name}/", query_string={"filter": "anything"}
    )
    assert response.status_code == 400


def test_filter_and_json_complexity_limits_fail_before_execution() -> None:
    db = SQLAlchemy()

    class LimitedRow(SAFRSBase, db.Model):
        __tablename__ = "security_reassessment_limited_rows"

        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String)

    app = Flask(__name__)
    app.config.update(
        SQLALCHEMY_DATABASE_URI="sqlite://",
        TESTING=True,
        MAX_FILTER_DEPTH=2,
        MAX_JSON_DEPTH=4,
        MAX_REQUEST_BODY_BYTES=256,
    )
    db.init_app(app)
    with app.app_context():
        db.create_all()
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False, app_db=db)
        api.expose_object(LimitedRow)

    client = app.test_client()
    collection = f"/{LimitedRow._s_collection_name}/"
    deep_filter = '{"not":{"not":{"name":"name","op":"eq","val":"x"}}}'
    assert client.get(collection, query_string={"filter": deep_filter}).status_code == 400
    deep_body = _document(LimitedRow, "1", name="x")
    deep_body["data"]["attributes"]["nested"] = {"a": {"b": {"c": "d"}}}
    assert client.post(collection, headers=JSONAPI_HEADERS, json=deep_body).status_code == 400
    oversized = _document(LimitedRow, "2", name="x" * 400)
    assert client.post(collection, headers=JSONAPI_HEADERS, json=oversized).status_code == 413


def test_json_type_persists_utf8_json_and_never_unpickles_database_bytes() -> None:
    engine = create_engine("sqlite://")
    metadata = MetaData()
    records = Table(
        "security_json_records",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("payload", JSONType()),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(records.insert().values(id=1, payload={"safe": True}))
        raw = connection.exec_driver_sql(
            "select payload from security_json_records where id = 1"
        ).scalar_one()
        assert raw.startswith(b"{")
        assert connection.execute(select(records.c.payload).where(records.c.id == 1)).scalar_one() == {
            "safe": True
        }

        legacy_pickle = pickle.dumps({"legacy": True})
        connection.exec_driver_sql(
            "insert into security_json_records (id, payload) values (?, ?)",
            (2, legacy_pickle),
        )
        with pytest.raises((UnicodeDecodeError, ValueError)):
            connection.execute(select(records.c.payload).where(records.c.id == 2)).scalar_one()


def test_request_local_database_binding_survives_another_api_initialization() -> None:
    first_db = SQLAlchemy()
    second_db = SQLAlchemy()

    class FirstRow(SAFRSBase, first_db.Model):
        __tablename__ = "security_reassessment_first_rows"
        id = first_db.Column(first_db.Integer, primary_key=True)

    class SecondRow(SAFRSBase, second_db.Model):
        __tablename__ = "security_reassessment_second_rows"
        id = second_db.Column(second_db.Integer, primary_key=True)

    first = Flask("security-first")
    first.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    first_db.init_app(first)
    original_prefix = FirstRow.url_prefix
    with first.app_context():
        first_db.create_all()
        first_db.session.add(FirstRow(id=1))
        first_db.session.commit()
        first_api = SafrsApi(first, host="first", prefix="/one", swaggerui_blueprint=False, app_db=first_db)
        first_api.expose_object(FirstRow)
        assert FirstRow.url_prefix == original_prefix
        assert "_safrs_api" not in FirstRow.__dict__

    second = Flask("security-second")
    second.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    second_db.init_app(second)
    with second.app_context():
        second_db.create_all()
        second_db.session.add(SecondRow(id=2))
        second_db.session.commit()
        second_api = SafrsApi(second, host="second", prefix="/two", swaggerui_blueprint=False, app_db=second_db)
        second_api.expose_object(SecondRow)

    first_payload = first.test_client().get(f"/one/{FirstRow._s_collection_name}/").get_json()
    second_payload = second.test_client().get(f"/two/{SecondRow._s_collection_name}/").get_json()
    assert [item["id"] for item in first_payload["data"]] == ["1"]
    assert [item["id"] for item in second_payload["data"]] == ["2"]

    with first_api.runtime_context():
        assert FirstRow._s_query.count() == 1
    with second_api.runtime_context():
        assert SecondRow._s_query.count() == 1


def test_related_route_policy_is_route_aware_and_runs_once() -> None:
    db = SQLAlchemy()
    calls: list[str] = []

    class RouteParent(SAFRSBase, db.Model):
        __tablename__ = "security_reassessment_route_parents"
        id = db.Column(db.Integer, primary_key=True)
        children = db.relationship("RouteChild", back_populates="parent")

    class RouteChild(SAFRSBase, db.Model):
        __tablename__ = "security_reassessment_route_children"
        id = db.Column(db.Integer, primary_key=True)
        parent_id = db.Column(db.Integer, db.ForeignKey("security_reassessment_route_parents.id"))
        parent = db.relationship(RouteParent, back_populates="children")

    def audit(function: Any) -> Any:
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            calls.append("child-read")
            return function(*args, **kwargs)

        return wrapped

    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    db.init_app(app)
    with app.app_context():
        db.create_all()
        db.session.add_all(
            [RouteParent(id=1), RouteChild(id=1, parent_id=1), RouteChild(id=2, parent_id=1)]
        )
        db.session.commit()
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False, app_db=db)
        api.expose_object(RouteParent)
        api.expose_object(RouteChild, method_decorators={"get": [audit]})

    client = app.test_client()
    assert client.get(f"/{RouteParent._s_collection_name}/1/").status_code == 200
    assert calls == []
    assert client.get(
        f"/{RouteParent._s_collection_name}/1/", query_string={"include": "children"}
    ).status_code == 200
    assert calls == ["child-read"]


def test_authorization_materialization_has_a_fail_closed_bound() -> None:
    db = SQLAlchemy()

    class ScanRow(SAFRSBase, db.Model):
        __tablename__ = "security_reassessment_scan_rows"
        id = db.Column(db.Integer, primary_key=True)

        def _s_check_instance_access(self: Any, action: str = "read") -> bool:
            return True

    app = Flask(__name__)
    app.config.update(
        SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True, MAX_AUTHORIZATION_SCAN=1
    )
    db.init_app(app)
    with app.app_context():
        db.create_all()
        db.session.add_all([ScanRow(id=1), ScanRow(id=2)])
        db.session.commit()
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False, app_db=db)
        api.expose_object(ScanRow)

    response = app.test_client().get(f"/{ScanRow._s_collection_name}/")
    assert response.status_code == 400
    assert "_s_query_scope" in response.get_data(as_text=True)


def test_debug_logs_and_errors_do_not_echo_secrets(caplog: pytest.LogCaptureFixture) -> None:
    secret = "never-log-this-token"
    app = Flask("security-log-redaction")

    class FakeIntegrityError:
        orig = RuntimeError(secret)
        statement = "insert secret"
        params = {"token": secret}

    class SecretPolicy:
        jsonapi_id = "1"

        def _s_check_instance_access(self, _action: str) -> bool:
            raise RuntimeError(secret)

    def malformed_documentation() -> None:
        pass

    malformed_documentation.__doc__ = f"token: [{secret}"

    caplog.set_level(logging.DEBUG, logger="safrs.safrs_init")
    with app.test_request_context(f"/items/1?token={secret}"):
        log_integrity_error_details(FakeIntegrityError())
        error = GenericError(secret)
        assert run_instance_access_check(SecretPolicy, SecretPolicy(), quiet=True) is False
        parse_object_doc(malformed_documentation)
        apply_fstring(f"{secret}: {{missing}}", {})

    assert secret not in caplog.text
    assert secret not in error.message
