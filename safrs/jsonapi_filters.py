"""
JSON:API filtering strategy
"""
import operator
import re

from .config import get_request_param
import sqlalchemy
import safrs
from .jsonapi_attr import is_jsonapi_attr


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

    if expressions:
        _expressions = []
        for column, val in expressions:
            pat1 = r"(?P<op1>[\>\<\=]+)(?P<val1>.+)(?P<bop1>(and)|(or))(?P<op2>[\>\<\=]+)(?P<val2>.+)"
            pat2 = r"(?P<op1>[\>\<\=]+)(?P<val1>.+)"
            op = {'<': operator.lt, '<=': operator.le, '>': operator.gt, '>=': operator.ge}
            try:
                m = re.match(pat1, val).groupdict()
                op_ = sqlalchemy.or_ if m['bop1'].lower() == 'or' else sqlalchemy.and_
                _expressions.append(op_(op[m['op1']](column, m['val1']), op[m['op2']](column, m['val2'])))
                continue
            except Exception as e:
                pass
            try:
                m = re.match(pat2, val).groupdict()
                _expressions.append(op[m['op1']](column, m['val1']))
                continue
            except Exception as e:
                pass

            if hasattr(column, "in_"):
                _expressions.append(column.in_(val.split(",")))
            else:
                safrs.log.warning("'{}.{}' is not a column ({})".format(cls, column, type(column)))
        result = cls._s_query.filter(*_expressions)
    else:
        result = cls._s_query

    return result
