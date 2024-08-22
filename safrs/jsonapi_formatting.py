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


def jsonapi_filter_list(relation):
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


def jsonapi_filter_query(object_query, safrs_object):
    """
    :param object_query: query to be filtered (lazy='dynamic' relationships AppenderBaseQuery)
    :param safrs_object: sqla object to be queried
    :return: sqla query object

    Called when filtering a relationship query
    """
    filter_query = safrs_object.jsonapi_filter()
    result = object_query.intersect(filter_query)
    return result


def jsonapi_sort(object_query, safrs_object):
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


def paginate(object_query, SAFRSObject=None):
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

    def get_link(count, limit):
        result = SAFRSObject._s_url if SAFRSObject else ""
        ignore_args = "page[offset]", "page[limit]"
        result += "?" + "&".join(
            [f"{k}={v}" for k, v in request.args.items() if k not in ignore_args] + [f"page[offset]={count}&page[limit]={limit}"]
        )
        return result

    try:
        page_offset = int(get_request_param("page_offset"))
        limit = int(get_request_param("page_limit", get_config("DEFAULT_PAGE_LIMIT")))
    except ValueError:
        raise ValidationError("Pagination Value Error")

    if limit <= 0:
        limit = 1
    if limit > get_config("MAX_PAGE_LIMIT"):
        limit = get_config("MAX_PAGE_LIMIT")
    if page_offset <= 0:
        page_offset = 0
    if page_offset > get_config("MAX_PAGE_OFFSET"):
        page_offset = get_config("MAX_PAGE_OFFSET")
    page_base = int(page_offset / limit) * limit

    # Counting may take > 1s for a table with millions of records, depending on the storage engine :|
    # Make it configurable
    # With mysql innodb we can use following to retrieve the count:
    # select TABLE_ROWS from information_schema.TABLES where TABLE_NAME = 'TableName';
    if isinstance(object_query, (list, sqlalchemy.orm.collections.InstrumentedList)):
        count = len(object_query)
    elif SAFRSObject is None:  # for backwards compatibility, ie. when not passed as an arg to paginate()
        count = object_query.count()
    else:
        count = SAFRSObject._s_count()

    first_args = (0, limit)
    last_args = (int(int(count / limit) * limit), limit)  # round down
    self_args = (page_base if page_base <= last_args[0] else last_args[0], limit)
    next_args = (page_offset + limit, limit) if page_offset + limit <= last_args[0] else last_args
    prev_args = (page_offset - limit, limit) if page_offset > limit else first_args

    links = {
        "first": get_link(*first_args),
        "self": get_link(page_offset, limit),  # cfr. request.url
        "last": get_link(*last_args),
        "prev": get_link(*prev_args),
        "next": get_link(*next_args),
    }

    if last_args == self_args:
        del links["last"]
    if first_args == self_args:
        del links["first"]
    if next_args == last_args:
        del links["next"]
    if prev_args == first_args:
        del links["prev"]

    if isinstance(object_query, (list, sqlalchemy.orm.collections.InstrumentedList)):
        instances = object_query[page_offset : page_offset + limit]
    elif isinstance(object_query, dict):
        # (might happen when using a custom filter)
        instances = object_query
    elif not hasattr(object_query, "offset"):
        # in case the query is emulated
        instances = []
    else:
        try:
            res_query = object_query.offset(page_offset).limit(limit)
            instances = res_query.all()
        except OverflowError:
            raise ValidationError("Pagination Overflow Error")
        except sqlalchemy.exc.CompileError as exc:  # pragma: no cover
            # dirty workaround for when no sort parameter is provided in case of mssql offset/limit queries
            # error msg:
            #     "MSSQL requires an order_by when using an OFFSET or a non-simple LIMIT clause"
            safrs.log.warning(f"{exc} / Add a valid sort= URL parameter")
            if "MSSQL requires an order_by" in str(exc) and SAFRSObject and SAFRSObject.id_type.primary_keys:
                pk = SAFRSObject.id_type.primary_keys[0]
                res_query = object_query.order_by(getattr(SAFRSObject, pk)).offset(page_offset).limit(limit)
                instances = res_query.all()
            else:
                raise GenericError(f"{exc}")
        except Exception as exc:
            raise GenericError(f"{exc}")

    return links, instances, count


def jsonapi_format_response(data=None, meta=None, links=None, errors=None, count=None, include=None):
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
