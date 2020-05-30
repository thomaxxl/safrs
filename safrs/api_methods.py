"""
.. api_methods::
"""
from sqlalchemy import or_
import safrs
from .jsonapi import SAFRSFormattedResponse, paginate, jsonapi_format_response, jsonapi_sort
from .swagger_doc import jsonapi_rpc
from .errors import GenericError, ValidationError


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
        result = cls.query.filter(or_(column.like("%" + value + "%") for column in cls._s_columns if column.name == column_name))
    else:
        result = cls.query.filter(or_(column.like("%" + query + "%") for column in cls._s_columns))
    instances = jsonapi_sort(result, cls)
    links, instances, count = paginate(instances)
    data = [item for item in instances]
    meta = {}
    errors = None
    response.response = jsonapi_format_response(data, meta, links, errors, count)
    return response


@jsonapi_rpc(http_methods=["POST"])
def duplicate(self):
    """
        description: Duplicate an object - copy it and give it a new id
    """
    from sqlalchemy.orm.session import make_transient

    session = safrs.DB.session
    session.expunge(self)
    make_transient(self)
    self.id = self.id_type()
    session.add(self)
    session.commit()
    response = SAFRSFormattedResponse(self)
    return response


@classmethod
@jsonapi_rpc(http_methods=["POST"])
def lookup_re_mysql(cls, **kwargs):
    """
        pageable: True
        description : Regex search all matching objects (works only in MySQL!!!)
        args:
            name: thom.*
    """
    result = cls
    for key, value in kwargs.items():
        column = getattr(cls, key, None)
        if not column:
            raise ValidationError('Invalid Column "{}"'.format(key))
        try:
            result = result.query.filter(column.op("regexp")(value))

        except Exception as exc:
            raise GenericError("Failed to execute query {}".format(exc))

    return SAFRSFormattedResponse(result.all())


@classmethod
@jsonapi_rpc(http_methods=["POST"])
def startswith(cls, **kwargs):
    """
        pageable: True
        summary : lookup items where specified attributes starts with the argument string
        args:
            attr_name: value
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
