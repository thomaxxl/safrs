"""
JSON:API filtering strategies
"""
from typing import Any, cast

import sqlalchemy
import safrs
from sqlalchemy.orm import joinedload

from .jsonapi_context import maybe_jsonapi_context
from .config import get_config
from .errors import ValidationError
from .filtering import (
    apply_filter_read_permissions,
    bracket_filter_expression,
    coerce_filter_values,
    custom_filter_read_fields,
    filter_attribute_names,
    parse_bracket_filter_name,
    require_filterable_attribute,
    uses_builtin_json_filter,
    validate_bracket_filter_count,
    validate_filter_result,
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
        filter_error = getattr(flask_request, "filter_validation_error", "")
        if filter_error:
            raise ValidationError(str(filter_error).removeprefix("Validation Error: "))
        filters = getattr(flask_request, "filters", None)
        if isinstance(filters, dict) and filters:
            request_filters = {str(key): str(value) for key, value in filters.items()}
            validate_bracket_filter_count(request_filters)
            return request_filters
        query_items = flask_request.args.items()
        flask_filters: dict[str, str] = {}
        for key, value in query_items:
            attr_name = parse_bracket_filter_name(key)
            if attr_name is not None:
                flask_filters[attr_name] = str(value)
        if flask_filters:
            validate_bracket_filter_count(flask_filters)
            return flask_filters

    context = maybe_jsonapi_context()
    if context is None:
        return {}
    query_items = context.query_multi_items()

    result: dict[str, str] = {}
    for key, value in query_items:
        attr_name = parse_bracket_filter_name(key)
        if attr_name is not None:
            result[attr_name] = str(value)
    validate_bracket_filter_count(result)
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
            # Loader configuration lives on RelationshipProperty, not the
            # class's InstrumentedAttribute. Inspecting inc_rel.lazy silently
            # skipped eager loading for real mapped models.
            relationship = current_cls._s_relationships[inc_rel_name]
            if relationship.lazy not in ["select", "joined", "subquery", "selectin"]:
                # we can't set options for lazy_load 'dynamic'/'eager'/'raise' relationships
                # not setting them on 'noload' either
                break
            options = options.joinedload(inc_rel) if options else joinedload(inc_rel)
            current_cls = relationship.mapper.class_
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
            declared_fields = custom_filter_read_fields(cls, safrs_object_filter)
            result = safrs_object_filter(filter_args)
            result = apply_filter_read_permissions(cls, result, declared_fields)
        else:
            custom_filter = cls._s_filter
            declared_fields = (
                () if uses_builtin_json_filter(cls) else custom_filter_read_fields(cls, custom_filter)
            )
            result = custom_filter(filter_args)
            if uses_builtin_json_filter(cls):
                result = apply_filter_read_permissions(cls, result, filter_attribute_names(filter_args))
            else:
                result = apply_filter_read_permissions(cls, result, declared_fields)
        return validate_filter_result(result)

    expressions: list[tuple[Any, Any]] = []
    filters = _get_bracket_filters()
    if isinstance(cls, (list, sqlalchemy.orm.collections.InstrumentedList)):
        safrs.log.debug(f"Filtering not implemented for {cls}")
        return cls

    for attr_name, val in filters.items():
        attr = require_filterable_attribute(cls, attr_name)
        expressions.append((attr, coerce_filter_values(attr, val, attr_name)))

    result_query = create_query(cls)
    if expressions:
        _expressions = []
        for column, values in expressions:
            attr_name = str(getattr(column, "key", getattr(column, "name", "<unknown>")))
            _expressions.append(bracket_filter_expression(cast(Any, column), values, attr_name))
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
