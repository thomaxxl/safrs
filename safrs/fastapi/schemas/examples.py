# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any, Dict, Optional, Type

import safrs
from fastapi.encoders import jsonable_encoder
from safrs.jsonapi_attr import is_jsonapi_attr


def _json_safe(value: Any) -> Any:
    return jsonable_encoder(value)


def _writable_attribute_names(Model: Type[Any]) -> set[str]:
    attrs = getattr(Model, "_s_jsonapi_attrs", {})
    writable: set[str] = set()
    for attr_name, column_or_attr in attrs.items():
        if not is_jsonapi_attr(column_or_attr) or callable(getattr(column_or_attr, "fset", None)):
            writable.add(attr_name)
    return writable


def attributes_example(Model: Type[Any], *, writable_only: bool = False) -> Dict[str, Any]:
    sample_factory = getattr(Model, "_s_sample_dict", None)
    if callable(sample_factory):
        try:
            sample = sample_factory()
            if isinstance(sample, dict):
                if writable_only:
                    writable = _writable_attribute_names(Model)
                    sample = {key: value for key, value in sample.items() if key in writable}
                return _json_safe(sample) or {}
        except Exception as exc:
            safrs.log.debug("Failed to build attributes example for %s: %s", getattr(Model, "__name__", Model), exc)
    return {}


def resource_identifier_example(Model: Type[Any]) -> Dict[str, str]:
    sample_id_factory = getattr(Model, "_s_sample_id", None)
    sample_id: Any = "0"
    if callable(sample_id_factory):
        try:
            generated = sample_id_factory()
            if generated is not None:
                sample_id = generated
        except Exception as exc:
            safrs.log.debug("Failed to build sample id for %s: %s", getattr(Model, "__name__", Model), exc)
    json_safe_id = _json_safe(sample_id)
    return {
        "type": str(getattr(Model, "_s_type", getattr(Model, "__name__", "Resource"))),
        "id": str(json_safe_id),
    }


def create_document_example(Model: Type[Any]) -> Dict[str, Any]:
    rid = resource_identifier_example(Model)
    data: Dict[str, Any] = {
        "type": rid["type"],
        "attributes": attributes_example(Model, writable_only=True),
    }
    if bool(getattr(Model, "allow_client_generated_ids", False)):
        data["id"] = rid["id"]
    return {"data": data}


def patch_document_example(Model: Type[Any]) -> Dict[str, Any]:
    rid = resource_identifier_example(Model)
    return {
        "data": {
            "type": rid["type"],
            "id": rid["id"],
            "attributes": attributes_example(Model, writable_only=True),
        }
    }


def relationship_to_one_example(TargetModel: Type[Any]) -> Dict[str, Optional[Dict[str, str]]]:
    return {"data": resource_identifier_example(TargetModel)}


def relationship_to_many_example(TargetModel: Type[Any]) -> Dict[str, Any]:
    return {"data": [resource_identifier_example(TargetModel)]}


# Backward-compatible aliases
relationship_document_to_one_example = relationship_to_one_example
relationship_document_to_many_example = relationship_to_many_example
