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


@pytest.mark.parametrize("target_first", [True, False], ids=["target-first", "parent-first"])
@pytest.mark.parametrize(
    "method_decorators",
    [[_deny_access], {"get": [_deny_access]}],
    ids=["list", "method-mapping"],
)
def test_flask_parent_traversal_applies_target_method_decorators(
    target_first: bool,
    method_decorators: Any,
) -> None:
    db = SQLAlchemy()

    class MethodDecoratorParent(SAFRSBase, db.Model):
        __tablename__ = "security_method_decorator_parents"

        id = db.Column(db.Integer, primary_key=True)
        children = db.relationship("MethodDecoratorChild", back_populates="parent")

    class MethodDecoratorChild(SAFRSBase, db.Model):
        __tablename__ = "security_method_decorator_children"

        id = db.Column(db.Integer, primary_key=True)
        secret = db.Column(db.String)
        parent_id = db.Column(db.Integer, db.ForeignKey("security_method_decorator_parents.id"))
        parent = db.relationship(MethodDecoratorParent, back_populates="children")

    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    db.init_app(app)

    with app.app_context():
        db.create_all()
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False)
        parent = MethodDecoratorParent(id=1)
        parent.children.append(MethodDecoratorChild(id=7, secret="protected"))
        db.session.add(parent)
        db.session.commit()
        if target_first:
            api.expose_object(MethodDecoratorChild, method_decorators=method_decorators)
            api.expose_object(MethodDecoratorParent)
        else:
            api.expose_object(MethodDecoratorParent)
            api.expose_object(MethodDecoratorChild, method_decorators=method_decorators)

    client = app.test_client()
    child_url = f"/{MethodDecoratorChild._s_collection_name}/7/"
    relationship_url = f"/{MethodDecoratorParent._s_collection_name}/1/children"
    include_url = f"/{MethodDecoratorParent._s_collection_name}/1/?include=children"

    assert client.get(child_url).status_code == HTTPStatus.UNAUTHORIZED
    traversal_responses = [client.get(relationship_url), client.get(include_url)]
    assert [response.status_code for response in traversal_responses] == [
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.UNAUTHORIZED,
    ]


def test_flask_parent_traversal_applies_relationship_decorators() -> None:
    db = SQLAlchemy()

    class RelationshipPolicyParent(SAFRSBase, db.Model):
        __tablename__ = "security_relationship_policy_parents"

        id = db.Column(db.Integer, primary_key=True)
        children = db.relationship("RelationshipPolicyChild", back_populates="parent")

    class RelationshipPolicyChild(SAFRSBase, db.Model):
        __tablename__ = "security_relationship_policy_children"

        id = db.Column(db.Integer, primary_key=True)
        parent_id = db.Column(db.Integer, db.ForeignKey("security_relationship_policy_parents.id"))
        parent = db.relationship(RelationshipPolicyParent, back_populates="children")

    RelationshipPolicyParent.children.property.decorators = [_deny_access]

    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    db.init_app(app)

    with app.app_context():
        db.create_all()
        parent = RelationshipPolicyParent(id=1)
        parent.children.append(RelationshipPolicyChild(id=7))
        db.session.add(parent)
        db.session.commit()
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False)
        api.expose_object(RelationshipPolicyParent)
        api.expose_object(RelationshipPolicyChild)

    client = app.test_client()
    parent_url = f"/{RelationshipPolicyParent._s_collection_name}/1/"
    relationship_url = f"/{RelationshipPolicyParent._s_collection_name}/1/children"

    assert client.get(relationship_url).status_code == HTTPStatus.UNAUTHORIZED
    assert client.get(f"{parent_url}?include=children").status_code == HTTPStatus.UNAUTHORIZED
    nested_write = client.post(
        f"/{RelationshipPolicyParent._s_collection_name}/",
        headers=JSONAPI_HEADERS,
        json={
            "data": {
                "type": RelationshipPolicyParent._s_type,
                "attributes": {},
                "relationships": {
                    "children": {
                        "data": [{"type": RelationshipPolicyChild._s_type, "id": "7"}],
                    }
                },
            }
        },
    )
    assert nested_write.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.parametrize("policy_kind", ["model", "method"], ids=["model-decorator", "method-decorator"])
def test_flask_parent_delete_applies_target_authorization(policy_kind: str) -> None:
    db = SQLAlchemy()

    class CascadeParent(SAFRSBase, db.Model):
        __tablename__ = f"security_cascade_parents_{policy_kind}"

        id = db.Column(db.Integer, primary_key=True)
        children = db.relationship(
            "CascadeChild",
            back_populates="parent",
            cascade="all, delete-orphan",
        )

    class CascadeChild(SAFRSBase, db.Model):
        __tablename__ = f"security_cascade_children_{policy_kind}"

        id = db.Column(db.Integer, primary_key=True)
        parent_id = db.Column(
            db.Integer,
            db.ForeignKey(f"security_cascade_parents_{policy_kind}.id"),
        )
        parent = db.relationship(CascadeParent, back_populates="children")

    method_decorators: Any = []
    if policy_kind == "model":
        CascadeChild.decorators = [_deny_access]
    else:
        method_decorators = {"delete": [_deny_access]}

    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    db.init_app(app)

    with app.app_context():
        db.create_all()
        parent = CascadeParent(id=1)
        parent.children.append(CascadeChild(id=7))
        db.session.add(parent)
        db.session.commit()
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False)
        api.expose_object(CascadeParent)
        api.expose_object(CascadeChild, method_decorators=method_decorators)

    client = app.test_client()
    parent_url = f"/{CascadeParent._s_collection_name}/1/"
    child_url = f"/{CascadeChild._s_collection_name}/7/"

    assert client.delete(child_url).status_code == HTTPStatus.UNAUTHORIZED
    assert client.delete(parent_url).status_code == HTTPStatus.UNAUTHORIZED
    with app.app_context():
        assert db.session.get(CascadeParent, 1) is not None
        assert db.session.get(CascadeChild, 7) is not None


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
