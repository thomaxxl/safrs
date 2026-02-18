# -*- coding: utf-8 -*-

from typing import Any, Dict, Optional, Tuple, Type, cast

from pydantic import ConfigDict, Field, create_model

from .jsonapi_primitives import PermissiveModel


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
    return py_type


def _jsonapi_attr_return_type(Model: Type[Any], attr_name: str) -> Any:
    model_attr = getattr(Model, attr_name, None)
    if model_attr is None:
        return Any
    if hasattr(model_attr, "fget") and callable(getattr(model_attr, "fget", None)):
        annotations = getattr(model_attr.fget, "__annotations__", {})
        return annotations.get("return", Any)
    annotations = getattr(model_attr, "__annotations__", {})
    return annotations.get("return", Any)


def _attribute_type(Model: Type[Any], attr_name: str, column_or_attr: Any) -> Any:
    if hasattr(column_or_attr, "type"):
        return _safe_python_type(column_or_attr)
    return _jsonapi_attr_return_type(Model, attr_name)


def _field_definitions(Model: Type[Any]) -> Dict[str, Tuple[Any, Any]]:
    fields: Dict[str, Tuple[Any, Any]] = {}
    attrs = getattr(Model, "_s_jsonapi_attrs", {})
    for attr_name, column_or_attr in attrs.items():
        py_type = _attribute_type(Model, attr_name, column_or_attr)
        fields[attr_name] = (Optional[py_type], None)
    return fields


def _sample_example(Model: Type[Any]) -> Optional[Dict[str, Any]]:
    sample_factory = getattr(Model, "_s_sample_dict", None)
    if not callable(sample_factory):
        return None
    try:
        sample = sample_factory()
    except Exception:
        return None
    if isinstance(sample, dict):
        return sample
    return None


def create_attributes_model(Model: Type[Any], model_name: str) -> Type[PermissiveModel]:
    fields = _field_definitions(Model)
    model = cast(
        Type[PermissiveModel],
        create_model(model_name, __base__=PermissiveModel, **cast(Any, fields)),
    )
    sample = _sample_example(Model)
    if sample is not None:
        model.model_config = ConfigDict(
            extra="allow",
            json_schema_extra={"examples": [sample]},
        )
        model.model_rebuild(force=True)
    return model
