# -*- coding: utf-8 -*-
#
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
from .base import is_jsonapi_attr, Included
from .errors import ValidationError, GenericError
from .config import get_config, get_request_param


def jsonapi_filter(safrs_object):
    """
        https://jsonapi.org/recommendations/#filtering
        Apply the request.args filters to the object
        :param safrs_object: the safrs class object that is queried
        :return: sqla query object
    """
    # First check if a filter= URL query parameter has been used
    # the SAFRSObject should've implemented a filter method or
    # overwritten the _s_filter method to implement custom filtering
    filter_args = get_request_param("filter")
    if filter_args:
        safrs_object_filter = getattr(safrs_object, "filter", None)
        if isinstance(safrs_object, (list, sqlalchemy.orm.collections.InstrumentedList)):
            # not implemented
            result = safrs_object
        elif callable(safrs_object_filter):
            result = safrs_object_filter(filter_args)
        else:
            result = safrs_object._s_filter(filter_args)
        return result

    expressions = []
    filters = get_request_param("filters", {})
    if isinstance(safrs_object, (list, sqlalchemy.orm.collections.InstrumentedList)):
        return safrs_object

    for attr_name, val in filters.items():
        if attr_name == "id":
            return safrs_object._s_get_instance_by_id(val)
        if attr_name not in safrs_object._s_jsonapi_attrs:
            # validation failed: this attribute can't be queried
            safrs.log.warning("Invalid filter {}".format(attr_name))
            continue
        else:
            attr = safrs_object._s_jsonapi_attrs[attr_name]
        if is_jsonapi_attr(attr):
            # to do
            safrs.log.debug("Filtering not implemented for {}".format(attr))
        else:
            expressions.append((attr, val))

    if expressions:
        _expressions = []
        for column, val in expressions:
            if hasattr(column, "in_"):
                _expressions.append(column.in_(val.split(",")))
            else:
                safrs.log.warning("'{}.{}' is not a column ({})".format(safrs_object, column, type(column)))
        result = safrs_object._s_query.filter(*_expressions)
    else:
        result = safrs_object._s_query

    return result


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
        filter_query = jsonapi_filter(instance.__class__)
        result.update(filter_query.filter_by(**pks).all())  # this should only contain zero or one items
    return list(result)


def jsonapi_filter_query(object_query, safrs_object):
    """
        :param object_query: query to be filtered (lazy='dynamic' relationships AppenderBaseQuery)
        :param safrs_object: sqla object to be queried
        :return: sqla query object

        Called when filtering a relationship query
    """
    filter_query = jsonapi_filter(safrs_object)
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
    sort_attrs = request.args.get("sort", None)
    if sort_attrs is not None:
        for sort_attr in sort_attrs.split(","):
            reverse = sort_attr.startswith("-")
            if reverse:
                # if the sort column starts with - , then we want to do a reverse sort
                # The sort order for each sort field MUST be ascending unless it is prefixed
                # with a minus, in which case it MUST be descending.
                sort_attr = sort_attr[1:]
                attr = getattr(safrs_object, sort_attr, None)
                if attr is not None:
                    attr = attr.desc()
            else:
                attr = getattr(safrs_object, sort_attr, None)
            if sort_attr == "id":
                if attr is None:
                    # jsonapi_id is a composite key => to do: parse the id
                    continue
            elif attr is None or sort_attr not in safrs_object._s_jsonapi_attrs:
                safrs.log.debug("{} has no attribute {} in {}".format(safrs_object, sort_attr, safrs_object._s_jsonapi_attrs))
                continue
            if isinstance(object_query, (list, sqlalchemy.orm.collections.InstrumentedList)):
                object_query = sorted(list(object_query), key=lambda obj: getattr(obj, sort_attr), reverse=reverse)
            elif is_jsonapi_attr(attr):
                # to do: implement sorting for jsonapi_attr
                safrs.log.debug("sorting not implemented for {}".format(attr))
            else:
                try:
                    # This may fail on non-sqla objects, eg. properties
                    object_query = object_query.order_by(attr)
                except sqlalchemy.exc.ArgumentError as exc:
                    safrs.log.warning("Sort failed for {}.{}: {}".format(safrs_object, sort_attr, exc))
                except Exception as exc:
                    safrs.log.warning("Sort failed for {}.{}: {}".format(safrs_object, sort_attr, exc))

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
        result += "?" + "&".join(
            ["{}={}".format(k, v) for k, v in request.args.items()] + ["page[offset]={}&page[limit]={}".format(count, limit)]
        )
        return result

    try:
        page_offset = int(get_request_param("page_offset"))
        limit = int(get_request_param("page_limit", get_config("MAX_PAGE_LIMIT")))
    except ValueError:
        raise ValidationError("Pagination Value Error")

    if limit <= 0:
        limit = 1
    if limit > get_config("MAX_PAGE_LIMIT"):
        limit = get_config("MAX_PAGE_LIMIT")
    if page_offset <= 0:
        page_offset = 0
    if page_offset > get_config("MAX_PAGE_LIMIT"):
        page_offset = get_config("MAX_PAGE_LIMIT")
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
    if count is None:
        try:
            count = object_query.count()
        except Exception as exc:
            # May happen for custom types, for ex. the psycopg2 extension
            safrs.log.warning("Can't get count for {} ({})".format(SAFRSObject, exc))
            count = -1

        if count > get_config("MAX_TABLE_COUNT"):
            safrs.log.warning("Large table count detected, performance may be impacted, consider using '_s_count'")

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
        instances = object_query[page_offset:page_offset + limit]
    elif isinstance(object_query, dict):
        # (might happen when using a custom filter)
        instances = object_query
    else:
        try:
            res_query = object_query.offset(page_offset).limit(limit)
            instances = res_query.all()
        except OverflowError:
            raise ValidationError("Pagination Overflow Error")
        except Exception as exc:
            raise GenericError("Pagination Error {}".format(exc))

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
    meta["count"] = count

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

    result["included"] = Included

    return result
