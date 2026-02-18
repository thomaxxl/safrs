# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple, TypedDict, cast

HTTP_METHODS = {"get", "post", "patch", "delete", "put", "options", "head"}
PATH_PARAM_RE = re.compile(r"\{[^}]+\}")
JSONAPI_MEDIA_TYPE = "application/vnd.api+json"


class InternalParameter(TypedDict):
    name: str
    in_: str
    required: bool
    type: str


class InternalOperation(TypedDict):
    tag: str
    summary: str
    description: str
    parameters: List[InternalParameter]
    request_body: Dict[str, str]
    responses: Dict[str, Dict[str, str]]


class InternalSpec(TypedDict):
    operations: Dict[Tuple[str, str], InternalOperation]
    tags: Dict[str, str]
    schemas: Dict[str, Any]


def canonical_path(path: str) -> str:
    normalized = path or "/"
    if normalized != "/" and normalized.endswith("/"):
        normalized = normalized.rstrip("/")
    normalized = PATH_PARAM_RE.sub("{}", normalized)
    return normalized or "/"


def _join_base_path(base_path: str, path: str) -> str:
    if not base_path:
        return path
    if path.startswith(base_path):
        return path
    return f"{base_path.rstrip('/')}/{path.lstrip('/')}"


def _schema_signature(schema: Any) -> str:
    if not isinstance(schema, dict):
        return "none"
    if "$ref" in schema:
        return str(schema["$ref"])
    if "type" in schema:
        schema_type = str(schema["type"])
        if schema_type == "array":
            return f"array[{_schema_signature(schema.get('items', {}))}]"
        return schema_type
    if "properties" in schema:
        prop_names = ",".join(sorted(str(name) for name in schema.get("properties", {}).keys()))
        return f"object[{prop_names}]"
    return "object"


def _normalize_parameter(parameter: Dict[str, Any]) -> InternalParameter | None:
    param_in = str(parameter.get("in", ""))
    if param_in not in {"query", "path"}:
        return None
    name = str(parameter.get("name", ""))
    if param_in == "path":
        name = "{}"

    schema = parameter.get("schema", {})
    param_type = parameter.get("type")
    if isinstance(schema, dict) and "type" in schema:
        param_type = schema["type"]
    elif isinstance(schema, dict) and "$ref" in schema:
        param_type = schema["$ref"]
    if param_type is None:
        param_type = "string"

    return {
        "name": name,
        "in_": param_in,
        "required": bool(parameter.get("required", False)),
        "type": str(param_type),
    }


def _collect_parameters(path_item: Dict[str, Any], operation: Dict[str, Any]) -> List[InternalParameter]:
    combined = list(path_item.get("parameters", [])) + list(operation.get("parameters", []))
    normalized: List[InternalParameter] = []
    seen: set[tuple[str, str]] = set()
    for parameter in combined:
        if not isinstance(parameter, dict):
            continue
        parsed = _normalize_parameter(parameter)
        if parsed is None:
            continue
        key = (parsed["in_"], parsed["name"])
        if key in seen:
            continue
        seen.add(key)
        normalized.append(parsed)
    return normalized


def load_swagger2_as_internal(spec: Dict[str, Any]) -> InternalSpec:
    base_path = str(spec.get("basePath", ""))
    global_consumes = list(spec.get("consumes", []))
    global_produces = list(spec.get("produces", []))
    operations: Dict[Tuple[str, str], InternalOperation] = {}

    for raw_path, path_item in spec.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            method_name = str(method).lower()
            if method_name not in HTTP_METHODS or not isinstance(operation, dict):
                continue

            full_path = canonical_path(_join_base_path(base_path, str(raw_path)))
            key = (full_path, method_name)
            parameters = _collect_parameters(path_item, operation)

            request_body: Dict[str, str] = {}
            body_parameter = next((p for p in operation.get("parameters", []) if isinstance(p, dict) and p.get("in") == "body"), None)
            if isinstance(body_parameter, dict):
                consumes = list(operation.get("consumes", [])) or list(path_item.get("consumes", [])) or global_consumes
                if not consumes:
                    consumes = [JSONAPI_MEDIA_TYPE]
                body_signature = _schema_signature(body_parameter.get("schema", {}))
                request_body = {media: body_signature for media in consumes}

            responses: Dict[str, Dict[str, str]] = {}
            for status_code, response in operation.get("responses", {}).items():
                if not isinstance(response, dict):
                    continue
                schema_signature = _schema_signature(response.get("schema", {}))
                if schema_signature == "none":
                    responses[str(status_code)] = {}
                    continue
                produces = list(operation.get("produces", [])) or list(path_item.get("produces", [])) or global_produces
                if not produces:
                    produces = [JSONAPI_MEDIA_TYPE]
                responses[str(status_code)] = {media: schema_signature for media in produces}

            op_tags = operation.get("tags", [])
            tag = str(op_tags[0]) if isinstance(op_tags, list) and op_tags else ""
            operations[key] = {
                "tag": tag,
                "summary": str(operation.get("summary", "")),
                "description": str(operation.get("description", "")),
                "parameters": parameters,
                "request_body": request_body,
                "responses": responses,
            }

    tags: Dict[str, str] = {}
    for tag_data in spec.get("tags", []):
        if not isinstance(tag_data, dict):
            continue
        tag_name = str(tag_data.get("name", ""))
        tags[tag_name] = str(tag_data.get("description", ""))

    schemas = cast(Dict[str, Any], spec.get("definitions", {}))
    return {"operations": operations, "tags": tags, "schemas": schemas}


def load_openapi3_as_internal(spec: Dict[str, Any]) -> InternalSpec:
    operations: Dict[Tuple[str, str], InternalOperation] = {}

    for raw_path, path_item in spec.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            method_name = str(method).lower()
            if method_name not in HTTP_METHODS or not isinstance(operation, dict):
                continue

            key = (canonical_path(str(raw_path)), method_name)
            parameters = _collect_parameters(path_item, operation)

            request_body: Dict[str, str] = {}
            raw_request_body = operation.get("requestBody", {})
            if isinstance(raw_request_body, dict):
                content = raw_request_body.get("content", {})
                if isinstance(content, dict):
                    for media, media_info in content.items():
                        if not isinstance(media_info, dict):
                            continue
                        request_body[str(media)] = _schema_signature(media_info.get("schema", {}))

            responses: Dict[str, Dict[str, str]] = {}
            for status_code, response in operation.get("responses", {}).items():
                if not isinstance(response, dict):
                    continue
                content = response.get("content", {})
                media_map: Dict[str, str] = {}
                if isinstance(content, dict):
                    for media, media_info in content.items():
                        if not isinstance(media_info, dict):
                            continue
                        media_map[str(media)] = _schema_signature(media_info.get("schema", {}))
                responses[str(status_code)] = media_map

            op_tags = operation.get("tags", [])
            tag = str(op_tags[0]) if isinstance(op_tags, list) and op_tags else ""
            operations[key] = {
                "tag": tag,
                "summary": str(operation.get("summary", "")),
                "description": str(operation.get("description", "")),
                "parameters": parameters,
                "request_body": request_body,
                "responses": responses,
            }

    tags: Dict[str, str] = {}
    for tag_data in spec.get("tags", []):
        if not isinstance(tag_data, dict):
            continue
        tag_name = str(tag_data.get("name", ""))
        tags[tag_name] = str(tag_data.get("description", ""))

    components = spec.get("components", {})
    schemas: Dict[str, Any] = {}
    if isinstance(components, dict):
        raw_schemas = components.get("schemas", {})
        if isinstance(raw_schemas, dict):
            schemas = raw_schemas
    return {"operations": operations, "tags": tags, "schemas": schemas}


def load_any_spec_as_internal(spec: Dict[str, Any]) -> InternalSpec:
    if "swagger" in spec:
        return load_swagger2_as_internal(spec)
    return load_openapi3_as_internal(spec)
