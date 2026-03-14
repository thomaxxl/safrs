from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from safrs import jsonapi_attr
from safrs.fastapi.schemas.examples import create_document_example, patch_document_example
from safrs.fastapi.schemas.registry import SchemaRegistry


class _Column:
    def __init__(self, python_type: Any) -> None:
        self.type = SimpleNamespace(python_type=python_type)


class _JsonapiAttrDocModel:
    _s_type = "FastJsonapiAttrThing"
    _s_collection_name = "FastJsonapiAttrThings"
    allow_client_generated_ids = False

    @jsonapi_attr
    def readonly_value(self) -> str:
        """
        description: Read-only computed value
        default: summary-default
        swagger_format: string
        """
        return "summary:alpha"

    @jsonapi_attr
    def password(self) -> str:
        """
        description: Writable secret facade
        default: example-secret
        swagger_format: password
        """
        return "********"

    @password.setter
    def password(self, value: str) -> None:
        self._password = value

    @staticmethod
    def _s_sample_dict() -> dict[str, str]:
        return {
            "name": "alpha",
            "readonly_value": "summary:alpha",
            "password": "example-secret",
        }

    class id_type:
        primary_keys = ["id"]


_JsonapiAttrDocModel._s_jsonapi_attrs = {
    "name": _Column(str),
    "readonly_value": _JsonapiAttrDocModel.readonly_value,
    "password": _JsonapiAttrDocModel.password,
}


class _SwaggerTypedJsonapiAttrModel:
    _s_type = "SwaggerTypedThing"
    _s_collection_name = "SwaggerTypedThings"
    _s_jsonapi_attrs: dict[str, Any]

    @jsonapi_attr
    def count(self):
        """
        description: Count without a Python return annotation
        default: 3
        swagger_type: integer
        """
        return 3

    @count.setter
    def count(self, value: int) -> None:
        self._count = value


_SwaggerTypedJsonapiAttrModel._s_jsonapi_attrs = {
    "count": _SwaggerTypedJsonapiAttrModel.count,
}


def test_request_attributes_skip_readonly_jsonapi_attrs_and_keep_metadata() -> None:
    registry = SchemaRegistry(document_relationships=False)

    response_schema = registry.attributes(_JsonapiAttrDocModel).model_json_schema()
    request_schema = registry.request_attributes(_JsonapiAttrDocModel).model_json_schema()
    create_schema = registry.document_create(_JsonapiAttrDocModel).model_json_schema()

    response_props = response_schema["properties"]
    request_props = request_schema["properties"]

    assert "readonly_value" in response_props
    assert response_props["readonly_value"]["description"] == "Read-only computed value"

    assert "readonly_value" not in request_props
    assert request_props["password"]["default"] == "example-secret"
    assert request_props["password"]["description"] == "Writable secret facade"
    assert request_props["password"]["format"] == "password"
    assert request_schema["examples"][0] == {"name": "alpha", "password": "example-secret"}

    create_request = create_schema["$defs"]["FastJsonapiAttrThingCreateResource"]["properties"]["attributes"]["anyOf"][0]
    assert create_request["$ref"].endswith("/FastJsonapiAttrThingRequestAttributes")


def test_request_document_examples_skip_readonly_jsonapi_attrs() -> None:
    create_example = create_document_example(_JsonapiAttrDocModel)
    patch_example = patch_document_example(_JsonapiAttrDocModel)

    assert create_example["data"]["attributes"] == {"name": "alpha", "password": "example-secret"}
    assert patch_example["data"]["attributes"] == {"name": "alpha", "password": "example-secret"}


def test_swagger_type_metadata_falls_back_for_unannotated_jsonapi_attrs() -> None:
    registry = SchemaRegistry(document_relationships=False)

    response_schema = registry.attributes(_SwaggerTypedJsonapiAttrModel).model_json_schema()
    request_schema = registry.request_attributes(_SwaggerTypedJsonapiAttrModel).model_json_schema()

    response_any_of = response_schema["properties"]["count"]["anyOf"]
    request_any_of = request_schema["properties"]["count"]["anyOf"]
    response_types = {entry["type"] for entry in response_any_of if "type" in entry}
    request_types = {entry["type"] for entry in request_any_of if "type" in entry}

    assert response_types == {"integer", "null"}
    assert request_types == {"integer", "null"}
