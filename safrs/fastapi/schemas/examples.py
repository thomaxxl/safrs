# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any, Dict, Optional, Type

from fastapi.encoders import jsonable_encoder


def _json_safe(value: Any) -> Any:
    return jsonable_encoder(value)


def attributes_example(Model: Type[Any]) -> Dict[str, Any]:
    sample_factory = getattr(Model, "_s_sample_dict", None)
    if callable(sample_factory):
        try:
            sample = sample_factory()
            if isinstance(sample, dict):
                return _json_safe(sample) or {}
        except Exception:
            pass
    return {}


def resource_identifier_example(Model: Type[Any]) -> Dict[str, str]:
    sample_id_factory = getattr(Model, "_s_sample_id", None)
    sample_id: Any = "0"
    if callable(sample_id_factory):
        try:
            generated = sample_id_factory()
            if generated is not None:
                sample_id = generated
        except Exception:
            pass
    json_safe_id = _json_safe(sample_id)
    return {
        "type": str(getattr(Model, "_s_type", getattr(Model, "__name__", "Resource"))),
        "id": str(json_safe_id),
    }


def create_document_example(Model: Type[Any]) -> Dict[str, Any]:
    rid = resource_identifier_example(Model)
    data: Dict[str, Any] = {
        "type": rid["type"],
        "attributes": attributes_example(Model),
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
            "attributes": attributes_example(Model),
        }
    }


def relationship_to_one_example(TargetModel: Type[Any]) -> Dict[str, Optional[Dict[str, str]]]:
    return {"data": resource_identifier_example(TargetModel)}


def relationship_to_many_example(TargetModel: Type[Any]) -> Dict[str, Any]:
    return {"data": [resource_identifier_example(TargetModel)]}


# Backward-compatible aliases
relationship_document_to_one_example = relationship_to_one_example
relationship_document_to_many_example = relationship_to_many_example
