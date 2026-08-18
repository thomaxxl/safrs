# -*- coding: utf-8 -*-

import decimal
from typing import Any, Dict, Optional, Tuple, Type, cast

from fastapi.encoders import jsonable_encoder
from pydantic import ConfigDict, Field, create_model

from safrs.jsonapi_attr import is_jsonapi_attr, jsonapi_attr_is_read_only, jsonapi_attr_is_write_only
from .jsonapi_primitives import PermissiveModel

_SWAGGER_TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
}


def _normalize_python_type(py_type: Any) -> Any:
    if py_type is decimal.Decimal:
        return float
    return py_type


def _safe_python_type(column_or_attr: Any) -> Any:
    col_type = getattr(column_or_attr, "type", None)
    if col_type is None:
        return Any
    try:
        py_type = getattr(col_type, "python_type", Any)
    except NotImplementedError:
        return Any
    except Exception:
        return Any
    if py_type is None:
        return Any
    return _normalize_python_type(py_type)


def _jsonapi_attr_return_type(Model: Type[Any], attr_name: str) -> Any:
    model_attr = getattr(Model, attr_name, None)
    if model_attr is None:
        return Any
    if hasattr(model_attr, "fget") and callable(getattr(model_attr, "fget", None)):
        annotations = getattr(model_attr.fget, "__annotations__", {})
        annotated = annotations.get("return", Any)
        if isinstance(annotated, str):
            annotated = Any
        if annotated is not Any:
            return _normalize_python_type(annotated)
    elif hasattr(model_attr, "__annotations__"):
        annotations = getattr(model_attr, "__annotations__", {})
        annotated = annotations.get("return", Any)
        if isinstance(annotated, str):
            annotated = Any
        if annotated is not Any:
            return _normalize_python_type(annotated)
    swagger_type = str(getattr(model_attr, "swagger_type", "")).strip().lower()
    return _SWAGGER_TYPE_MAP.get(swagger_type, Any)


def _attribute_type(Model: Type[Any], attr_name: str, column_or_attr: Any) -> Any:
    if hasattr(column_or_attr, "type"):
        return _safe_python_type(column_or_attr)
    return _jsonapi_attr_return_type(Model, attr_name)


def _is_writable_attribute(column_or_attr: Any) -> bool:
    if not is_jsonapi_attr(column_or_attr):
        return True
    return not jsonapi_attr_is_read_only(column_or_attr)

def _attribute_field_info(column_or_attr: Any, *, writable_only: bool = False) -> Any:
    if not is_jsonapi_attr(column_or_attr):
        return None
    default = getattr(column_or_attr, "default", None)
    description = getattr(column_or_attr, "description", None)
    swagger_format = getattr(column_or_attr, "swagger_format", None)
    json_schema_extra: Dict[str, Any] = {}
    if swagger_format:
        json_schema_extra["format"] = swagger_format
    if writable_only and jsonapi_attr_is_write_only(column_or_attr):
        json_schema_extra["writeOnly"] = True
    if not writable_only and jsonapi_attr_is_read_only(column_or_attr):
        json_schema_extra["readOnly"] = True
    if json_schema_extra:
        return Field(default=default, description=description, json_schema_extra=json_schema_extra)
    if description is not None or default is not None:
        return Field(default=default, description=description)
    return None


def _field_definitions(Model: Type[Any], *, writable_only: bool = False) -> Dict[str, Tuple[Any, Any]]:
    fields: Dict[str, Tuple[Any, Any]] = {}
    attrs = getattr(Model, "_s_jsonapi_writable_attrs", None) if writable_only else None
    if attrs is None:
        attrs = getattr(Model, "_s_jsonapi_attrs", {})
    for attr_name, column_or_attr in attrs.items():
        if writable_only and not _is_writable_attribute(column_or_attr):
            continue
        if not writable_only and jsonapi_attr_is_write_only(column_or_attr):
            continue
        py_type = _attribute_type(Model, attr_name, column_or_attr)
        fields[attr_name] = (Optional[py_type], _attribute_field_info(column_or_attr, writable_only=writable_only))
    return fields


def _sample_example(Model: Type[Any], *, writable_only: bool = False) -> Optional[Dict[str, Any]]:
    sample_factory = getattr(Model, "_s_sample_dict", None)
    if not callable(sample_factory):
        return None
    try:
        sample = sample_factory()
    except Exception:
        return None
    if isinstance(sample, dict):
        allowed = set(_field_definitions(Model, writable_only=writable_only))
        filtered = {key: value for key, value in sample.items() if key in allowed}
        return cast(Dict[str, Any], jsonable_encoder(filtered))
    return None


def create_attributes_model(
    Model: Type[Any],
    model_name: str,
    *,
    writable_only: bool = False,
) -> Type[PermissiveModel]:
    fields = _field_definitions(Model, writable_only=writable_only)
    model = cast(
        Type[PermissiveModel],
        create_model(model_name, __base__=PermissiveModel, **cast(Any, fields)),
    )
    sample = _sample_example(Model, writable_only=writable_only)
    if sample is not None:
        model.model_config = ConfigDict(
            extra="allow",
            json_schema_extra={"examples": [sample]},
        )
        model.model_rebuild(force=True)
    return model
