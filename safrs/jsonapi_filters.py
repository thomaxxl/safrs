"""
JSON:API filtering strategies
"""
from .config import get_request_param
import sqlalchemy
import safrs
from .jsonapi_attr import is_jsonapi_attr
from flask import request
from sqlalchemy.orm import joinedload


def create_query(cls):
    """
    Create a query for the target collection `cls`.
    If `include=` query parameters are given, the corresponding relationships will be joined loaded if possible
    See: https://docs.sqlalchemy.org/en/13/orm/loading_relationships.html

    :param cls: class (collection) we want to query
    """
    query = cls._s_query

    if not safrs.SAFRS.OPTIMIZED_LOADING:
        return query
    included_csv = request.args.get("include", safrs.SAFRS.DEFAULT_INCLUDED)
    included_list = [inc for inc in included_csv.split(",") if inc]

    for inc in included_list:
        current_cls = cls
        options = None
        for inc_rel_name in inc.split("."):
            if inc_rel_name not in current_cls._s_relationships:
                safrs.log.error("Invalid relationship : {}.{}".format(current_cls, inc_rel_name))
                break
            inc_rel = getattr(current_cls, inc_rel_name)
            if current_cls._s_relationships[inc_rel_name].lazy not in ["select", "joined", "subquery", "selectin"]:
                # we can't set options for lazy_load 'dynamic'/'eager'/'raise' relationships
                # not setting them on 'noload' either
                break
            options = options.joinedload(inc_rel) if options else joinedload(inc_rel)
            current_cls = inc_rel.mapper.class_
        if options:
            query = query.options(options)

    return query


@classmethod
def jsonapi_filter(cls):
    """
    https://jsonapi.org/recommendations/#filtering
    Apply the request.args filters to the object

    :return: sqla query object
    """

    # First check if a filter= URL query parameter has been used
    # the SAFRSObject should've implemented a filter method or
    # overwritten the _s_filter method to implement custom filtering
    filter_args = get_request_param("filter")
    if filter_args:
        safrs_object_filter = getattr(cls, "filter", None)
        if isinstance(cls, (list, sqlalchemy.orm.collections.InstrumentedList)):
            # not implemented
            result = cls
        elif callable(safrs_object_filter):
            result = safrs_object_filter(filter_args)
        else:
            result = cls._s_filter(filter_args)
        return result

    expressions = []
    filters = get_request_param("filters", {})
    if isinstance(cls, (list, sqlalchemy.orm.collections.InstrumentedList)):
        safrs.log.debug("Filtering not implemented for {}".format(cls))
        return cls

    for attr_name, val in filters.items():
        if attr_name == "id":
            return cls._s_get_instance_by_id(val)
        if attr_name not in cls._s_jsonapi_attrs:
            # validation failed: this attribute can't be queried
            safrs.log.warning("Invalid filter {}".format(attr_name))
            return []
        else:
            attr = cls._s_jsonapi_attrs[attr_name]
        if is_jsonapi_attr(attr):
            # to do
            safrs.log.debug("Filtering not implemented for {}".format(attr))
        else:
            expressions.append((attr, val))

    result_query = create_query(cls)
    if expressions:
        _expressions = []
        for column, val in expressions:
            if hasattr(column, "in_"):
                _expressions.append(column.in_(val.split(",")))
            else:
                safrs.log.warning("'{}.{}' is not a column ({})".format(cls, column, type(column)))
        result_query = result_query.filter(*_expressions)

    return result_query


@classmethod
def get_swagger_filters(cls):
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
        description = "{} attribute filter (csv)".format(attr_name)
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
        "description": "Custom {} filter".format(cls.SAFRSObject._s_class_name),
    }

class FilteringStrategy:
    def __init__(self, jsonapi_filter=jsonapi_filter, swagger_gen=get_swagger_filters):
        self.jsonapi_filter = jsonapi_filter
        self.swagger_gen = swagger_gen
