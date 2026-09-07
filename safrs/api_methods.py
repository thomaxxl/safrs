from typing import Any
from sqlalchemy import or_
from sqlalchemy.orm.session import make_transient
import safrs
from .runtime import get_db
from . import tx
from .jsonapi_formatting import paginate, jsonapi_sort
from .json_encoder import SAFRSFormattedResponse
from .api_doc import jsonapi_rpc
from .errors import GenericError, SystemValidationError
from .filtering import apply_filter_read_permissions, get_filterable_attribute


def _filter_column(cls: Any, key: str) -> Any:
    """Resolve RPC filter fields through the same read policy as HTTP filters."""

    column = get_filterable_attribute(cls, key)
    if column is None:
        raise SystemValidationError(f'Invalid Column "{key}"')
    return column


@jsonapi_rpc(http_methods=["POST"])
def duplicate(self: Any) -> SAFRSFormattedResponse:
    """
    description: Duplicate an object - copy it and give it a new id
    """
    session = get_db().session
    session.expunge(self)
    make_transient(self)
    self.id = self.id_type()
    session.add(self)
    tx.note_write(self.__class__)
    session_info = getattr(session, "info", None)
    in_uow = bool(tx.in_request() or (isinstance(session_info, dict) and session_info.get("_safrs_uow_active", False)))
    if in_uow:
        session.flush()
    return SAFRSFormattedResponse(self)


@classmethod  # type: ignore[misc]
@jsonapi_rpc(http_methods=["POST"])
def lookup_re_mysql(cls: Any, **kwargs: str) -> SAFRSFormattedResponse:  # pragma: no cover
    """
    pageable: True
    description: Regex search all matching objects (works only in MySQL!!!)
    args:
        name: thom.*
    """
    result = cls.query
    for key, value in kwargs.items():
        column = _filter_column(cls, key)
        try:
            result = result.filter(column.op("regexp")(value))
        except Exception as exc:
            raise GenericError("Failed to execute query") from exc

    instances = apply_filter_read_permissions(cls, result, kwargs.keys())
    if hasattr(instances, "all") and callable(instances.all):
        instances = instances.all()
    return SAFRSFormattedResponse(instances)


@classmethod  # type: ignore[misc]
@jsonapi_rpc(http_methods=["POST"])
def startswith(cls: Any, **kwargs: str) -> SAFRSFormattedResponse:  # pragma: no cover
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
        instances = apply_filter_read_permissions(cls, instances, ())
        links, instances, count = paginate(instances)
        data = [item for item in instances]
        meta: dict[str, Any] = {}
        errors = None
        response = SAFRSFormattedResponse(data, meta, links, errors, count)
    except Exception as exc:
        raise GenericError("Failed to execute query") from exc

    for key, value in kwargs.items():
        column = _filter_column(cls, key)
        try:
            instances = result.query.filter(column.like(value + "%"))
            instances = apply_filter_read_permissions(cls, instances, (key,))
            links, instances, count = paginate(instances)
            data = [item for item in instances]
            meta = {}
            errors = None
            response = SAFRSFormattedResponse(data, meta, links, errors, count)
        except Exception as exc:
            raise GenericError("Failed to execute query") from exc
    return response


@classmethod  # type: ignore[misc]
@jsonapi_rpc(http_methods=["POST"])
def search(cls: Any, **kwargs: str) -> SAFRSFormattedResponse:  # pragma: no cover
    """
    pageable: True
    description: Lookup column names
    args:
        query: val
    """
    query = kwargs.get("query", "")
    columns = [
        c
        for c in cls._s_columns
        if c.type.python_type in [str, int, float]
        and get_filterable_attribute(cls, cls.colname_to_attrname(c.name)) is not None
    ]
    if ":" in query:
        column_name, value = query.split(":")
        searched_columns = [column for column in columns if column.name == column_name]
        result = cls.query.filter(or_(*[column.like("%" + value + "%") for column in searched_columns]))
    else:
        searched_columns = columns
        result = cls.query.filter(or_(*[column.like("%" + query + "%") for column in columns]))
    searched_attrs = [cls.colname_to_attrname(column.name) for column in searched_columns]
    instances = apply_filter_read_permissions(cls, result, searched_attrs)
    instances = jsonapi_sort(instances, cls)
    links, instances, count = paginate(instances)
    data = [item for item in instances]
    meta: dict[str, Any] = {}
    errors = None
    return SAFRSFormattedResponse(data, meta, links, errors, count)


@classmethod  # type: ignore[misc]
@jsonapi_rpc(http_methods=["POST"])
def re_search(cls: Any, **kwargs: str) -> SAFRSFormattedResponse:  # pragma: no cover
    """
    pageable: True
    description: Lookup column names
    args:
        query: search.*all
    """
    query = kwargs.get("query", "")
    columns = [
        column
        for column in cls._s_columns
        if get_filterable_attribute(cls, cls.colname_to_attrname(column.name)) is not None
    ]
    result = cls.query.filter(or_(*[column.op("regexp")(query) for column in columns]))
    instances = apply_filter_read_permissions(
        cls,
        result,
        [cls.colname_to_attrname(column.name) for column in columns],
    )
    links, instances, count = paginate(instances)
    data = [item for item in instances]
    meta: dict[str, Any] = {}
    errors = None
    return SAFRSFormattedResponse(data, meta, links, errors, count)
