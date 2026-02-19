# -*- coding: utf-8 -*-

from typing import Any, Dict, Optional, Type

from fastapi.encoders import jsonable_encoder


def _sample_id(Model: Type[Any]) -> str:
    sample_id_factory = getattr(Model, "_s_sample_id", None)
    if callable(sample_id_factory):
        try:
            sample_id = sample_id_factory()
            if sample_id is not None:
                return str(sample_id)
        except Exception:
            pass
    return "0"


def _sample_attributes(Model: Type[Any]) -> Dict[str, Any]:
    sample_factory = getattr(Model, "_s_sample_dict", None)
    if callable(sample_factory):
        try:
            sample = sample_factory()
            if isinstance(sample, dict):
                return jsonable_encoder(sample)
        except Exception:
            pass
    return {}


def create_document_example(Model: Type[Any]) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "type": str(getattr(Model, "_s_type", getattr(Model, "__name__", "Resource"))),
        "attributes": _sample_attributes(Model),
    }
    if bool(getattr(Model, "_s_allow_client_generated_ids", False)):
        data["id"] = _sample_id(Model)
    return {"data": data}


def patch_document_example(Model: Type[Any]) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "type": str(getattr(Model, "_s_type", getattr(Model, "__name__", "Resource"))),
        "id": _sample_id(Model),
        "attributes": _sample_attributes(Model),
    }
    return {"data": data}


def resource_identifier_example(Model: Type[Any]) -> Dict[str, str]:
    return {
        "type": str(getattr(Model, "_s_type", getattr(Model, "__name__", "Resource"))),
        "id": _sample_id(Model),
    }


def relationship_document_to_one_example(TargetModel: Type[Any]) -> Dict[str, Optional[Dict[str, str]]]:
    return {"data": resource_identifier_example(TargetModel)}


def relationship_document_to_many_example(TargetModel: Type[Any]) -> Dict[str, Any]:
    return {"data": [resource_identifier_example(TargetModel)]}
