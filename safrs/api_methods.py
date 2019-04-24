"""
api_methods.py
"""
from sqlalchemy import or_
from .jsonapi import SAFRSFormattedResponse, paginate, jsonapi_format_response
from .swagger_doc import documented_api_method, jsonapi_rpc
from .errors import GenericError, ValidationError

# from .safrs_types import SAFRSID


def get_list(self, id_list):
    """
        description: [deprecated] use csv filter[idx] instead
        args:
            id_list:
                - xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
                - xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
    """

    result = []
    for idx in id_list:
        instance = self._s_query.get(idx)
        if idx:
            result.append(instance)

    return result


@documented_api_method
def lookup_re_mysql(cls, **kwargs):
    """
        pageable: True
        description : Regex search all matching objects (works only in MySQL!!!)
        args:
            name: thom.*
    """
    # from .jsonapi import SAFRSFormattedResponse, paginate, jsonapi_format_response

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
            response.response = jsonapi_format_response(
                data, meta, links, errors, count
            )

        except Exception as exc:
            raise GenericError("Failed to execute query {}".format(exc))

    return result.all()


@documented_api_method
def startswith(cls, **kwargs):
    """
        pageable: True
        description : lookup column names
        args:
        name: t
    """
    # from .jsonapi import SAFRSFormattedResponse, paginate, jsonapi_format_response
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
            response.response = jsonapi_format_response(
                data, meta, links, errors, count
            )

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
    result = cls.query.filter(
        or_(column.op("regexp")(query) for column in cls._s_columns)
    )
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
            query: keyword
    """
    query = kwargs.get("query", "")
    response = SAFRSFormattedResponse()
    if ":" in query:
        column_name, value = query.split(":")
        result = cls.query.filter(
            or_(
                column.like("%" + value + "%")
                for column in cls._s_columns
                if column.name == column_name
            )
        )
    else:
        result = cls.query.filter(
            or_(column.like("%" + query + "%") for column in cls._s_columns)
        )
    instances = result
    links, instances, count = paginate(instances)
    data = [item for item in instances]
    meta = {}
    errors = None
    response.response = jsonapi_format_response(data, meta, links, errors, count)
    return response
