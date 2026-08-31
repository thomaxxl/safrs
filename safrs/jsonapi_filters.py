"""
JSON:API filtering strategies
"""
import re
from typing import Any, cast

import sqlalchemy
import safrs
from .jsonapi_attr import is_jsonapi_attr
from sqlalchemy.orm import joinedload

from .jsonapi_context import maybe_jsonapi_context
from .config import get_config
from .errors import ValidationError
from .filtering import (
    apply_filter_read_permissions,
    filter_attribute_names,
    get_filterable_attribute,
    uses_builtin_json_filter,
)

flask_request: Any = None

try:
    from flask import has_request_context, request as _flask_request
except ImportError:  # pragma: no cover
    def has_request_context() -> bool:
        return False
else:
    flask_request = _flask_request


def _get_include_csv(default: str) -> str:
    if has_request_context():
        args = getattr(flask_request, "args", None)
        if args is not None and "include" in args:
            return str(args.get("include", default))
    context = maybe_jsonapi_context()
    if context is None:
        return default
    return context.get_include_csv(default)


def _get_filter_arg() -> str:
    if has_request_context():
        filter_arg = getattr(flask_request, "filter", "")
        if filter_arg:
            return str(filter_arg)
        args = getattr(flask_request, "args", None)
        if args is not None and "filter" in args:
            return str(args.get("filter", ""))
    context = maybe_jsonapi_context()
    if context is None:
        return ""
    return str(getattr(context.query_params, "get", lambda *_args, **_kwargs: "")("filter", "") or "")


def _get_bracket_filters() -> dict[str, str]:
    if has_request_context():
        filters = getattr(flask_request, "filters", None)
        if isinstance(filters, dict) and filters:
            return {str(key): str(value) for key, value in filters.items()}
        query_items = flask_request.args.items()
        flask_filters: dict[str, str] = {}
        for key, value in query_items:
            match = re.search(r"filter\[(\w+)\]", str(key))
            if match:
                flask_filters[match.group(1)] = str(value)
        if flask_filters:
            return flask_filters

    context = maybe_jsonapi_context()
    if context is None:
        return {}
    query_items = context.query_multi_items()

    result: dict[str, str] = {}
    for key, value in query_items:
        match = re.search(r"filter\[(\w+)\]", str(key))
        if match:
            result[match.group(1)] = str(value)
    return result


def _included_paths(cls: Any, included_csv: str) -> list[str]:
    included_list: list[str] = []
    include_names = [include_name.strip() for include_name in included_csv.split(",") if include_name.strip()]
    max_paths_config = get_config("MAX_INCLUDE_PATHS")
    max_include_paths = int(
        max_paths_config if max_paths_config is not None else safrs.SAFRS.MAX_INCLUDE_PATHS
    )
    if max_include_paths > 0 and len(include_names) > max_include_paths:
        raise ValidationError(f"Too many include paths (maximum {max_include_paths})")
    max_depth_config = get_config("MAX_INCLUDE_DEPTH")
    max_include_depth = int(
        max_depth_config if max_depth_config is not None else safrs.SAFRS.MAX_INCLUDE_DEPTH
    )
    for include_name in include_names:
        if include_name == safrs.SAFRS.INCLUDE_ALL:
            included_list.extend(str(rel_name) for rel_name in cls._s_relationships.keys())
            continue
        include_depth = len([segment for segment in include_name.split(".") if segment])
        if max_include_depth > 0 and include_depth > max_include_depth:
            raise ValidationError(f"Include path exceeds maximum depth {max_include_depth}")
        included_list.append(include_name)
    if max_include_paths > 0 and len(included_list) > max_include_paths:
        raise ValidationError(f"Too many include paths (maximum {max_include_paths})")
    return included_list


def create_query(cls: Any) -> Any:
    """
    Create a query for the target collection `cls`.
    If `include=` query parameters are given, the corresponding relationships will be joined loaded if possible
    See: https://docs.sqlalchemy.org/en/13/orm/loading_relationships.html

    :param cls: class (collection) we want to query
    """
    query = cls._s_query

    if not get_config("OPTIMIZED_LOADING"):
        return query
    included_csv = _get_include_csv(str(get_config("DEFAULT_INCLUDED") or ""))
    included_list = _included_paths(cls, included_csv)

    for inc in included_list:
        current_cls = cls
        options = None
        for inc_rel_name in inc.split("."):
            if inc_rel_name == str(get_config("INCLUDE_ALL") or safrs.SAFRS.INCLUDE_ALL):
                continue
            if inc_rel_name not in current_cls._s_relationships:
                safrs.log.warning(f"Invalid relationship : {current_cls}.{inc_rel_name}")
                break
            inc_rel = getattr(current_cls, inc_rel_name)  # == current_cls._s_relationships[inc_rel_name]
            if not hasattr(inc_rel, "lazy") or inc_rel.lazy not in ["select", "joined", "subquery", "selectin"]:
                # we can't set options for lazy_load 'dynamic'/'eager'/'raise' relationships
                # not setting them on 'noload' either
                break
            options = options.joinedload(inc_rel) if options else joinedload(inc_rel)
            current_cls = inc_rel.mapper.class_
        if options:
            query = query.options(options)

    return query


@classmethod  # type: ignore[misc]
def jsonapi_filter(cls: Any) -> Any:
    """
    https://jsonapi.org/recommendations/#filtering
    Apply the request.args filters to the object

    :return: sqla query object
    """

    # First check if a filter= URL query parameter has been used
    # the SAFRSObject should've implemented a filter method or
    # overwritten the _s_filter method to implement custom filtering
    filter_args = _get_filter_arg()
    if filter_args:
        safrs_object_filter = getattr(cls, "filter", None)
        if isinstance(cls, (list, sqlalchemy.orm.collections.InstrumentedList)):
            # not implemented
            result = cls
        elif callable(safrs_object_filter):
            # pylint: disable=not-callable
            result = safrs_object_filter(filter_args)
        else:
            result = cls._s_filter(filter_args)
            if uses_builtin_json_filter(cls):
                result = apply_filter_read_permissions(cls, result, filter_attribute_names(filter_args))
        return result

    expressions: list[tuple[Any, Any]] = []
    filters = _get_bracket_filters()
    if isinstance(cls, (list, sqlalchemy.orm.collections.InstrumentedList)):
        safrs.log.debug(f"Filtering not implemented for {cls}")
        return cls

    for attr_name, val in filters.items():
        if attr_name == "id":
            if get_filterable_attribute(cls, attr_name) is None:
                safrs.log.warning(f"Invalid filter {attr_name}")
                return []
            attr = getattr(cls, "id", None)
            if attr is None:
                # todo!!: add support for composite pkeys using `cls.id_type.get_pks`
                if "," in val:
                    if len(cls.id_type.column_names) > 1:
                        safrs.log.warning(f'Csv search not implemented for non-default composite "id" types: {val}')
                        return []
                    attr_name = cls.id_type.column_names[0]
                    attr = getattr(cls, attr_name, None)
                else:
                    return cls._s_get_instance_by_id(val)
        else:
            attr = get_filterable_attribute(cls, attr_name)
        if attr is None:
            # validation failed: this attribute can't be queried
            safrs.log.warning(f"Invalid filter {attr_name}")
            return []
        if is_jsonapi_attr(attr):
            # to do
            safrs.log.debug(f"Filtering not implemented for {attr}")
        else:
            expressions.append((attr, val))

    result_query = create_query(cls)
    if expressions:
        _expressions = []
        for column, val in expressions:
            if hasattr(column, "in_"):
                _expressions.append(cast(Any, column).in_(val.split(",")))
            else:
                safrs.log.warning(f"'{cls}.{column}' is not a column ({type(column)})")
        result_query = result_query.filter(*_expressions)
    return apply_filter_read_permissions(cls, result_query, filters.keys())


@classmethod  # type: ignore[misc]
def get_swagger_filters(cls: Any) -> Any:
    """
    :return: JSON:API filters swagger spec
    create the filter[] swagger doc for all jsonapi attributes + the id

    the columns may have attributes defined that are used for custom formatting:
    - description
    - filterable
    - type
    - format
    """
    attr_list = list(cls.SAFRSObject._s_jsonapi_attrs.keys()) + ["id"]

    for attr_name in attr_list:
        # (Customizable swagger specs):
        default_filter = ""
        description = f"{attr_name} attribute filter (csv)"
        swagger_type = "string"
        swagger_format = "string"
        name_format = "filter[{}]"
        required = False

        column = getattr(cls.SAFRSObject, "_s_column_dict", {}).get(attr_name, None)
        if column is not None:
            if not getattr(column, "filterable", True):
                continue
            description = getattr(column, "description", description)
            swagger_type = getattr(column, "swagger_type", swagger_type)
            swagger_format = getattr(column, "format", swagger_format)
            name_format = getattr(column, "name_format", name_format)
            required = getattr(column, "required", required)
            default_filter = getattr(column, "default_filter", default_filter)

        param = {
            "default": default_filter,
            "type": swagger_type,
            "name": name_format.format(attr_name),
            "in": "query",
            "format": swagger_format,
            "required": required,
            "description": description,
        }
        yield param

    yield {
        "default": "",
        "type": "string",
        "name": "filter",
        "in": "query",
        "format": "string",
        "required": False,
        "description": f"Custom {cls.SAFRSObject._s_class_name} filter",
    }


class FilteringStrategy:
    def __init__(self: Any, jsonapi_filter: Any=jsonapi_filter, swagger_gen: Any=get_swagger_filters) -> None:
        self.jsonapi_filter = jsonapi_filter
        self.swagger_gen = swagger_gen
