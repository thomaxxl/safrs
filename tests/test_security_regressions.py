from __future__ import annotations

from functools import wraps
from http import HTTPStatus
from typing import Any, Callable

import pytest
from flask import Flask, abort
from flask_sqlalchemy import SQLAlchemy

from safrs import SAFRSBase, SafrsApi
from safrs.errors import ValidationError
from safrs.fastapi.schemas import SchemaRegistry
from safrs.jsonapi_context import JsonApiContext, reset_jsonapi_context, set_jsonapi_context


JSONAPI_HEADERS = {
    "Accept": "application/vnd.api+json",
    "Content-Type": "application/vnd.api+json",
}


def _jsonapi_document(model: type[Any], *, attributes: dict[str, Any], resource_id: str | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {"type": model._s_type, "attributes": attributes}
    if resource_id is not None:
        data["id"] = resource_id
    return {"data": data}


def test_post_and_patch_enforce_column_write_permissions() -> None:
    db = SQLAlchemy()

    class PermissionAccount(SAFRSBase, db.Model):
        __tablename__ = "security_permission_accounts"

        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String)
        role = db.Column(db.String)
        secret = db.Column(db.String)

    PermissionAccount.__table__.c.role.permissions = "r"
    PermissionAccount.__table__.c.secret.permissions = "w"

    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    db.init_app(app)

    with app.app_context():
        db.create_all()
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False)
        api.expose_object(PermissionAccount)

        request_fields = SchemaRegistry().request_attributes(PermissionAccount).model_fields
        assert "name" in request_fields
        assert "secret" not in request_fields
        assert "role" not in request_fields

    client = app.test_client()
    collection_url = f"/{PermissionAccount._s_collection_name}/"
    create_response = client.post(
        collection_url,
        headers=JSONAPI_HEADERS,
        json=_jsonapi_document(
            PermissionAccount,
            attributes={"name": "alice", "role": "admin", "secret": "initial"},
        ),
    )

    assert create_response.status_code == HTTPStatus.CREATED
    create_data = create_response.get_json()["data"]
    resource_id = create_data["id"]
    assert create_data["attributes"]["role"] is None
    assert "secret" not in create_data["attributes"]

    patch_response = client.patch(
        f"{collection_url}{resource_id}/",
        headers=JSONAPI_HEADERS,
        json=_jsonapi_document(
            PermissionAccount,
            resource_id=resource_id,
            attributes={"role": "owner", "secret": "updated"},
        ),
    )

    assert patch_response.status_code == HTTPStatus.OK
    with app.app_context():
        account = db.session.get(PermissionAccount, int(resource_id))
        assert account.role is None
        assert account.secret is None


def test_request_parser_rejects_a_read_only_column_directly() -> None:
    db = SQLAlchemy()

    class ReadOnlyColumn(SAFRSBase, db.Model):
        __tablename__ = "security_readonly_columns"

        id = db.Column(db.Integer, primary_key=True)
        role = db.Column(db.String)

    ReadOnlyColumn.__table__.c.role.permissions = "r"
    token = set_jsonapi_context(JsonApiContext(query_params={}))
    try:
        with pytest.raises(ValidationError) as exc_info:
            ReadOnlyColumn._s_parse_attr_value_for_request("role", "admin")
        assert "read-only" in exc_info.value.message
    finally:
        reset_jsonapi_context(token)


def _deny_access(function: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(function)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        abort(HTTPStatus.UNAUTHORIZED)

    return wrapped


def test_flask_relationship_routes_and_parent_traversal_apply_target_decorators() -> None:
    db = SQLAlchemy()

    class AuthorizationParent(SAFRSBase, db.Model):
        __tablename__ = "security_authorization_parents"

        id = db.Column(db.Integer, primary_key=True)
        children = db.relationship("AuthorizationChild", back_populates="parent")

    class AuthorizationChild(SAFRSBase, db.Model):
        __tablename__ = "security_authorization_children"
        decorators = [_deny_access]

        id = db.Column(db.Integer, primary_key=True)
        secret = db.Column(db.String)
        parent_id = db.Column(db.Integer, db.ForeignKey("security_authorization_parents.id"))
        parent = db.relationship(AuthorizationParent, back_populates="children")

    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    db.init_app(app)

    with app.app_context():
        db.create_all()
        parent = AuthorizationParent(id=1)
        parent.children.append(AuthorizationChild(id=7, secret="protected"))
        db.session.add(parent)
        db.session.commit()
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False)
        api.expose_object(AuthorizationParent)
        api.expose_object(AuthorizationChild)

    client = app.test_client()
    assert client.get(f"/{AuthorizationChild._s_collection_name}/7/").status_code == HTTPStatus.UNAUTHORIZED
    assert (
        client.get(f"/{AuthorizationParent._s_collection_name}/1/children").status_code
        == HTTPStatus.UNAUTHORIZED
    )
    assert client.get(f"/{AuthorizationParent._s_collection_name}/1/?include=children").status_code == HTTPStatus.UNAUTHORIZED

    nested_write = client.post(
        f"/{AuthorizationParent._s_collection_name}/",
        headers=JSONAPI_HEADERS,
        json={
            "data": {
                "type": AuthorizationParent._s_type,
                "attributes": {},
                "relationships": {
                    "children": {
                        "data": [
                            {
                                "type": AuthorizationChild._s_type,
                                "id": "7",
                                "attributes": {"secret": "overwritten"},
                            }
                        ]
                    }
                },
            }
        },
    )
    assert nested_write.status_code == HTTPStatus.UNAUTHORIZED
    with app.app_context():
        assert db.session.get(AuthorizationChild, 7).secret == "protected"


def test_relationship_creation_accepts_nested_resources_of_the_expected_type() -> None:
    db = SQLAlchemy()

    class LinkParent(SAFRSBase, db.Model):
        __tablename__ = "security_link_parents"

        id = db.Column(db.Integer, primary_key=True)
        children = db.relationship("LinkChild", back_populates="parent")

    class LinkChild(SAFRSBase, db.Model):
        __tablename__ = "security_link_children"

        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String)
        parent_id = db.Column(db.Integer, db.ForeignKey("security_link_parents.id"))
        parent = db.relationship(LinkParent, back_populates="children")

    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    db.init_app(app)

    with app.app_context():
        db.create_all()
        db.session.add(LinkChild(id=7, name="original"))
        db.session.commit()
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False)
        api.expose_object(LinkParent)
        api.expose_object(LinkChild)

    collection_url = f"/{LinkParent._s_collection_name}/"
    client = app.test_client()
    create_response = client.post(
        collection_url,
        headers=JSONAPI_HEADERS,
        json={
            "data": {
                "type": LinkParent._s_type,
                "attributes": {},
                "relationships": {
                    "children": {
                        "data": [
                            {
                                "type": LinkChild._s_type,
                                "id": None,
                                "attributes": {"name": "created"},
                            }
                        ]
                    }
                },
            }
        },
    )
    assert create_response.status_code == HTTPStatus.CREATED
    with app.app_context():
        child = db.session.execute(db.select(LinkChild).filter_by(name="created")).scalar_one()
        assert child.parent_id is not None

    wrong_type = client.post(
        collection_url,
        headers=JSONAPI_HEADERS,
        json={
            "data": {
                "type": LinkParent._s_type,
                "attributes": {},
                "relationships": {
                    "children": {
                        "data": [
                            {
                                "type": LinkParent._s_type,
                                "id": None,
                                "attributes": {"name": "wrong-type"},
                            }
                        ]
                    }
                },
            }
        },
    )
    assert wrong_type.status_code == HTTPStatus.BAD_REQUEST
