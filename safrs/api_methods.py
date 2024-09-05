from typing import Any, Dict
from sqlalchemy import or_
from sqlalchemy.orm.session import make_transient
import safrs
from .jsonapi import paginate, jsonapi_sort
from .json_encoder import SAFRSFormattedResponse
from .swagger_doc import jsonapi_rpc
from .errors import GenericError, SystemValidationError


@jsonapi_rpc(http_methods=["POST"])
def duplicate(self: Any) -> SAFRSFormattedResponse:
    """
    description: Duplicate an object - copy it and give it a new id
    """
    session = safrs.DB.session
    session.expunge(self)
    make_transient(self)
    self.id = self.id_type()
    session.add(self)
    session.commit()
    return SAFRSFormattedResponse(self)


@classmethod
@jsonapi_rpc(http_methods=["POST"])
def lookup_re_mysql(cls: Any, **kwargs: Dict[str, str]) -> SAFRSFormattedResponse:  # pragma: no cover
    """
    pageable: True
    description: Regex search all matching objects (works only in MySQL!!!)
    args:
        name: thom.*
    """
    result = cls
    for key, value in kwargs.items():
        column = getattr(cls, key, None)
        if not column:
            raise SystemValidationError(f'Invalid Column "{key}"')
        try:
            result = result.query.filter(column.op("regexp")(value))
        except Exception as exc:
            raise GenericError(f"Failed to execute query {exc}")

    return SAFRSFormattedResponse(result.all())


@classmethod
@jsonapi_rpc(http_methods=["POST"])
def startswith(cls: Any, **kwargs: Dict[str, str]) -> SAFRSFormattedResponse:  # pragma: no cover
    """
    pageable: True
    summary: Lookup items where specified attributes start with the argument string
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
        response = SAFRSFormattedResponse(data, meta, links, errors, count)
    except Exception as exc:
        raise GenericError(f"Failed to execute query {exc}")

    for key, value in kwargs.items():
        column = getattr(cls, key, None)
        if not column:
            raise SystemValidationError(f'Invalid Column "{key}"')
        try:
            instances = result.query.filter(column.like(value + "%"))
            links, instances, count = paginate(instances)
            data = [item for item in instances]
            meta = {}
            errors = None
            response = SAFRSFormattedResponse(data, meta, links, errors, count)
        except Exception as exc:
            raise GenericError(f"Failed to execute query {exc}")
    return response


@classmethod
@jsonapi_rpc(http_methods=["POST"])
def search(cls: Any, **kwargs: Dict[str, str]) -> SAFRSFormattedResponse:  # pragma: no cover
    """
    pageable: True
    description: Lookup column names
    args:
        query: val
    """
    query = kwargs.get("query", "")
    columns = [c for c in cls._s_columns if c.type.python_type in [str, int, float]]
    if ":" in query:
        column_name, value = query.split(":")
        result = cls.query.filter(or_(column.like("%" + value + "%") for column in columns if column.name == column_name))
    else:
        result = cls.query.filter(or_(column.like("%" + query + "%") for column in columns))
    instances = jsonapi_sort(result, cls)
    links, instances, count = paginate(instances)
    data = [item for item in instances]
    meta = {}
    errors = None
    return SAFRSFormattedResponse(data, meta, links, errors, count)


@classmethod
@jsonapi_rpc(http_methods=["POST"])
def re_search(cls: Any, **kwargs: Dict[str, str]) -> SAFRSFormattedResponse:  # pragma: no cover
    """
    pageable: True
    description: Lookup column names
    args:
        query: search.*all
    """
    query = kwargs.get("query", "")
    result = cls.query.filter(or_(column.op("regexp")(query) for column in cls._s_columns))
    instances = result
    links, instances, count = paginate(instances)
    data = [item for item in instances]
    meta = {}
    errors = None
    return SAFRSFormattedResponse(data, meta, links, errors, count)
