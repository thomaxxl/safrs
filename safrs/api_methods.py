"""
.. api_methods::
"""
from sqlalchemy import or_
from .jsonapi import SAFRSFormattedResponse, paginate, jsonapi_format_response
from .swagger_doc import jsonapi_rpc
from .errors import GenericError, ValidationError

@classmethod
@jsonapi_rpc(http_methods=['POST'])
def lookup_re_mysql(cls, **kwargs):
    """
        pageable: True
        description : Regex search all matching objects (works only in MySQL!!!)
        args:
            name: thom.*
    """
    result = cls
    response = SAFRSFormattedResponse()
    for key, value in kwargs.items():
        column = getattr(cls, key, None)
        if not column:
            raise ValidationError('Invalid Column "{}"'.format(key))
        try:
            result = result.query.filter(column.op("regexp")(value))
            instances = result
            links, instances, count = paginate(instances)
            data = [item for item in instances]
            meta = {}
            errors = None
            response.response = jsonapi_format_response(data, meta, links, errors, count)

        except Exception as exc:
            raise GenericError("Failed to execute query {}".format(exc))

    return result.all()

@classmethod
@jsonapi_rpc(http_methods=['POST'])
def startswith(cls, **kwargs):
    """
        pageable: True
        description : lookup column names
        
    """
    result = cls
    response = SAFRSFormattedResponse()
    try:
        instances = result.query
        links, instances, count = paginate(instances)
        data = [item for item in instances]
        meta = {}
        errors = None
        response.response = jsonapi_format_response(data, meta, links, errors, count)
    except Exception as exc:
        raise GenericError("Failed to execute query {}".format(exc))

    for key, value in kwargs.items():
        column = getattr(cls, key, None)
        if not column:
            raise ValidationError('Invalid Column "{}"'.format(key))
        try:
            instances = result.query.filter(column.like(value + "%"))
            links, instances, count = paginate(instances)
            data = [item for item in instances]
            meta = {}
            errors = None
            response.response = jsonapi_format_response(data, meta, links, errors, count)

        except Exception as exc:
            raise GenericError("Failed to execute query {}".format(exc))
    return response


@classmethod
@jsonapi_rpc(http_methods=["POST"])
def re_search(cls, **kwargs):
    """
        pageable: True
        description : lookup column names
        args:
            query: search.*all
    """
    query = kwargs.get("query", "")
    response = SAFRSFormattedResponse()
    result = cls.query.filter(or_(column.op("regexp")(query) for column in cls._s_columns))
    instances = result
    links, instances, count = paginate(instances)
    data = [item for item in instances]
    meta = {}
    errors = None
    response.response = jsonapi_format_response(data, meta, links, errors, count)
    return response


@classmethod
@jsonapi_rpc(http_methods=["POST"])
def search(cls, **kwargs):
    """
        pageable: True
        description : lookup column names
        args:
            col_name: value
    """
    query = kwargs.get("query", "")
    response = SAFRSFormattedResponse()
    if ":" in query:
        column_name, value = query.split(":")
        result = cls.query.filter(
            or_(column.like("%" + value + "%") for column in cls._s_columns if column.name == column_name)
        )
    else:
        result = cls.query.filter(or_(column.like("%" + query + "%") for column in cls._s_columns))
    instances = result
    links, instances, count = paginate(instances)
    data = [item for item in instances]
    meta = {}
    errors = None
    response.response = jsonapi_format_response(data, meta, links, errors, count)
    return response
