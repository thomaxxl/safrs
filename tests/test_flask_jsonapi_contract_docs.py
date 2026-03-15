from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from flask import Flask

from safrs import jsonapi_attr
from safrs.jsonapi import Resource, SAFRSRestAPI, SAFRSRestRelationshipAPI, _build_location_header
from safrs.swagger_doc import _attributes_schema_for_model


class _FakeInstance:
    _s_object_id = "CustomerId"

    def __init__(self, jsonapi_id: str) -> None:
        self.jsonapi_id = jsonapi_id


def test_build_location_header_percent_encodes_control_chars() -> None:
    app = Flask(__name__)

    @app.route("/api/Customer/<CustomerId>", endpoint="customer_detail")
    def _customer_detail(**_kwargs: Any) -> str:
        return "ok"

    with app.test_request_context("/"):
        location = _build_location_header("customer_detail", _FakeInstance("\nX"))

    assert "\n" not in location
    assert "\r" not in location
    assert "%0A" in location
    assert location.endswith("%0AX")


def test_collection_delete_docstring_documents_conflict_status() -> None:
    doc = SAFRSRestAPI.delete.__doc__ or ""
    assert "409" in doc
    assert "description: Conflict" in doc


def test_relationship_delete_docstring_documents_conflict_status() -> None:
    doc = SAFRSRestRelationshipAPI.delete.__doc__ or ""
    assert "409" in doc
    assert "description: Conflict" in doc


def test_swagger_include_description_lists_relationship_examples() -> None:
    class _SwaggerIncludeResource(Resource):
        SAFRSObject = SimpleNamespace(
            _s_relationships={"Customer": object(), "Employee": object()},
            _s_class_name="Order",
        )

    include_param = _SwaggerIncludeResource.get_swagger_include()
    assert include_param["description"] == "Order relationships to include (csv, ex.: Customer,Employee)"


def test_flask_request_schema_marks_write_only_jsonapi_attrs() -> None:
    class _JsonapiAttrSwaggerModel:
        @jsonapi_attr(write_only=True, description="Secret", swagger_format="password")
        def password(self) -> str:
            return "********"

        @password.setter
        def password(self, value: str) -> None:
            self._password = value

        @jsonapi_attr(read_only=True, description="Computed summary")
        def summary(self) -> str:
            return "summary"

        @summary.setter
        def summary(self, value: str) -> None:
            self._summary = value

    _JsonapiAttrSwaggerModel._s_jsonapi_attrs = {
        "password": _JsonapiAttrSwaggerModel.password,
        "summary": _JsonapiAttrSwaggerModel.summary,
    }

    schema = _attributes_schema_for_model(_JsonapiAttrSwaggerModel, for_patch=False)

    assert "summary" not in schema["properties"]
    assert schema["properties"]["password"]["writeOnly"] is True
    assert schema["properties"]["password"]["format"] == "password"


def test_swagger_fields_exclude_write_only_jsonapi_attrs() -> None:
    class _JsonapiAttrFieldModel:
        @jsonapi_attr(write_only=True)
        def password(self) -> str:
            return "********"

        @password.setter
        def password(self, value: str) -> None:
            self._password = value

    _JsonapiAttrFieldModel._s_jsonapi_attrs = {
        "name": object(),
        "password": _JsonapiAttrFieldModel.password,
    }

    class _SwaggerFieldResource(Resource):
        SAFRSObject = SimpleNamespace(
            _s_jsonapi_attrs=_JsonapiAttrFieldModel._s_jsonapi_attrs,
            _s_class_name="User",
        )

    fields_param = _SwaggerFieldResource.get_swagger_fields()
    assert fields_param["default"] == "name"
