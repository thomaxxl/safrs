from typing import Any, cast
# JSON:API response formatting functions:
# - filtering (https://jsonapi.org/format/#fetching-filtering)
# - sorting (https://jsonapi.org/format/#fetching-sorting)
# - pagination (https://jsonapi.org/format/#fetching-pagination)
#
# Response formatting follows filter -> sort -> paginate
#
import sqlalchemy
import sqlalchemy.orm.dynamic
import sqlalchemy.orm.collections
import safrs
from flask import request
from .jsonapi_attr import is_jsonapi_attr
from .errors import ValidationError, GenericError
from .config import get_config, get_request_param


def jsonapi_filter_list(relation: Any) -> Any:
    """
    :param relation: InstrumentedList
    :return: list of instances filtered using the jsonapi filters in the url query args

    Called when filtering a relationship collection
    """
    result = set()
    for instance in relation:
        if not hasattr(instance, "id_type"):
            # item is not a SAFRSBase instance
            result.add(instance)
            continue
        pks = {col.name: getattr(instance, col.name) for col in instance.id_type.columns}
        filter_query = instance.__class__.jsonapi_filter()
        result.update(filter_query.filter_by(**pks).all())  # this should only contain zero or one items
    return list(result)


def jsonapi_filter_query(object_query: Any, safrs_object: Any) -> Any:
    """
    :param object_query: query to be filtered (lazy='dynamic' relationships AppenderBaseQuery)
    :param safrs_object: sqla object to be queried
    :return: sqla query object

    Called when filtering a relationship query
    """
    filter_query = safrs_object.jsonapi_filter()
    result = object_query.intersect(filter_query)
    return result


def jsonapi_sort(object_query: Any, safrs_object: Any) -> Any:
    """
    http://jsonapi.org/format/#fetching-sorting
    sort by csv sort= values
    :param object_query: sqla query object
    :param safrs_object: SAFRSObject
    :return: sqla query object
    """
    sort_attrs = request.args.get("sort", "") or "id"

    for sort_attr in sort_attrs.split(","):
        reverse = sort_attr.startswith("-")
        if reverse:
            # if the sort column starts with - , then we want to do a reverse sort
            # The sort order for each sort field MUST be ascending unless it is prefixed
            # with a minus, in which case it MUST be descending.
            sort_attr = sort_attr[1:]
            attr = getattr(safrs_object, sort_attr, None)
            if attr is not None and hasattr(attr, "desc"):
                attr = attr.desc()
        else:
            attr = getattr(safrs_object, sort_attr, None)
        if sort_attr == "id":
            if attr is None:
                if safrs_object.id_type.primary_keys:
                    attr = getattr(safrs_object, safrs_object.id_type.primary_keys[0], None)  # todo: composite keys edge case
                    if attr is not None:  # might be the case if pk is unicode
                        sort_attr = attr.name
                else:
                    continue
        elif attr is None or sort_attr not in safrs_object._s_jsonapi_attrs:
            safrs.log.debug(f"{safrs_object} has no attribute {sort_attr} in {safrs_object._s_jsonapi_attrs}")
            continue
        if isinstance(object_query, (list, sqlalchemy.orm.collections.InstrumentedList)):
            object_query = sorted(
                list(object_query), key=lambda obj: (getattr(obj, sort_attr, None) is None, getattr(obj, sort_attr, None)), reverse=reverse
            )
        elif is_jsonapi_attr(attr):
            # to do: implement sorting for jsonapi_attr
            safrs.log.debug(f"sorting not implemented for {attr}")
        elif hasattr(object_query, "order_by"):
            try:
                # This may fail on non-sqla objects, eg. properties
                object_query = object_query.order_by(attr)
            except sqlalchemy.exc.ArgumentError as exc:
                safrs.log.warning(f"Sort failed for {safrs_object}.{sort_attr}: {exc}")
            except Exception as exc:
                safrs.log.warning(f"Sort failed for {safrs_object}.{sort_attr}: {exc}")

    return object_query


def _paginate_link(base_url: str, count: int, limit: int) -> str:
    ignore_args = "page[offset]", "page[limit]"
    params = [f"{k}={v}" for k, v in request.args.items() if k not in ignore_args]
    params.append(f"page[offset]={count}&page[limit]={limit}")
    return base_url + "?" + "&".join(params)


def _pagination_args() -> tuple[int, int]:
    try:
        page_offset = int(get_request_param("page_offset"))
        limit = int(get_request_param("page_limit", get_config("DEFAULT_PAGE_LIMIT")))
    except ValueError as exc:
        raise ValidationError("Pagination Value Error") from exc

    max_page_limit = cast(int, get_config("MAX_PAGE_LIMIT"))
    max_page_offset = cast(int, get_config("MAX_PAGE_OFFSET"))
    if limit <= 0:
        limit = 1
    if limit > max_page_limit:
        limit = max_page_limit
    if page_offset <= 0:
        page_offset = 0
    if page_offset > max_page_offset:
        page_offset = max_page_offset
    return page_offset, limit


def _pagination_count(object_query: Any, safrs_object: Any) -> int:
    if isinstance(object_query, (list, sqlalchemy.orm.collections.InstrumentedList)):
        return len(object_query)
    if safrs_object is None:
        return object_query.count()
    return safrs_object._s_count()


def _pagination_links(page_offset: int, limit: int, count: int, base_url: str) -> dict[str, str]:
    page_base = int(page_offset / limit) * limit
    first_args = (0, limit)
    last_args = (int(int(count / limit) * limit), limit)
    self_args = (page_base if page_base <= last_args[0] else last_args[0], limit)
    next_args = (page_offset + limit, limit) if page_offset + limit <= last_args[0] else last_args
    prev_args = (page_offset - limit, limit) if page_offset > limit else first_args
    links = {
        "first": _paginate_link(base_url, *first_args),
        "self": _paginate_link(base_url, page_offset, limit),
        "last": _paginate_link(base_url, *last_args),
        "prev": _paginate_link(base_url, *prev_args),
        "next": _paginate_link(base_url, *next_args),
    }
    if last_args == self_args:
        del links["last"]
    if first_args == self_args:
        del links["first"]
    if next_args == last_args:
        del links["next"]
    if prev_args == first_args:
        del links["prev"]
    return links


def _paginate_instances(object_query: Any, page_offset: int, limit: int, safrs_object: Any) -> Any:
    if isinstance(object_query, (list, sqlalchemy.orm.collections.InstrumentedList)):
        return object_query[page_offset : page_offset + limit]
    if isinstance(object_query, dict):
        return object_query
    if not hasattr(object_query, "offset"):
        return []

    try:
        return object_query.offset(page_offset).limit(limit).all()
    except OverflowError as exc:
        raise ValidationError("Pagination Overflow Error") from exc
    except sqlalchemy.exc.CompileError as exc:  # pragma: no cover
        safrs.log.warning(f"{exc} / Add a valid sort= URL parameter")
        if "MSSQL requires an order_by" in str(exc) and safrs_object and safrs_object.id_type.primary_keys:
            pk = safrs_object.id_type.primary_keys[0]
            return object_query.order_by(getattr(safrs_object, pk)).offset(page_offset).limit(limit).all()
        raise GenericError(f"{exc}") from exc
    except Exception as exc:
        raise GenericError(f"{exc}") from exc


def paginate(object_query: Any, SAFRSObject: Any=None) -> Any:
    """
    this is where the query is executed, hence it's the bottleneck of the queries

    http://jsonapi.org/format/#fetching-pagination

    A server MAY choose to limit the number of resources returned
    in a response to a subset (“page”) of the whole set available.
    A server MAY provide links to traverse a paginated data set (“pagination links”).
    Pagination links MUST appear in the links object that corresponds
    to a collection. To paginate the primary data, supply pagination links
    in the top-level links object. To paginate an included collection
    returned in a compound document, supply pagination links in the
    corresponding links object.

    The following keys MUST be used for pagination links:

    first: the first page of data
    last: the last page of data
    prev: the previous page of data
    next: the next page of data

    We use page[offset] and page[limit], where
    offset is the number of records to offset by prior to returning resources

    :param object_query: SQLAalchemy query object
    :param SAFRSObject: optional
    :return: links, instances, count
    """

    page_offset, limit = _pagination_args()
    count = _pagination_count(object_query, SAFRSObject)
    base_url = SAFRSObject._s_url if SAFRSObject else ""
    links = _pagination_links(page_offset, limit, count, base_url)
    instances = _paginate_instances(object_query, page_offset, limit, SAFRSObject)
    return links, instances, count


def jsonapi_format_response(data: Any=None, meta: Any=None, links: Any=None, errors: Any=None, count: Any=None, include: Any=None) -> Any:
    """
    Create a response dict according to the json:api schema spec
    :param data : the objects that will be serialized
    :return: jsonapi formatted dictionary
    """
    limit = get_request_param("page_limit", get_config("MAX_PAGE_LIMIT"))
    try:
        limit = int(limit)
    except ValueError:
        raise ValidationError("page[limit] error")
    if meta is None:
        meta = {}

    meta["limit"] = limit
    meta["count"] = meta["total"] = count

    jsonapi = dict(version="1.0")
    result = dict(data=data)

    if errors:
        result["errors"] = errors
    if meta:
        result["meta"] = meta
    if jsonapi:
        result["jsonapi"] = jsonapi
    if links:
        result["links"] = links

    result["included"] = safrs.base.Included

    return result
