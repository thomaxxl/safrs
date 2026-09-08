from __future__ import annotations

from functools import wraps
from http import HTTPStatus
from typing import Any, Callable

import pytest
from flask import Flask, abort, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.ext.hybrid import hybrid_method

from safrs import SAFRSBase, SafrsApi
from safrs.api_methods import search as safrs_search
from safrs.api_methods import startswith as safrs_startswith
from safrs.errors import SystemValidationError, ValidationError
from safrs.fastapi.schemas import SchemaRegistry
from safrs.jsonapi_context import JsonApiContext, reset_jsonapi_context, set_jsonapi_context
from safrs.config import get_config
from safrs.safrs_api import _dedupe_decorators


JSONAPI_HEADERS = {
    "Accept": "application/vnd.api+json",
    "Content-Type": "application/vnd.api+json",
}


def _jsonapi_document(model: type[Any], *, attributes: dict[str, Any], resource_id: str | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {"type": model._s_type, "attributes": attributes}
    if resource_id is not None:
        data["id"] = resource_id
    return {"data": data}


def test_filters_reject_class_hidden_and_non_filterable_fields() -> None:
    db = SQLAlchemy()

    class FilterPolicyAccount(SAFRSBase, db.Model):
        __tablename__ = "security_filter_policy_accounts"

        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String)
        secret = db.Column(db.String)
        internal = db.Column(db.String)
        startswith = safrs_startswith

    FilterPolicyAccount.__table__.c.secret.permissions = "w"
    FilterPolicyAccount.__table__.c.internal.filterable = False

    app = Flask(__name__)
    app.config.update(
        SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True, MAX_BRACKET_FILTERS=1
    )
    db.init_app(app)
    with app.app_context():
        db.create_all()
        db.session.add(FilterPolicyAccount(id=1, name="alice", secret="hunter2", internal="marker"))
        db.session.commit()
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False, app_db=db)
        api.expose_object(FilterPolicyAccount)

    client = app.test_client()
    collection_url = f"/{FilterPolicyAccount._s_collection_name}/"

    hidden = client.get(collection_url, query_string={"filter[secret]": "hunter2"})
    non_filterable = client.get(collection_url, query_string={"filter[internal]": "marker"})
    structured = client.get(
        collection_url,
        query_string={"filter": '{"name":"secret","op":"eq","val":"hunter2"}'},
    )
    malformed_name = client.get(collection_url, query_string={"filter[]": "alice"})
    empty_value = client.get(collection_url, query_string={"filter[name]": ""})
    invalid_id = client.get(collection_url, query_string={"filter[id]": "not-an-integer"})
    too_many = client.get(
        collection_url,
        query_string={"filter[id]": "1", "filter[name]": "alice"},
    )
    valid = client.get(collection_url, query_string={"filter[name]": "alice"})

    assert hidden.status_code == HTTPStatus.BAD_REQUEST
    assert hidden.get_json()["errors"][0]["code"] == str(HTTPStatus.BAD_REQUEST.value)
    assert non_filterable.status_code == HTTPStatus.BAD_REQUEST
    assert non_filterable.get_json()["errors"][0]["code"] == str(HTTPStatus.BAD_REQUEST.value)
    assert structured.status_code == HTTPStatus.BAD_REQUEST
    assert malformed_name.status_code == HTTPStatus.BAD_REQUEST
    assert empty_value.status_code == HTTPStatus.BAD_REQUEST
    assert invalid_id.status_code == HTTPStatus.BAD_REQUEST
    assert too_many.status_code == HTTPStatus.BAD_REQUEST
    assert [item["id"] for item in valid.get_json()["data"]] == ["1"]

    with app.test_request_context("/"):
        with pytest.raises(SystemValidationError):
            FilterPolicyAccount.startswith(secret="hunter2")


def test_filters_cannot_probe_instance_hidden_fields() -> None:
    db = SQLAlchemy()

    class InstanceFilterAccount(SAFRSBase, db.Model):
        __tablename__ = "security_instance_filter_accounts"

        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String)
        secret = db.Column(db.String)
        startswith = safrs_startswith
        search = safrs_search

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
            [
                InstanceFilterAccount(id=1, name="alice", secret="hunter2"),
                InstanceFilterAccount(id=2, name="bob", secret="decoy"),
            ]
        )
        db.session.commit()
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False, app_db=db)
        api.expose_object(InstanceFilterAccount)

    client = app.test_client()
    collection_url = f"/{InstanceFilterAccount._s_collection_name}/"

    direct = client.get(f"{collection_url}1/")
    denied = client.get(collection_url, query_string={"filter[secret]": "hunter2"})
    allowed = client.get(collection_url, query_string={"filter[secret]": "decoy"})
    structured = client.get(
        collection_url,
        query_string={"filter": '{"name":"secret","op":"eq","val":"hunter2"}'},
    )

    assert "secret" not in direct.get_json()["data"]["attributes"]
    assert denied.get_json()["data"] == []
    assert denied.get_json()["meta"]["total"] == 0
    assert structured.get_json()["data"] == []
    assert structured.get_json()["meta"]["total"] == 0
    assert [item["id"] for item in allowed.get_json()["data"]] == ["2"]

    with app.test_request_context("/"):
        prefix_result = InstanceFilterAccount.startswith(secret="hunter")
        search_result = InstanceFilterAccount.search(query="hunter2")
    assert prefix_result.to_dict()["data"] == []
    assert prefix_result.to_dict()["meta"]["total"] == 0
    assert search_result.to_dict()["data"] == []
    assert search_result.to_dict()["meta"]["total"] == 0


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


def test_flask_upsert_uses_explicit_authorization_and_patch_update_path() -> None:
    db = SQLAlchemy()
    authorization_calls: list[int] = []
    patch_calls: list[int] = []

    def authorize_upsert(function: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(function)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            authorization_calls.append(1)
            return function(*args, **kwargs)

        return wrapped

    class UpsertAccount(SAFRSBase, db.Model):
        __tablename__ = "security_upsert_accounts"
        allow_client_generated_ids = True
        http_methods = ["GET", "POST"]

        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String)

        def _s_patch(self: Any, **attributes: Any) -> Any:
            patch_calls.append(self.id)
            return super()._s_patch(**attributes)

    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    db.init_app(app)

    with app.app_context():
        db.create_all()
        db.session.add(UpsertAccount(id=1, name="original"))
        db.session.commit()
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False)
        api.expose_object(
            UpsertAccount,
            method_decorators={"patch": [_deny_access], "upsert": [authorize_upsert]},
        )

    client = app.test_client()
    collection_url = f"/{UpsertAccount._s_collection_name}/"

    update_response = client.post(
        collection_url,
        headers=JSONAPI_HEADERS,
        json=_jsonapi_document(UpsertAccount, resource_id="1", attributes={"name": "updated"}),
    )
    assert update_response.status_code == HTTPStatus.OK
    assert authorization_calls == [1]
    assert patch_calls == [1]

    create_response = client.post(
        collection_url,
        headers=JSONAPI_HEADERS,
        json=_jsonapi_document(UpsertAccount, resource_id="2", attributes={"name": "created"}),
    )
    assert create_response.status_code == HTTPStatus.CREATED
    assert authorization_calls == [1]
    assert patch_calls == [1]

    with app.app_context():
        assert db.session.get(UpsertAccount, 1).name == "updated"
        assert db.session.get(UpsertAccount, 2).name == "created"


def test_flask_upsert_falls_back_to_patch_authorization() -> None:
    db = SQLAlchemy()

    class ProtectedUpsertAccount(SAFRSBase, db.Model):
        __tablename__ = "security_protected_upsert_accounts"
        allow_client_generated_ids = True
        http_methods = ["GET", "POST"]

        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String)

    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    db.init_app(app)

    with app.app_context():
        db.create_all()
        db.session.add(ProtectedUpsertAccount(id=1, name="protected"))
        db.session.commit()
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False)
        api.expose_object(ProtectedUpsertAccount, method_decorators={"patch": [_deny_access]})

    client = app.test_client()
    collection_url = f"/{ProtectedUpsertAccount._s_collection_name}/"
    update_response = client.post(
        collection_url,
        headers=JSONAPI_HEADERS,
        json=_jsonapi_document(
            ProtectedUpsertAccount,
            resource_id="1",
            attributes={"name": "unauthorized"},
        ),
    )

    assert update_response.status_code == HTTPStatus.UNAUTHORIZED
    with app.app_context():
        assert db.session.get(ProtectedUpsertAccount, 1).name == "protected"


def test_flask_nested_upsert_applies_target_patch_authorization() -> None:
    db = SQLAlchemy()

    class NestedUpsertParent(SAFRSBase, db.Model):
        __tablename__ = "security_nested_upsert_parents"

        id = db.Column(db.Integer, primary_key=True)
        children = db.relationship("NestedUpsertChild", back_populates="parent")

    class NestedUpsertChild(SAFRSBase, db.Model):
        __tablename__ = "security_nested_upsert_children"
        allow_client_generated_ids = True

        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String)
        parent_id = db.Column(db.Integer, db.ForeignKey("security_nested_upsert_parents.id"))
        parent = db.relationship(NestedUpsertParent, back_populates="children")

    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    db.init_app(app)

    with app.app_context():
        db.create_all()
        db.session.add(NestedUpsertChild(id=7, name="protected"))
        db.session.commit()
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False)
        api.expose_object(NestedUpsertParent)
        api.expose_object(NestedUpsertChild, method_decorators={"patch": [_deny_access]})

    client = app.test_client()
    response = client.post(
        f"/{NestedUpsertParent._s_collection_name}/",
        headers=JSONAPI_HEADERS,
        json={
            "data": {
                "type": NestedUpsertParent._s_type,
                "attributes": {},
                "relationships": {
                    "children": {
                        "data": [
                            {
                                "type": NestedUpsertChild._s_type,
                                "id": "7",
                                "attributes": {"name": "unauthorized"},
                            }
                        ]
                    }
                },
            }
        },
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    with app.app_context():
        assert db.session.get(NestedUpsertChild, 7).name == "protected"
        assert db.session.execute(db.select(NestedUpsertParent)).scalars().all() == []


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


def test_post_rechecks_caller_dependent_write_permissions_without_cross_request_cache() -> None:
    db = SQLAlchemy()

    class CallerScopedAccount(SAFRSBase, db.Model):
        __tablename__ = "security_caller_scoped_accounts"

        id = db.Column(db.Integer, primary_key=True)
        role = db.Column(db.String)

        @hybrid_method
        def _s_check_perm(self: Any, property_name: str, permission: str="r") -> bool:
            if property_name == "role" and permission == "w":
                return request.headers.get("X-Admin") == "yes"
            return True

    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    db.init_app(app)

    with app.app_context():
        db.create_all()
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False, app_db=db)
        api.expose_object(CallerScopedAccount)

    collection_url = f"/{CallerScopedAccount._s_collection_name}/"
    client = app.test_client()
    admin_headers = {**JSONAPI_HEADERS, "X-Admin": "yes"}
    allowed = client.post(
        collection_url,
        headers=admin_headers,
        json=_jsonapi_document(CallerScopedAccount, attributes={"role": "admin"}),
    )
    denied = client.post(
        collection_url,
        headers=JSONAPI_HEADERS,
        json=_jsonapi_document(CallerScopedAccount, attributes={"role": "attacker"}),
    )

    assert allowed.status_code == HTTPStatus.CREATED
    assert denied.status_code == HTTPStatus.CREATED
    with app.app_context():
        assert [row.role for row in db.session.execute(db.select(CallerScopedAccount)).scalars()] == [
            "admin",
            None,
        ]


def test_post_rechecks_initialized_instance_write_permissions() -> None:
    db = SQLAlchemy()

    class InstanceScopedAccount(SAFRSBase, db.Model):
        __tablename__ = "security_instance_scoped_accounts"

        id = db.Column(db.Integer, primary_key=True)
        role = db.Column(db.String)

        @hybrid_method
        def _s_check_perm(self: Any, property_name: str, permission: str="r") -> bool:
            return not (property_name == "role" and permission == "w")

        @_s_check_perm.expression
        def _s_check_perm(cls: Any, property_name: str, permission: str="r") -> bool:
            return True

    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    db.init_app(app)
    with app.app_context():
        db.create_all()
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False, app_db=db)
        api.expose_object(InstanceScopedAccount)

    response = app.test_client().post(
        f"/{InstanceScopedAccount._s_collection_name}/",
        headers=JSONAPI_HEADERS,
        json=_jsonapi_document(InstanceScopedAccount, attributes={"role": "admin"}),
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    with app.app_context():
        assert db.session.execute(db.select(InstanceScopedAccount)).scalars().all() == []


def test_relationship_routes_cannot_bypass_target_http_method_restrictions() -> None:
    db = SQLAlchemy()

    class ReadOnlyTargetParent(SAFRSBase, db.Model):
        __tablename__ = "security_readonly_target_parents"

        id = db.Column(db.Integer, primary_key=True)
        children = db.relationship("ReadOnlyTargetChild", back_populates="parent")

    class ReadOnlyTargetChild(SAFRSBase, db.Model):
        __tablename__ = "security_readonly_target_children"
        http_methods = ["GET"]

        id = db.Column(db.Integer, primary_key=True)
        parent_id = db.Column(db.Integer, db.ForeignKey("security_readonly_target_parents.id"))
        parent = db.relationship(ReadOnlyTargetParent, back_populates="children")

    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    db.init_app(app)
    with app.app_context():
        db.create_all()
        first = ReadOnlyTargetParent(id=1)
        second = ReadOnlyTargetParent(id=2)
        first.children.append(ReadOnlyTargetChild(id=7))
        db.session.add_all([first, second])
        db.session.commit()
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False, app_db=db)
        api.expose_object(ReadOnlyTargetParent)
        api.expose_object(ReadOnlyTargetChild)

    client = app.test_client()
    child_patch = client.patch(
        f"/{ReadOnlyTargetChild._s_collection_name}/7/",
        headers=JSONAPI_HEADERS,
        json=_jsonapi_document(ReadOnlyTargetChild, resource_id="7", attributes={}),
    )
    relationship_patch = client.patch(
        f"/{ReadOnlyTargetParent._s_collection_name}/2/children",
        headers=JSONAPI_HEADERS,
        json={"data": [{"type": ReadOnlyTargetChild._s_type, "id": "7"}]},
    )

    assert child_patch.status_code == HTTPStatus.METHOD_NOT_ALLOWED
    assert relationship_patch.status_code == HTTPStatus.METHOD_NOT_ALLOWED
    with app.app_context():
        assert db.session.get(ReadOnlyTargetChild, 7).parent_id == 1


def test_nested_post_cannot_create_a_target_with_post_disabled() -> None:
    db = SQLAlchemy()

    class NestedMethodParent(SAFRSBase, db.Model):
        __tablename__ = "security_nested_method_parents"

        id = db.Column(db.Integer, primary_key=True)
        children = db.relationship("NestedMethodChild", back_populates="parent")

    class NestedMethodChild(SAFRSBase, db.Model):
        __tablename__ = "security_nested_method_children"
        http_methods = ["GET"]

        id = db.Column(db.Integer, primary_key=True)
        parent_id = db.Column(db.Integer, db.ForeignKey("security_nested_method_parents.id"))
        parent = db.relationship(NestedMethodParent, back_populates="children")

    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    db.init_app(app)
    with app.app_context():
        db.create_all()
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False, app_db=db)
        api.expose_object(NestedMethodParent)
        api.expose_object(NestedMethodChild)

    response = app.test_client().post(
        f"/{NestedMethodParent._s_collection_name}/",
        headers=JSONAPI_HEADERS,
        json={
            "data": {
                "type": NestedMethodParent._s_type,
                "attributes": {},
                "relationships": {
                    "children": {"data": [{"type": NestedMethodChild._s_type, "id": "7"}]}
                },
            }
        },
    )
    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
    with app.app_context():
        assert db.session.execute(db.select(NestedMethodParent)).scalars().all() == []
        assert db.session.execute(db.select(NestedMethodChild)).scalars().all() == []


def test_nested_post_cannot_update_a_target_with_patch_disabled() -> None:
    db = SQLAlchemy()

    class NestedPatchParent(SAFRSBase, db.Model):
        __tablename__ = "security_nested_patch_parents"

        id = db.Column(db.Integer, primary_key=True)
        children = db.relationship("NestedPatchChild", back_populates="parent")

    class NestedPatchChild(SAFRSBase, db.Model):
        __tablename__ = "security_nested_patch_children"
        http_methods = ["GET", "POST"]
        allow_client_generated_ids = True

        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String)
        parent_id = db.Column(db.Integer, db.ForeignKey("security_nested_patch_parents.id"))
        parent = db.relationship(NestedPatchParent, back_populates="children")

    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    db.init_app(app)
    with app.app_context():
        db.create_all()
        db.session.add(NestedPatchChild(id=7, name="protected"))
        db.session.commit()
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False, app_db=db)
        api.expose_object(NestedPatchParent)
        api.expose_object(NestedPatchChild)

    response = app.test_client().post(
        f"/{NestedPatchParent._s_collection_name}/",
        headers=JSONAPI_HEADERS,
        json={
            "data": {
                "type": NestedPatchParent._s_type,
                "attributes": {},
                "relationships": {
                    "children": {
                        "data": [
                            {
                                "type": NestedPatchChild._s_type,
                                "id": "7",
                                "attributes": {"name": "bypassed"},
                            }
                        ]
                    }
                },
            }
        },
    )
    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
    with app.app_context():
        child = db.session.get(NestedPatchChild, 7)
        assert child.name == "protected"
        assert child.parent_id is None
        assert db.session.execute(db.select(NestedPatchParent)).scalars().all() == []


def test_cascade_delete_cannot_bypass_target_delete_restriction() -> None:
    db = SQLAlchemy()

    class RestrictedCascadeParent(SAFRSBase, db.Model):
        __tablename__ = "security_restricted_cascade_parents"

        id = db.Column(db.Integer, primary_key=True)
        children = db.relationship(
            "RestrictedCascadeChild",
            back_populates="parent",
            cascade="all, delete-orphan",
        )

    class RestrictedCascadeChild(SAFRSBase, db.Model):
        __tablename__ = "security_restricted_cascade_children"
        http_methods = ["GET"]

        id = db.Column(db.Integer, primary_key=True)
        parent_id = db.Column(db.Integer, db.ForeignKey("security_restricted_cascade_parents.id"))
        parent = db.relationship(RestrictedCascadeParent, back_populates="children")

    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    db.init_app(app)
    with app.app_context():
        db.create_all()
        parent = RestrictedCascadeParent(id=1)
        parent.children.append(RestrictedCascadeChild(id=7))
        db.session.add(parent)
        db.session.commit()
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False, app_db=db)
        api.expose_object(RestrictedCascadeParent)
        api.expose_object(RestrictedCascadeChild)

    response = app.test_client().delete(f"/{RestrictedCascadeParent._s_collection_name}/1/")
    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
    with app.app_context():
        assert db.session.get(RestrictedCascadeParent, 1) is not None
        assert db.session.get(RestrictedCascadeChild, 7) is not None


def test_upsert_precheck_race_fails_as_conflict_without_updating(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = SQLAlchemy()

    class RacingUpsertAccount(SAFRSBase, db.Model):
        __tablename__ = "security_racing_upsert_accounts"
        allow_client_generated_ids = True

        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String)

    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    db.init_app(app)
    with app.app_context():
        db.create_all()
        db.session.add(RacingUpsertAccount(id=1, name="protected"))
        db.session.commit()
        original_lookup = RacingUpsertAccount._s_get_upsert_target.__func__
        calls = 0

        def racing_lookup(cls: Any, jsonapi_id: Any=None, **params: Any) -> Any:
            nonlocal calls
            calls += 1
            if calls == 1:
                return None
            return original_lookup(cls, jsonapi_id, **params)

        monkeypatch.setattr(RacingUpsertAccount, "_s_get_upsert_target", classmethod(racing_lookup))
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False, app_db=db)
        api.expose_object(RacingUpsertAccount, method_decorators={"patch": [_deny_access]})

    response = app.test_client().post(
        f"/{RacingUpsertAccount._s_collection_name}/",
        headers=JSONAPI_HEADERS,
        json=_jsonapi_document(RacingUpsertAccount, resource_id="1", attributes={"name": "bypassed"}),
    )
    assert response.status_code == HTTPStatus.CONFLICT
    assert calls == 1
    with app.app_context():
        assert db.session.get(RacingUpsertAccount, 1).name == "protected"


@pytest.mark.parametrize("operation", ["post", "patch"])
def test_write_responses_apply_get_authorization_and_roll_back(operation: str) -> None:
    db = SQLAlchemy()

    class WriteOnlyPrincipalAccount(SAFRSBase, db.Model):
        __tablename__ = f"security_write_response_accounts_{operation}"

        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String)

    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    db.init_app(app)
    with app.app_context():
        db.create_all()
        if operation == "patch":
            db.session.add(WriteOnlyPrincipalAccount(id=1, name="original"))
            db.session.commit()
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False, app_db=db)
        api.expose_object(WriteOnlyPrincipalAccount, method_decorators={"get": [_deny_access]})

    client = app.test_client()
    collection_url = f"/{WriteOnlyPrincipalAccount._s_collection_name}/"
    if operation == "post":
        response = client.post(
            collection_url,
            headers=JSONAPI_HEADERS,
            json=_jsonapi_document(WriteOnlyPrincipalAccount, attributes={"name": "created"}),
        )
    else:
        response = client.patch(
            f"{collection_url}1/",
            headers=JSONAPI_HEADERS,
            json=_jsonapi_document(
                WriteOnlyPrincipalAccount,
                resource_id="1",
                attributes={"name": "updated"},
            ),
        )

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    with app.app_context():
        rows = db.session.execute(db.select(WriteOnlyPrincipalAccount)).scalars().all()
        if operation == "post":
            assert rows == []
        else:
            assert len(rows) == 1
            assert rows[0].name == "original"


def test_head_inherits_get_authorization() -> None:
    db = SQLAlchemy()

    class HeadProtectedAccount(SAFRSBase, db.Model):
        __tablename__ = "security_head_protected_accounts"

        id = db.Column(db.Integer, primary_key=True)

    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    db.init_app(app)
    with app.app_context():
        db.create_all()
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False, app_db=db)
        api.expose_object(HeadProtectedAccount, method_decorators={"get": [_deny_access]})

    response = app.test_client().head(f"/{HeadProtectedAccount._s_collection_name}/")
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_head_applies_model_decorators() -> None:
    db = SQLAlchemy()

    class DecoratorHeadProtectedAccount(SAFRSBase, db.Model):
        __tablename__ = "security_decorator_head_protected_accounts"
        decorators = [_deny_access]

        id = db.Column(db.Integer, primary_key=True)

    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    db.init_app(app)
    with app.app_context():
        db.create_all()
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False, app_db=db)
        api.expose_object(DecoratorHeadProtectedAccount)

    response = app.test_client().head(
        f"/{DecoratorHeadProtectedAccount._s_collection_name}/"
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_bulk_and_include_complexity_limits_are_enforced() -> None:
    db = SQLAlchemy()

    class LimitedParent(SAFRSBase, db.Model):
        __tablename__ = "security_limited_parents"

        id = db.Column(db.Integer, primary_key=True)
        children = db.relationship("LimitedChild", back_populates="parent")

    class LimitedChild(SAFRSBase, db.Model):
        __tablename__ = "security_limited_children"

        id = db.Column(db.Integer, primary_key=True)
        parent_id = db.Column(db.Integer, db.ForeignKey("security_limited_parents.id"))
        parent = db.relationship(LimitedParent, back_populates="children")

    app = Flask(__name__)
    app.config.update(
        SQLALCHEMY_DATABASE_URI="sqlite://",
        TESTING=True,
        MAX_BULK_ITEMS=1,
        MAX_INCLUDE_DEPTH=1,
        MAX_INCLUDE_PATHS=1,
        MAX_INCLUDED_RESOURCES=1,
    )
    db.init_app(app)
    with app.app_context():
        db.create_all()
        parent = LimitedParent(id=1)
        parent.children.extend([LimitedChild(id=1), LimitedChild(id=2)])
        db.session.add(parent)
        db.session.commit()
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False, app_db=db)
        api.expose_object(LimitedParent)
        api.expose_object(LimitedChild)

    client = app.test_client()
    collection_url = f"/{LimitedParent._s_collection_name}/"
    bulk_response = client.post(
        collection_url,
        headers=JSONAPI_HEADERS,
        json={
            "data": [
                {"type": LimitedParent._s_type, "attributes": {}},
                {"type": LimitedParent._s_type, "attributes": {}},
            ]
        },
    )
    deep_include = client.get(f"{collection_url}?include=children.parent")
    wide_include = client.get(f"{collection_url}?include=children,children")
    too_many_included = client.get(f"{collection_url}?include=children")
    nested_bulk = client.post(
        collection_url,
        headers=JSONAPI_HEADERS,
        json={
            "data": {
                "type": LimitedParent._s_type,
                "attributes": {},
                "relationships": {
                    "children": {
                        "data": [
                            {"type": LimitedChild._s_type, "id": "3"},
                            {"type": LimitedChild._s_type, "id": "4"},
                        ]
                    }
                },
            }
        },
    )

    assert bulk_response.status_code == HTTPStatus.BAD_REQUEST
    assert deep_include.status_code == HTTPStatus.BAD_REQUEST
    assert wide_include.status_code == HTTPStatus.BAD_REQUEST
    assert too_many_included.status_code == HTTPStatus.BAD_REQUEST
    assert nested_bulk.status_code == HTTPStatus.BAD_REQUEST


def test_flask_configuration_is_resolved_per_application() -> None:
    first_app = Flask("security-config-first")
    second_app = Flask("security-config-second")
    first_app.config["MAX_PAGE_LIMIT"] = 1
    second_app.config["MAX_PAGE_LIMIT"] = 999

    with first_app.app_context():
        assert get_config("MAX_PAGE_LIMIT") == 1
    with second_app.app_context():
        assert get_config("MAX_PAGE_LIMIT") == 999


def test_swagger_definitions_do_not_leak_between_flask_apps() -> None:
    private_db = SQLAlchemy()

    class PrivateSchemaModel(SAFRSBase, private_db.Model):
        __tablename__ = "security_private_schema_models"

        id = private_db.Column(private_db.Integer, primary_key=True)
        top_secret_value = private_db.Column(private_db.String)

    private_app = Flask("security-private-schema")
    private_app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    private_db.init_app(private_app)
    with private_app.app_context():
        private_db.create_all()
        private_api = SafrsApi(private_app, host="localhost", app_db=private_db)
        private_api.expose_object(PrivateSchemaModel)

    public_db = SQLAlchemy()

    class PublicSchemaModel(SAFRSBase, public_db.Model):
        __tablename__ = "security_public_schema_models"

        id = public_db.Column(public_db.Integer, primary_key=True)
        public_value = public_db.Column(public_db.String)

    public_app = Flask("security-public-schema")
    public_app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    public_db.init_app(public_app)
    with public_app.app_context():
        public_db.create_all()
        public_api = SafrsApi(public_app, host="localhost", app_db=public_db)
        public_api.expose_object(PublicSchemaModel)

    swagger_body = public_app.test_client().get("/swagger.json").get_data(as_text=True)
    assert "PublicSchemaModel" in swagger_body
    assert "public_value" in swagger_body
    assert "PrivateSchemaModel" not in swagger_body
    assert "top_secret_value" not in swagger_body


def test_decorator_deduplication_preserves_configured_order() -> None:
    def first(function: Callable[..., Any]) -> Callable[..., Any]:
        return function

    def second(function: Callable[..., Any]) -> Callable[..., Any]:
        return function

    assert _dedupe_decorators([first, second, first]) == [first, second]


def test_constructor_validation_failure_never_retries_with_database_defaults() -> None:
    from sqlalchemy.orm import validates

    db = SQLAlchemy()

    class ConstructorPolicyAccount(SAFRSBase, db.Model):
        __tablename__ = "security_constructor_policy_accounts"

        id = db.Column(db.Integer, primary_key=True)
        role = db.Column(db.String, default="admin")

        @validates("role")
        def validate_role(self: Any, _key: str, value: str) -> str:
            if value == "attacker":
                raise ValueError("forbidden role")
            return value

    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    db.init_app(app)
    with app.app_context():
        db.create_all()
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False, app_db=db)
        api.expose_object(ConstructorPolicyAccount)

    response = app.test_client().post(
        f"/{ConstructorPolicyAccount._s_collection_name}/",
        headers=JSONAPI_HEADERS,
        json=_jsonapi_document(ConstructorPolicyAccount, attributes={"role": "attacker"}),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    with app.app_context():
        assert db.session.execute(db.select(ConstructorPolicyAccount)).scalars().all() == []


def test_relationship_write_permission_blocks_direct_and_nested_mutation() -> None:
    db = SQLAlchemy()

    class RelationshipPolicyParent(SAFRSBase, db.Model):
        __tablename__ = "security_relationship_policy_parents"
        _s_allow_add_rels = True

        id = db.Column(db.Integer, primary_key=True)
        children = db.relationship("RelationshipPolicyChild", back_populates="parent")

        @hybrid_method
        def _s_check_perm(self: Any, property_name: str, permission: str = "r") -> bool:
            return not (property_name == "children" and permission == "w")

        @_s_check_perm.expression
        def _s_check_perm(cls: Any, property_name: str, permission: str = "r") -> bool:
            return not (property_name == "children" and permission == "w")

    class RelationshipPolicyChild(SAFRSBase, db.Model):
        __tablename__ = "security_relationship_policy_children"

        id = db.Column(db.Integer, primary_key=True)
        parent_id = db.Column(db.Integer, db.ForeignKey("security_relationship_policy_parents.id"))
        parent = db.relationship(RelationshipPolicyParent, back_populates="children")

    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    db.init_app(app)
    with app.app_context():
        db.create_all()
        db.session.add_all([RelationshipPolicyParent(id=1), RelationshipPolicyChild(id=2)])
        db.session.commit()
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False, app_db=db)
        api.expose_object(RelationshipPolicyParent)
        api.expose_object(RelationshipPolicyChild)

    client = app.test_client()
    relationship_url = (
        f"/{RelationshipPolicyParent._s_collection_name}/1/children"
    )
    linkage = {"data": [{"type": RelationshipPolicyChild._s_type, "id": "2"}]}
    direct = client.patch(relationship_url, headers=JSONAPI_HEADERS, json=linkage)
    nested_document = _jsonapi_document(RelationshipPolicyParent, attributes={})
    nested_document["data"]["relationships"] = {
        "children": {"data": [{"type": RelationshipPolicyChild._s_type, "id": "2"}]}
    }
    nested = client.post(
        f"/{RelationshipPolicyParent._s_collection_name}/",
        headers=JSONAPI_HEADERS,
        json=nested_document,
    )

    assert direct.status_code == HTTPStatus.FORBIDDEN
    assert nested.status_code == HTTPStatus.FORBIDDEN
    with app.app_context():
        assert db.session.get(RelationshipPolicyChild, 2).parent_id is None
