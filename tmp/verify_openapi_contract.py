#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run a demo API app and verify it matches a given OpenAPI / Swagger spec.

This script is designed for the SAFRS demo apps in `safrs/tmp/` but works for
any app that:
  - can be started as: `python app.py <host> <port>`
  - exposes a readiness endpoint at `/health`

It auto-detects the API base path from the spec:
  - Swagger / OpenAPI 2.0: uses `basePath`
  - OpenAPI 3.x: uses the first server URL path if it is relative (e.g. "/api")

Schemathesis v4 uses `--url` (NOT `--base-url`).

Important: The app process can get *very* chatty under fuzzing (stack traces,
validation errors, etc.). If you start it with stdout=PIPE and don't drain that
pipe continuously, the OS pipe buffer will fill up and the app will block on
logging. That looks like "random" read timeouts / connection failures.

This verifier therefore drains the app's stdout in a background thread and keeps
only a small ring buffer of the last N lines for reporting at the end.

Usage examples:
  python verify_openapi_contract.py --app fastapi_app.py --spec fastapi.openapi.json
  python verify_openapi_contract.py --app flask_app.py  --spec flask.swagger.json

Auth:
  export API_AUTHORIZATION='Bearer ...'  # or pass --auth

Exit codes:
  0  success (all checks passed)
  1  contract mismatch / test failure
  2  setup / runtime error
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from collections import deque
from pathlib import Path
from urllib.parse import urlparse
from typing import Any, Optional

_COLLECTION_TO_SEED_ID_KEY: dict[str, str] = {
    "People": "PersonId",
    "Books": "BookId",
    "Publishers": "PublisherId",
    "Reviews": "ReviewId",
}


def _find_free_port(host: str) -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, 0))
        return int(s.getsockname()[1])
    finally:
        s.close()


def _wait_http_ok(url: str, timeout_s: float) -> None:
    try:
        import requests
    except Exception as e:
        raise RuntimeError("Missing dependency 'requests' (pip install requests)") from e

    deadline = time.time() + timeout_s
    last_err = None
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=0.5)
            if r.status_code < 500:
                return
        except Exception as e:
            last_err = e
        time.sleep(0.1)

    msg = "Service didn't become ready: %s" % url
    if last_err is not None:
        msg += " (last error: %r)" % (last_err,)
    raise RuntimeError(msg)


def _load_spec(spec_path: Path) -> dict:
    with spec_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _extract_base_path_from_spec(spec: dict) -> str:
    """Return an API base path prefix (e.g. '/api') if present, else ''."""

    # Swagger / OpenAPI 2.0
    if str(spec.get("swagger", "")) == "2.0":
        base_path = spec.get("basePath", "")
        if isinstance(base_path, str):
            return base_path
        return ""

    # OpenAPI 3.x
    if "openapi" in spec:
        servers = spec.get("servers")
        if isinstance(servers, list) and servers:
            first = servers[0]
            if isinstance(first, dict):
                url = first.get("url", "")
                if isinstance(url, str) and url:
                    # Relative server URL like "/api" is common in FastAPI
                    if url.startswith("/"):
                        return url
                    # Absolute server URL like "http://localhost:8000/api"
                    if url.startswith("http://") or url.startswith("https://"):
                        try:
                            parsed = urlparse(url)
                            return parsed.path or ""
                        except Exception:
                            return ""
        return ""

    return ""


def _join_base_url(base_url: str, base_path: str) -> str:
    """Join 'http://host:port' + '/api' -> 'http://host:port/api'."""

    if not base_path:
        return base_url

    # Normalize
    if base_path == "/":
        return base_url

    return base_url.rstrip("/") + "/" + base_path.lstrip("/")


def _coerce_seed_values(values: list[Any], schema_type: str) -> list[Any]:
    if schema_type == "integer":
        result: list[Any] = []
        for value in values:
            try:
                result.append(int(value))
            except Exception:
                continue
        return result
    return [str(value) for value in values]


def _seed_key_for_field(field_name: str) -> str:
    parts = [part for part in str(field_name).split("_") if part]
    return "".join(part[:1].upper() + part[1:] for part in parts)


def _collection_from_path(path: str) -> Optional[str]:
    """Extract the top-level collection segment from a spec path."""
    segments = [segment for segment in str(path).split("/") if segment]
    if segments and segments[0] == "api":
        segments = segments[1:]
    if not segments:
        return None
    return str(segments[0])


def _seed_key_for_collection(collection: str) -> Optional[str]:
    return _COLLECTION_TO_SEED_ID_KEY.get(str(collection))


def _collections_requiring_object_id_seed(paths: dict[str, Any]) -> set[str]:
    collections: set[str] = set()
    for path, operations in paths.items():
        if not isinstance(operations, dict):
            continue
        collection = _collection_from_path(path)
        if not collection:
            continue
        for operation in operations.values():
            if not isinstance(operation, dict):
                continue
            parameters = operation.get("parameters")
            if not isinstance(parameters, list):
                continue
            for parameter in parameters:
                if not isinstance(parameter, dict):
                    continue
                if str(parameter.get("in")) != "path":
                    continue
                if str(parameter.get("name", "")) != "object_id":
                    continue
                collections.add(collection)
                break
    return collections


def _validate_object_id_seed_coverage(paths: dict[str, Any], seed: dict[str, Any]) -> None:
    required_collections = sorted(_collections_requiring_object_id_seed(paths))
    if not required_collections:
        return

    unknown_collections: list[str] = []
    missing_seed_keys: list[tuple[str, str]] = []
    for collection in required_collections:
        seed_key = _seed_key_for_collection(collection)
        if not seed_key:
            unknown_collections.append(collection)
            continue
        if seed_key not in seed:
            missing_seed_keys.append((collection, seed_key))

    if unknown_collections:
        raise RuntimeError(
            "Spec contains collections not present in seed mapping required for object_id patching: %s. "
            "You probably used the wrong spec. Did you mean fastapi.openapi.json?"
            % (", ".join(unknown_collections),)
        )

    if missing_seed_keys:
        detail = ", ".join(f"{collection}->{seed_key}" for collection, seed_key in missing_seed_keys)
        raise RuntimeError(
            "Seed payload missing ids required for object_id patching: %s. "
            "Ensure /seed includes these identifiers."
            % detail
        )


def _spec_major(spec: dict[str, Any]) -> int:
    if "openapi" in spec:
        return 3
    return 2


def _operation_summary_text(operation: dict[str, Any]) -> str:
    summary = str(operation.get("summary", ""))
    description = str(operation.get("description", ""))
    return (summary + " " + description).lower()


def _is_relationship_path(path: str) -> Optional[tuple[str, str, str]]:
    segments = [segment for segment in str(path).split("/") if segment]
    if segments and segments[0] == "api":
        segments = segments[1:]
    if len(segments) != 3:
        return None
    parent_collection, parent_id_segment, rel_name = segments
    if not (parent_id_segment.startswith("{") and parent_id_segment.endswith("}")):
        return None
    if not rel_name or (rel_name.startswith("{") and rel_name.endswith("}")):
        return None
    return parent_collection, parent_id_segment[1:-1], rel_name


def _swagger2_body_schema(operation: dict[str, Any]) -> Optional[dict[str, Any]]:
    parameters = operation.get("parameters")
    if not isinstance(parameters, list):
        return None
    for parameter in parameters:
        if not isinstance(parameter, dict):
            continue
        if str(parameter.get("in")) != "body":
            continue
        schema = parameter.get("schema")
        if isinstance(schema, dict):
            return schema
    return None


def _openapi3_body_schema(operation: dict[str, Any]) -> Optional[dict[str, Any]]:
    request_body = operation.get("requestBody")
    if not isinstance(request_body, dict):
        return None
    content = request_body.get("content")
    if not isinstance(content, dict):
        return None
    preferred_types = ["application/vnd.api+json", "application/json"]
    for media_type in preferred_types:
        media_spec = content.get(media_type)
        if isinstance(media_spec, dict):
            schema = media_spec.get("schema")
            if isinstance(schema, dict):
                return schema
    for media_spec in content.values():
        if not isinstance(media_spec, dict):
            continue
        schema = media_spec.get("schema")
        if isinstance(schema, dict):
            return schema
    return None


def _operation_body_schema(operation: dict[str, Any], spec_major: int) -> Optional[dict[str, Any]]:
    if spec_major == 3:
        return _openapi3_body_schema(operation)
    return _swagger2_body_schema(operation)


def _resolve_ref(spec: dict[str, Any], ref: str) -> Optional[dict[str, Any]]:
    if not isinstance(ref, str):
        return None

    if ref.startswith("#/components/schemas/"):
        name = ref.split("/", 3)[-1]
        components = spec.get("components", {})
        if isinstance(components, dict):
            schemas = components.get("schemas", {})
            if isinstance(schemas, dict):
                target = schemas.get(name)
                if isinstance(target, dict):
                    return target

    if ref.startswith("#/definitions/"):
        name = ref.split("/", 2)[-1]
        definitions = spec.get("definitions", {})
        if isinstance(definitions, dict):
            target = definitions.get(name)
            if isinstance(target, dict):
                return target

    return None


def _deref_schema(
    spec: dict[str, Any],
    schema: dict[str, Any],
    *,
    path: str,
    method: str,
    strict: bool = False,
) -> dict[str, Any]:
    seen: set[str] = set()
    current = schema
    while isinstance(current, dict) and "$ref" in current:
        ref = current.get("$ref")
        if not isinstance(ref, str) or not ref:
            if strict:
                raise RuntimeError(f"Invalid schema reference in {method.upper()} {path}: {ref!r}")
            return current
        if ref in seen:
            if strict:
                raise RuntimeError(f"Cyclic schema reference {ref!r} in {method.upper()} {path}")
            return current
        seen.add(ref)
        resolved = _resolve_ref(spec, ref)
        if not isinstance(resolved, dict):
            if strict:
                raise RuntimeError(f"Unresolvable schema reference {ref!r} in {method.upper()} {path}")
            return current
        current = resolved
    return current


def _relationship_data_schema(body_schema: dict[str, Any]) -> Optional[dict[str, Any]]:
    if str(body_schema.get("type", "object")) != "object":
        return None
    properties = body_schema.get("properties")
    if not isinstance(properties, dict):
        return None
    data_schema = properties.get("data")
    if not isinstance(data_schema, dict):
        return None

    data_type = data_schema.get("type")
    if isinstance(data_type, str) and data_type in ("array", "object"):
        return data_schema
    if "$ref" in data_schema:
        return data_schema

    for union_key in ("anyOf", "oneOf"):
        union_variants = data_schema.get(union_key)
        if not isinstance(union_variants, list):
            continue
        for variant in union_variants:
            if not isinstance(variant, dict):
                continue
            if variant.get("type") == "null":
                continue
            variant_type = variant.get("type")
            if isinstance(variant_type, str) and variant_type in ("array", "object"):
                return variant
            if "$ref" in variant:
                return variant
    return None


def _relationship_type_enum(data_schema: dict[str, Any]) -> list[str]:
    data_type = str(data_schema.get("type", ""))
    type_schema: Optional[dict[str, Any]] = None
    if data_type == "array":
        items = data_schema.get("items")
        if isinstance(items, dict):
            properties = items.get("properties")
            if isinstance(properties, dict):
                type_value = properties.get("type")
                if isinstance(type_value, dict):
                    type_schema = type_value
    else:
        properties = data_schema.get("properties")
        if isinstance(properties, dict):
            type_value = properties.get("type")
            if isinstance(type_value, dict):
                type_schema = type_value
    if not isinstance(type_schema, dict):
        return []
    enum_values = type_schema.get("enum")
    if not isinstance(enum_values, list):
        return []
    return [str(value) for value in enum_values]


def _validate_relationship_seed(
    rel_doc: Any,
    data_schema: dict[str, Any],
    seed_key: str,
    path: str,
    method: str,
) -> list[dict[str, Any]]:
    if not isinstance(rel_doc, dict):
        raise RuntimeError(f"Seed relationship payload for {seed_key} must be an object ({method.upper()} {path})")
    if "data" not in rel_doc:
        raise RuntimeError(f"Seed relationship payload for {seed_key} must include 'data' ({method.upper()} {path})")

    payload_data = rel_doc.get("data")
    data_type = str(data_schema.get("type", ""))

    items: list[dict[str, Any]] = []
    if data_type == "array":
        if not isinstance(payload_data, list):
            raise RuntimeError(
                f"Seed relationship payload for {seed_key} must use array data ({method.upper()} {path})"
            )
        if not payload_data:
            raise RuntimeError(
                f"Seed relationship payload for {seed_key} must include at least one identifier ({method.upper()} {path})"
            )
        items = [item for item in payload_data if isinstance(item, dict)]
        if len(items) != len(payload_data):
            raise RuntimeError(
                f"Seed relationship payload for {seed_key} has invalid identifier objects ({method.upper()} {path})"
            )
    else:
        if payload_data is None:
            raise RuntimeError(
                f"Seed relationship payload for {seed_key} must provide an identifier object ({method.upper()} {path})"
            )
        if not isinstance(payload_data, dict):
            raise RuntimeError(
                f"Seed relationship payload for {seed_key} must use object data ({method.upper()} {path})"
            )
        items = [payload_data]

    for item in items:
        item_id = item.get("id")
        item_type = item.get("type")
        if item_id in (None, "") or item_type in (None, ""):
            raise RuntimeError(
                f"Seed relationship payload for {seed_key} must include non-empty id/type ({method.upper()} {path})"
            )

    expected_types = _relationship_type_enum(data_schema)
    if expected_types:
        invalid_types = sorted({str(item.get("type")) for item in items if str(item.get("type")) not in expected_types})
        if invalid_types:
            raise RuntimeError(
                f"Seed relationship payload for {seed_key} has incompatible types {invalid_types} "
                f"(expected {expected_types}) for {method.upper()} {path}"
            )

    return items


def _apply_relationship_seed_to_schema(data_schema: dict[str, Any], items: list[dict[str, Any]]) -> None:
    ids = [str(item.get("id")) for item in items]
    types: list[str] = []
    for item in items:
        item_type = str(item.get("type"))
        if item_type not in types:
            types.append(item_type)

    data_type = str(data_schema.get("type", ""))
    if data_type == "array":
        data_schema["minItems"] = len(items)
        data_schema["maxItems"] = len(items)
        items_schema = data_schema.setdefault("items", {})
        if not isinstance(items_schema, dict):
            return
        properties = items_schema.setdefault("properties", {})
        if not isinstance(properties, dict):
            return
        id_schema = properties.setdefault("id", {"type": "string"})
        if isinstance(id_schema, dict):
            coerced_ids = _coerce_seed_values(ids, str(id_schema.get("type", "string")))
            if coerced_ids:
                id_schema["enum"] = coerced_ids
                id_schema.setdefault("default", coerced_ids[0])
        type_schema = properties.setdefault("type", {"type": "string"})
        if isinstance(type_schema, dict) and types:
            type_schema["enum"] = types
            type_schema.setdefault("default", types[0])
        return

    properties = data_schema.setdefault("properties", {})
    if not isinstance(properties, dict):
        return
    id_schema = properties.setdefault("id", {"type": "string"})
    if isinstance(id_schema, dict):
        coerced_ids = _coerce_seed_values(ids, str(id_schema.get("type", "string")))
        if coerced_ids:
            id_schema["enum"] = coerced_ids
            id_schema.setdefault("default", coerced_ids[0])
    type_schema = properties.setdefault("type", {"type": "string"})
    if isinstance(type_schema, dict) and types:
        type_schema["enum"] = types
        type_schema.setdefault("default", types[0])


def _patch_schema_with_seed(schema: dict[str, Any], seed: dict[str, Any]) -> None:
    schema_type = str(schema.get("type", ""))
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        items = schema.get("items")
        if isinstance(items, dict):
            _patch_schema_with_seed(items, seed)
        return

    relationship_ids: list[Any] = []
    for key in ("PersonId", "FriendId"):
        if key in seed:
            relationship_ids.append(seed[key])

    for field_name, field_schema in properties.items():
        if not isinstance(field_schema, dict):
            continue
        _patch_schema_with_seed(field_schema, seed)

        field_type = str(field_schema.get("type", "string"))
        enum_values: list[Any] = []
        seed_key = str(field_name)
        if seed_key in seed:
            enum_values = [seed[seed_key]]
        else:
            camel_key = _seed_key_for_field(str(field_name))
            if camel_key in seed:
                enum_values = [seed[camel_key]]
            elif str(field_name) == "id" and relationship_ids:
                enum_values = relationship_ids
            elif str(field_name).endswith("_id") and relationship_ids:
                enum_values = relationship_ids

        coerced_values = _coerce_seed_values(enum_values, field_type)
        if coerced_values:
            field_schema["enum"] = coerced_values
            field_schema.setdefault("default", coerced_values[0])


def _relationship_path_params_for_seed_key(seed: dict[str, Any], seed_key: str, path: str, method: str) -> dict[str, Any]:
    relationship_path_params = seed.get("relationship_path_params")
    if not isinstance(relationship_path_params, dict):
        raise RuntimeError(
            f"Seed payload missing 'relationship_path_params' required by {method.upper()} {path}"
        )
    params = relationship_path_params.get(seed_key)
    if not isinstance(params, dict) or not params:
        raise RuntimeError(
            f"Missing relationship path params for {seed_key} required by {method.upper()} {path}"
        )
    for name, value in params.items():
        if not isinstance(name, str) or not name:
            raise RuntimeError(
                f"Invalid relationship path parameter name for {seed_key} in {method.upper()} {path}"
            )
        if not isinstance(value, str) or not value:
            raise RuntimeError(
                f"Invalid relationship path parameter value for {seed_key}.{name} in {method.upper()} {path}"
            )
    return params


def _translate_relationship_parent_param(
    parent_collection: str,
    parent_id_param: str,
    seed_key: str,
    path: str,
    method: str,
    relationship_path_params: dict[str, Any],
) -> dict[str, Any]:
    """Translate canonical seed path params to operation-specific path param names."""
    if parent_id_param in relationship_path_params:
        return relationship_path_params

    if parent_id_param != "object_id":
        return relationship_path_params

    canonical_key = _seed_key_for_collection(parent_collection)
    if not canonical_key:
        raise RuntimeError(
            "Unsupported collection %r for relationship path translation (%s %s)"
            % (parent_collection, method.upper(), path)
        )

    if canonical_key not in relationship_path_params:
        raise RuntimeError(
            "Seed relationship_path_params for %s missing canonical key %r required to fill %r (%s %s)"
            % (seed_key, canonical_key, parent_id_param, method.upper(), path)
        )

    return {"object_id": relationship_path_params[canonical_key]}


def _patch_spec_with_seed(spec: dict[str, Any], seed: dict[str, Any]) -> dict[str, Any]:
    patched = json.loads(json.dumps(spec))
    major = _spec_major(patched)
    paths = patched.get("paths")
    if not isinstance(paths, dict):
        return patched

    _validate_object_id_seed_coverage(paths, seed)

    relationships_map = seed.get("relationships")
    for path, operations in paths.items():
        if not isinstance(operations, dict):
            continue
        collection = _collection_from_path(path)
        relationship_info = _is_relationship_path(path)
        for method, operation in operations.items():
            if not isinstance(operation, dict):
                continue
            method_lc = str(method).lower()
            parameters = operation.get("parameters")
            if not isinstance(parameters, list):
                parameters = []
            for parameter in parameters:
                if not isinstance(parameter, dict):
                    continue
                if str(parameter.get("in")) != "path":
                    continue
                name = str(parameter.get("name", ""))
                if name in seed:
                    value = seed[name]
                    parameter["enum"] = [value]
                    parameter.setdefault("default", value)
                    continue
                if name == "object_id":
                    seed_id_key = _seed_key_for_collection(collection or "")
                    if not seed_id_key or seed_id_key not in seed:
                        raise RuntimeError(
                            "Missing seed id for object_id patching: collection=%r seed_key=%r (path %s)"
                            % (collection, seed_id_key, path)
                        )
                    value = seed[seed_id_key]
                    parameter["enum"] = [value]
                    parameter.setdefault("default", value)

            body_schema = _operation_body_schema(operation, major)
            resolved_body_schema: Optional[dict[str, Any]] = None
            if isinstance(body_schema, dict):
                resolved_body_schema = _deref_schema(
                    patched,
                    body_schema,
                    path=path,
                    method=method_lc,
                    strict=False,
                )
                _patch_schema_with_seed(resolved_body_schema, seed)

            if method_lc not in {"post", "patch", "delete"}:
                continue
            if relationship_info is None:
                continue

            parent_collection, parent_id_param, rel_name = relationship_info
            seed_key = f"{parent_collection}.{rel_name}"
            summary_text = _operation_summary_text(operation)
            is_relationship_operation = ("relationship" in summary_text) or (
                isinstance(relationships_map, dict) and seed_key in relationships_map
            )
            if not is_relationship_operation:
                continue

            relationship_path_params = _relationship_path_params_for_seed_key(seed, seed_key, path, method_lc)
            relationship_path_params = _translate_relationship_parent_param(
                parent_collection,
                parent_id_param,
                seed_key,
                path,
                method_lc,
                relationship_path_params,
            )
            if parent_id_param not in relationship_path_params:
                raise RuntimeError(
                    f"Missing relationship path parameter '{parent_id_param}' for {seed_key} "
                    f"required by {method_lc.upper()} {path}"
                )
            seen_path_param_names = set()
            for parameter in parameters:
                if not isinstance(parameter, dict):
                    continue
                if str(parameter.get("in")) != "path":
                    continue
                name = str(parameter.get("name", ""))
                if name not in relationship_path_params:
                    continue
                seen_path_param_names.add(name)
                value = relationship_path_params[name]
                parameter["enum"] = [value]
                parameter["default"] = value
            missing_path_params = sorted(set(relationship_path_params.keys()) - seen_path_param_names)
            if missing_path_params:
                raise RuntimeError(
                    f"Relationship path parameters {missing_path_params} for {seed_key} were not found in "
                    f"{method_lc.upper()} {path}"
                )

            if not isinstance(body_schema, dict):
                raise RuntimeError(f"Missing request body schema for relationship operation {method_lc.upper()} {path}")
            resolved_relationship_body = _deref_schema(
                patched,
                body_schema,
                path=path,
                method=method_lc,
                strict=True,
            )
            data_schema = _relationship_data_schema(resolved_relationship_body)
            if not isinstance(data_schema, dict):
                raise RuntimeError(
                    f"Invalid relationship schema for {method_lc.upper()} {path}: expected JSON:API relationship document"
                )

            if not isinstance(relationships_map, dict):
                raise RuntimeError(
                    f"Seed payload missing 'relationships' map required by {method_lc.upper()} {path}"
                )
            if seed_key not in relationships_map:
                raise RuntimeError(
                    f"Missing seed relationship payload for {seed_key} required by {method_lc.upper()} {path}"
                )

            rel_doc = relationships_map[seed_key]
            items = _validate_relationship_seed(rel_doc, data_schema, seed_key, path, method_lc)
            _apply_relationship_seed_to_schema(data_schema, items)
    return patched


def _fetch_seed_payload(base_url: str, request_timeout_s: float) -> dict[str, Any]:
    try:
        import requests
    except Exception:
        return {}

    seed_url = base_url.rstrip("/") + "/seed"
    timeout_s = max(0.5, min(float(request_timeout_s), 5.0))
    try:
        response = requests.get(seed_url, timeout=timeout_s)
        if response.status_code >= 400:
            return {}
        payload = response.json()
        if isinstance(payload, dict):
            return payload
    except Exception:
        return {}
    return {}


def _prepare_spec_for_run(spec_path: Path, base_url: str, request_timeout_s: float) -> tuple[Path, bool]:
    seed = _fetch_seed_payload(base_url, request_timeout_s)
    if not seed:
        return spec_path, False

    spec = _load_spec(spec_path)
    patched = _patch_spec_with_seed(spec, seed)
    fd, tmp_path = tempfile.mkstemp(prefix="safrs_contract_spec_", suffix=".json")
    os.close(fd)
    patched_path = Path(tmp_path)
    patched_path.write_text(json.dumps(patched), encoding="utf-8")
    return patched_path, True


def _start_app_log_drain(
    proc: subprocess.Popen,
    ring: deque,
    tee: bool,
    log_fp: object,
) -> threading.Thread:
    """Continuously drain proc.stdout so the child can't block on log writes."""

    def _reader() -> None:
        if proc.stdout is None:
            return
        try:
            for raw in proc.stdout:
                # `raw` includes the trailing newline.
                line = raw.rstrip("\n")
                ring.append(line)
                if log_fp is not None:
                    try:
                        log_fp.write(raw)
                    except Exception:
                        # Don't let log file I/O kill the verifier.
                        pass
                if tee:
                    try:
                        sys.stdout.write(raw)
                        sys.stdout.flush()
                    except Exception:
                        pass
        finally:
            try:
                if log_fp is not None:
                    log_fp.flush()
            except Exception:
                pass

    t = threading.Thread(target=_reader, name="app-log-drain", daemon=True)
    t.start()
    return t


def _run_contract_tests(
    spec_path: Path,
    effective_url: str,
    max_examples: int,
    request_timeout_s: float,
    phases: str,
    auth_header: str,
    content_type: str,
) -> int:
    """Run schemathesis against the effective_url using a local spec file."""

    st = shutil.which("schemathesis")
    base_cmd = [st] if st else [sys.executable, "-m", "schemathesis"]

    cmd = (
        base_cmd
        + [
            "run",
            str(spec_path),
            "--url",
            effective_url,
            "--checks",
            "not_a_server_error,status_code_conformance,content_type_conformance,response_headers_conformance,response_schema_conformance",
            "--phases",
            phases,
            "--max-examples",
            str(max_examples),
            "--request-timeout",
            str(request_timeout_s),
            "--header",
            "Accept: application/vnd.api+json",
            "--header",
            "Content-Type: " + str(content_type),
        ]
    )

    if auth_header:
        cmd.extend(["--header", "Authorization: " + auth_header])

    print("[+] Running:")
    print("    " + " ".join(cmd))
    return subprocess.call(cmd)


def main() -> int:
    here = Path(__file__).resolve().parent

    ap = argparse.ArgumentParser()
    ap.add_argument("--app", required=True, help="Path to app entrypoint (python file)")
    ap.add_argument("--spec", required=True, help="Path to OpenAPI / Swagger JSON")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=0, help="0 means auto-select free port")
    ap.add_argument("--startup-timeout", type=float, default=15.0)
    ap.add_argument("--max-examples", type=int, default=25)
    ap.add_argument("--request-timeout", type=float, default=10.0)
    ap.add_argument(
        "--phases",
        default="examples,fuzzing",
        help="Schemathesis phases (e.g. 'examples,fuzzing' or add 'stateful')",
    )
    ap.add_argument(
        "--auth",
        default=os.environ.get("API_AUTHORIZATION", ""),
        help="Authorization header value (e.g. 'Bearer ...'). Can also be set via API_AUTHORIZATION env var.",
    )
    ap.add_argument(
        "--force-base-path",
        default="",
        help="Override the base path from the spec (example: '/api'). Useful if your spec is wrong.",
    )
    ap.add_argument(
        "--content-type",
        default="application/vnd.api+json",
        help="Content-Type header to send on all requests (default: JSON:API media type).",
    )
    ap.add_argument(
        "--app-log-lines",
        type=int,
        default=200,
        help="How many app log lines to keep and print at the end.",
    )
    ap.add_argument(
        "--tee-app-logs",
        action="store_true",
        help="Stream app logs to stdout while tests run (can be very noisy).",
    )
    ap.add_argument(
        "--app-log-file",
        default="",
        help="Optional file path to write the full app logs.",
    )
    args = ap.parse_args()

    app_path = Path(args.app).resolve()
    spec_path = Path(args.spec).resolve()

    if not app_path.exists():
        print("[-] App file not found: %s" % app_path, file=sys.stderr)
        return 2
    if not spec_path.exists():
        print("[-] Spec file not found: %s" % spec_path, file=sys.stderr)
        return 2

    host = args.host
    port = int(args.port) if int(args.port) != 0 else _find_free_port(host)

    try:
        spec = _load_spec(spec_path)
    except Exception as e:
        print("[-] Failed to load spec JSON: %s" % (e,), file=sys.stderr)
        return 2

    base_path = args.force_base_path.strip() or _extract_base_path_from_spec(spec)
    base_url = "http://%s:%d" % (host, port)
    effective_url = _join_base_url(base_url, base_path)

    env = dict(os.environ)
    env.setdefault("PYTHONUNBUFFERED", "1")
    app_stem = app_path.stem.lower()
    if "flask" in app_stem:
        framework = "flask"
    elif "fastapi" in app_stem:
        framework = "fastapi"
    else:
        framework = "app"
    env.setdefault("SAFRS_TMP_DB", f"tmp_{framework}_{port}.db")

    cmd = [sys.executable, str(app_path), host, str(port)]
    print("[+] Starting app:")
    print("    " + " ".join(cmd))
    print("[+] Spec base path:")
    print("    %s" % (base_path if base_path else "<empty>",))
    print("[+] Schemathesis URL:")
    print("    %s" % (effective_url,))

    # Ring buffer + optional logfile. Keep this outside of the try/finally so
    # we can always print a useful tail.
    ring = deque(maxlen=max(1, int(args.app_log_lines)))
    log_fp = None
    if args.app_log_file:
        try:
            log_fp = open(str(args.app_log_file), "w", encoding="utf-8", errors="replace")
            print("[+] App log file:")
            print("    %s" % str(args.app_log_file))
        except Exception as e:
            print("[-] Failed to open app log file: %s" % (e,), file=sys.stderr)
            return 2

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=env,
        cwd=str(here),
    )

    log_thread = _start_app_log_drain(proc, ring, bool(args.tee_app_logs), log_fp)

    runtime_spec_path = spec_path
    remove_runtime_spec = False
    try:
        _wait_http_ok("%s/health" % base_url, args.startup_timeout)
        runtime_spec_path, remove_runtime_spec = _prepare_spec_for_run(
            spec_path=spec_path,
            base_url=base_url,
            request_timeout_s=float(args.request_timeout),
        )
        rc = _run_contract_tests(
            spec_path=runtime_spec_path,
            effective_url=effective_url,
            max_examples=args.max_examples,
            request_timeout_s=float(args.request_timeout),
            phases=str(args.phases),
            auth_header=str(args.auth),
            content_type=str(args.content_type),
        )
        return 0 if rc == 0 else 1
    except KeyboardInterrupt:
        return 2
    except Exception as e:
        print("[-] Error: %s" % (e,), file=sys.stderr)
        return 2
    finally:
        try:
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT)
                try:
                    proc.wait(timeout=5)
                except Exception:
                    proc.kill()
        finally:
            if remove_runtime_spec:
                try:
                    runtime_spec_path.unlink(missing_ok=True)
                except Exception:
                    pass
            # Give the log drain thread a moment to read the final lines.
            try:
                log_thread.join(timeout=2.0)
            except Exception:
                pass

            try:
                if log_fp is not None:
                    log_fp.flush()
                    log_fp.close()
            except Exception:
                pass

            if ring:
                print("\n[+] App output (tail):")
                for line in ring:
                    print(line)


if __name__ == "__main__":
    raise SystemExit(main())
