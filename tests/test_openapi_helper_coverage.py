from types import SimpleNamespace

from safrs.fastapi.openapi import diff, normalize
from safrs.fastapi.relationships import (
    iter_exposed_relationship_properties,
    relationship_is_exposed,
    relationship_property,
    resolve_relationships,
)


def _operation(*, responses=None, parameters=None, request_body=None):
    return {
        "tag": "",
        "summary": "",
        "description": "",
        "parameters": parameters or [],
        "request_body": request_body or {},
        "responses": responses or {},
    }


def test_diff_reports_every_supported_mismatch():
    reference = {
        "operations": {
            ("/items", "get"): _operation(
                responses={
                    "200": {"application/vnd.api+json": "object"},
                    "204": {},
                    "404": {},
                },
                parameters=[{"in_": "query", "name": "filter", "required": False, "type": "string"}],
                request_body={"application/vnd.api+json": "object"},
            ),
            ("/missing", "post"): _operation(),
        },
        "tags": {"Items": "Item operations"},
        "schemas": {},
    }
    candidate = {
        "operations": {
            ("/items", "get"): _operation(responses={"200": {"application/json": "object"}}),
            ("/extra", "get"): _operation(),
        },
        "tags": {},
        "schemas": {},
    }

    report = diff.diff_internal_specs(reference, candidate)

    assert report["missing_operations"] == [["/missing", "post"]]
    assert report["extra_operations"] == [["/extra", "get"]]
    assert report["status_code_mismatches"][0]["missing_status_codes"] == ["204", "404"]
    assert report["missing_parameters"][0]["missing_parameters"] == [["query", "filter"]]
    assert report["missing_request_body"][0]["missing_media_types"] == ["application/vnd.api+json"]
    assert report["missing_response_media_types"][0]["missing_media_types"] == [
        "application/vnd.api+json"
    ]
    assert report["missing_tags"] == ["Items"]

    rendered = diff.format_report(report, top_n=2)
    assert "Spec Diff Summary" in rendered
    assert "[missing_operations]" in rendered
    assert diff._count("not a list") == 0
    assert "- none" in diff.format_report({})


def test_swagger_normalization_handles_malformed_and_defaulted_parts():
    spec = {
        "swagger": "2.0",
        "basePath": "/api",
        "paths": {
            "/ignored": "not a path item",
            "/items/{item_id}/": {
                "parameters": [None, {"in": "path", "name": "item_id", "required": True}],
                "consumes": [],
                "produces": [],
                "trace": {},
                "post": "not an operation",
                "get": {
                    "summary": "Get item",
                    "parameters": [
                        {"in": "path", "name": "duplicate"},
                        {"in": "query", "name": "filter", "schema": {"$ref": "#/definitions/Filter"}},
                        {"in": "body", "name": "data", "schema": {"type": "array", "items": {"type": "integer"}}},
                        {"in": "header", "name": "ignored"},
                    ],
                    "responses": {
                        "200": {"schema": None},
                        "201": {"schema": {"properties": {"second": {}, "first": {}}}},
                        "broken": "not a response",
                    },
                    "tags": ["Items"],
                },
            },
        },
        "tags": [None, {"name": "Items", "description": "Item operations"}],
        "definitions": {"Item": {"type": "object"}},
    }

    internal = normalize.load_any_spec_as_internal(spec)
    operation = internal["operations"][("/api/items/{}", "get")]

    assert operation["parameters"] == [
        {"name": "{}", "in_": "path", "required": True, "type": "string"},
        {
            "name": "filter",
            "in_": "query",
            "required": False,
            "type": "#/definitions/Filter",
        },
    ]
    assert operation["request_body"] == {
        normalize.JSONAPI_MEDIA_TYPE: "array[integer]"
    }
    assert operation["responses"]["200"] == {}
    assert operation["responses"]["201"] == {
        normalize.JSONAPI_MEDIA_TYPE: "object[first,second]"
    }
    assert internal["tags"] == {"Items": "Item operations"}
    assert normalize._join_base_path("", "/items") == "/items"
    assert normalize._join_base_path("/api", "/api/items") == "/api/items"
    assert normalize._schema_signature("not a schema") == "none"
    assert normalize._normalize_parameter({"in": "query", "name": "plain"})["type"] == "string"


def test_openapi3_normalization_ignores_invalid_nested_values():
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/ignored": [],
            "/widgets/{widget_id}/": {
                "parameters": [None],
                "trace": {},
                "post": "not an operation",
                "get": {
                    "parameters": [{"in": "query", "name": "page", "schema": {"type": "integer"}}],
                    "requestBody": {
                        "content": {
                            "application/json": {"schema": {"type": "string"}},
                            "broken": "not media info",
                        }
                    },
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/Widget"}},
                                "broken": "not media info",
                            }
                        },
                        "broken": "not a response",
                    },
                },
            },
        },
        "tags": [None, {"name": "Widgets"}],
        "components": {"schemas": {"Widget": {"type": "object"}}},
    }

    internal = normalize.load_any_spec_as_internal(spec)
    operation = internal["operations"][("/widgets/{}", "get")]

    assert operation["request_body"] == {"application/json": "string"}
    assert operation["responses"] == {
        "200": {"application/json": "#/components/schemas/Widget"}
    }
    assert operation["tag"] == ""
    assert internal["schemas"] == {"Widget": {"type": "object"}}
    assert normalize.load_openapi3_as_internal({"components": "bad"})["schemas"] == {}
    assert normalize.load_openapi3_as_internal({"components": {"schemas": []}})["schemas"] == {}


def test_relationship_helpers_cover_wrappers_fallbacks_and_exposure():
    direct = SimpleNamespace(mapper=object())
    wrapped = SimpleNamespace(relationship=direct)

    assert relationship_property(direct) is direct
    assert relationship_property(wrapped) is direct
    assert relationship_property(object()) is None
    assert resolve_relationships(type("NoMapper", (), {})) == {}

    hidden = SimpleNamespace(mapper=object(), expose=False)
    assert not relationship_is_exposed(type("Model", (), {}), "hidden", hidden)

    mapped_hidden = SimpleNamespace(mapper=object(), expose=False)
    mapped_model = type(
        "MappedModel",
        (),
        {"__mapper__": SimpleNamespace(relationships={"hidden": mapped_hidden})},
    )
    assert not relationship_is_exposed(mapped_model, "hidden", direct)

    descriptor_model = type("DescriptorModel", (), {"hidden": SimpleNamespace(expose=False)})
    assert not relationship_is_exposed(descriptor_model, "hidden", direct)
    property_model = type(
        "PropertyModel",
        (),
        {"hidden": SimpleNamespace(property=SimpleNamespace(expose=False))},
    )
    assert not relationship_is_exposed(property_model, "hidden", direct)


def test_relationship_helpers_tolerate_dynamic_mapper_errors_and_iterate():
    class BrokenRelationships:
        def get(self, name):
            raise RuntimeError(name)

    broken_mapper_model = type(
        "BrokenMapperModel",
        (),
        {"__mapper__": SimpleNamespace(relationships=BrokenRelationships())},
    )
    assert relationship_is_exposed(broken_mapper_model, "rel", SimpleNamespace(mapper=object()))

    class BrokenAttributeMeta(type):
        def __getattribute__(cls, name):
            if name == "rel":
                raise RuntimeError(name)
            return super().__getattribute__(name)

    class BrokenAttributeModel(metaclass=BrokenAttributeMeta):
        pass

    assert relationship_is_exposed(BrokenAttributeModel, "rel", SimpleNamespace(mapper=object()))

    visible = SimpleNamespace(key="visible", mapper=object())
    fallback = SimpleNamespace(key="fallback", mapper=object())
    hidden = SimpleNamespace(key="hidden", mapper=object(), expose=False)
    model = type(
        "IterableModel",
        (),
        {
            "_s_relationships": {
                "visible": SimpleNamespace(relationship=visible),
                "fallback": object(),
                "missing": object(),
                "hidden": hidden,
            },
            "__mapper__": SimpleNamespace(relationships=[visible, fallback, hidden]),
        },
    )

    assert list(iter_exposed_relationship_properties(model)) == [
        ("visible", visible),
        ("fallback", fallback),
    ]
