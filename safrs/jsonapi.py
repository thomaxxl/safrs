# -*- coding: utf-8 -*-
"""
  This file contains jsonapi-related flask-restful "Resource" objects:
  - SAFRSRestAPI for exposed database objects
  - SAFRSRestRelationshipAPI for exposed database relationships
  - SAFRSRestMethodAPI for exposed jsonapi_rpc methods

  Other jsonapi-related functions are also implemented here:
  - filtering: jsonapi_filter
  - sorting: jsonapi_sort
  - pagination: paginate
  - retrieve included resources: get_included
"""
#
# Some linting errors to ignore
# pylint: disable=redefined-builtin,invalid-name, line-too-long, protected-access, no-member, too-many-lines
# pylint: disable=fixme, logging-format-interpolation
#
# Configuration parameters:
# - endpoint
#
# todo:
# - expose canonical endpoints
# - move all swagger formatting to swagger_doc
#
import logging
from http import HTTPStatus
import sqlalchemy
import sqlalchemy.orm.dynamic
import sqlalchemy.orm.collections
from sqlalchemy.orm.interfaces import MANYTOONE
from flask import make_response, url_for
from flask import jsonify, request
from flask_restful_swagger_2 import Resource as FRSResource
import safrs
from .base import SAFRSBase
from .swagger_doc import is_public
from .errors import ValidationError, GenericError, NotFoundError
from .config import get_config, get_request_param
from .json_encoder import SAFRSFormattedResponse
from .util import classproperty

INCLUDE_ALL = "+all"  # this "include" query string parameter value tells us to retrieve all included resources

# JSON:API Response formatting follows filter -> sort -> paginate
def jsonapi_filter(safrs_object):
    """
        https://jsonapi.org/recommendations/#filtering
        Apply the request.args filters to the object
        :param safrs_object:
        :return: a sqla query object
    """
    # First check if a filter= URL query parameter has been used
    # the SAFRSObject should've implemented a filter method or
    # overwritten the _s_filter method to implement custom filtering
    filter_args = get_request_param("filter")
    if filter_args:
        safrs_object_filter = getattr(safrs_object, "filter", None)
        if callable(safrs_object_filter):
            result = safrs_object_filter(filter_args)
        else:
            result = safrs_object._s_filter(filter_args)
        return result

    expressions = []
    filters = get_request_param("filters", {})
    for attr_name, val in filters.items():
        if not attr_name in safrs_object._s_jsonapi_attrs + ["id"]:
            safrs.log.warning("Invalid filter {}".format(attr_name))
            continue
        attr = getattr(safrs_object, attr_name)
        expressions.append((attr, val))

    if isinstance(safrs_object, (list, sqlalchemy.orm.collections.InstrumentedList)):
        # todo: filter properly
        result = safrs_object
    elif expressions:
        expressions_ = [column.in_(val.split(",")) for column, val in expressions]
        result = safrs_object._s_query.filter(*expressions_)
    else:
        result = safrs_object._s_query

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
    if not sort_attrs is None:
        for sort_attr in sort_attrs.split(","):
            if sort_attr.startswith("-"):
                # if the sort column starts with - , then we want to do a reverse sort
                # The sort order for each sort field MUST be ascending unless it is prefixed
                # with a minus, in which case it MUST be descending.
                sort_attr = sort_attr[1:]
                attr = getattr(safrs_object, sort_attr, None)
                if not attr is None:
                    attr = attr.desc()
            else:
                attr = getattr(safrs_object, sort_attr, None)
            if sort_attr == "id":
                if attr is None:
                    # => todo: parse the id
                    continue
            elif attr is None or sort_attr not in safrs_object._s_jsonapi_attrs:
                safrs.log.error("{} has no column {} in {}".format(safrs_object, sort_attr, safrs_object._s_jsonapi_attrs))
                continue
            if isinstance(object_query, (list, sqlalchemy.orm.collections.InstrumentedList)):
                object_query = sorted(list(object_query), key=lambda obj: getattr(obj, sort_attr), reverse=sort_attr.startswith("-"))
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
        count = object_query.count()
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
        instances = object_query[page_offset : page_offset + limit]
    else:
        try:
            res_query = object_query.offset(page_offset).limit(limit)
            instances = res_query.all()
        except OverflowError:
            raise ValidationError("Pagination Overflow Error")
        except Exception as exc:
            raise GenericError("Pagination Error {}".format(exc))

    return links, instances, count


def get_included(data, limit, include="", level=0):
    """
        :param data:
        :param limit:
        :param include: csv string with the items to include
        :param level:
        :return:
        return a set of included items

        http://jsonapi.org/format/#fetching-includes

        Inclusion of Related Resources
        Multiple related resources can be requested in a comma-separated list:
        An endpoint MAY return resources related to the primary data by default.
        An endpoint MAY also support an include request parameter to allow
        the client to customize which related resources should be returned.
        In order to request resources related to other resources,
        a dot-separated path for each relationship name can be specified
    """
    result = set()

    if not include:
        return result

    if isinstance(data, (list, set)):
        for included in [get_included(obj, limit, include, level=level + 1) for obj in data]:
            result = result.union(included)
        return result

    # When we get here, data has to be a SAFRSBase instance
    if not isinstance(data, SAFRSBase):
        return result
    instance = data

    # Multiple related resources can be requested in a comma-separated list
    includes = include.split(",")

    if INCLUDE_ALL in includes:
        includes += [r.key for r in instance._s_relationships]

    for include in set(includes):
        relationship = include.split(".")[0]
        nested_rel = None
        if "." in include:
            nested_rel = ".".join(include.split(".")[level:])
        if relationship in [r.key for r in instance._s_relationships]:
            included = getattr(instance, relationship)

            # relationship direction in (ONETOMANY, MANYTOMANY):
            if included and isinstance(included, SAFRSBase) and included not in result:
                # convert single instance to a list so we can generically add the includes
                included = [included]
            elif isinstance(included, sqlalchemy.orm.collections.InstrumentedList):
                pass
            elif not included or included in result:
                continue
            try:
                # This works on sqlalchemy.orm.dynamic.AppenderBaseQuery
                included = included[:limit]
            except Exception as exc:
                safrs.log.debug("Failed to add included for {} (included: {} - {}): {}".format(relationship, type(included), included, exc))

            try:
                result = result.union(included)
            except Exception as exc:
                safrs.log.warning(
                    "Failed to unionize included for {} (included: {} - {}): {}".format(relationship, type(included), included, exc)
                )
                result.add(included)

        if INCLUDE_ALL in includes:
            for nested_included in [get_included(result, limit, level=level + 1) for obj in result]:
                # Removed recursion with get_included(result, limit, INCLUDE_ALL)
                result = result.union(nested_included)

        elif nested_rel:
            for nested_included in [get_included(result, limit, nested_rel, level=level + 1) for obj in result]:
                result = result.union(nested_included)

    return result


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

    if include is None:
        include = request.args.get("include", safrs.SAFRS.DEFAULT_INCLUDED)

    meta["limit"] = limit
    meta["count"] = count

    jsonapi = dict(version="1.0")
    included = list(get_included(data, limit, include=include))
    """if count >= 0:
        included = jsonapi_format_response(included, {}, {}, {}, -1)"""
    result = dict(data=data)

    if errors:
        result["errors"] = errors
    if meta:
        result["meta"] = meta
    if jsonapi:
        result["jsonapi"] = jsonapi
    if links:
        result["links"] = links
    if included:
        result["included"] = included

    return result


class Resource(FRSResource):

    SAFRSObject = None  # The class that will be returned when a http method is invoked
    # Flask views will need to set this to the SQLAlchemy safrs.DB.Model class
    target = None

    def _parse_target_data(self, child_data):
        """
            Validate the jsonapi payload in child_data, which should contain "id" and "type" keys
        """
        if not isinstance(child_data, dict):
            raise ValidationError("Invalid data type {}".format(child_data))
        child_id = child_data.get("id", None)
        if child_id is None:
            raise ValidationError("no child id {}".format(child_data))
        child_type = child_data.get("type")
        if not child_id:
            raise ValidationError("Invalid id in data", HTTPStatus.FORBIDDEN)
        if not child_type:
            raise ValidationError("Invalid type in data", HTTPStatus.FORBIDDEN)
        if child_type != self.target._s_type:
            raise ValidationError("Invalid type {} != {}".format(child_type, self.target._s_type), HTTPStatus.FORBIDDEN)
        child = self.target.get_instance(child_id)
        if not child:
            raise ValidationError("invalid child id {}".format(child_id))
        return child

    @classmethod
    def get_swagger_include(cls):
        """
            :return: JSON:API "include" query string swagger spec
        """
        default_include = ",".join(cls.SAFRSObject._s_relationship_names)

        param = {
            "default": default_include,
            "type": "string",
            "name": "include",
            "in": "query",
            "format": "string",
            "required": False,
            "description": "{} relationships to include (csv)".format(cls.SAFRSObject._s_class_name),
        }
        return param

    @classmethod
    def get_swagger_fields(cls):
        """
            :return: JSON:API fields[] swagger spec
        """
        attr_list = list(cls.SAFRSObject._s_jsonapi_attrs)
        # Add the fields query string swagger
        # todo: get the columns of the target
        param = {
            "default": ",".join(attr_list),
            "type": "string",
            "name": "fields[{}]".format(cls.SAFRSObject._s_class_name),
            "in": "query",
            "format": "string",
            "required": False,
            "description": "{} fields to include (csv)".format(cls.SAFRSObject._s_class_name),
        }
        return param

    @classmethod
    def get_swagger_sort(cls):
        """
            :return: JSON:API sort swagger spec
        """
        attr_list = list(cls.SAFRSObject._s_jsonapi_attrs) + ["id"]

        param = {
            "default": ",".join(attr_list),
            "type": "string",
            "name": "sort",
            "in": "query",
            "format": "string",
            "required": False,
            "description": "Sort order",
        }
        return param

    @classmethod
    def get_swagger_filters(cls):
        """
            :return: JSON:API filters swagger spec
            create the filter[] swagger doc for all jsonapi attributes + the id
        """
        attr_list = list(cls.SAFRSObject._s_jsonapi_attrs) + ["id"]

        for column_name in attr_list:
            param = {
                "default": "",
                "type": "string",
                "name": "filter[{}]".format(column_name),
                "in": "query",
                "format": "string",
                "required": False,
                "description": "{} attribute filter (csv)".format(column_name),
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


class SAFRSRestAPI(Resource):
    """
        Flask webservice wrapper for the underlying Resource Object:
        an sqla db model (SAFRSBase subclass : cls.SAFRSObject)

        This class implements HTTP Methods (get, post, put, delete, ...) and helpers

        http://jsonapi.org/format/#document-resource-objects
        A resource object MUST contain at least the following top-level members:
        - id
        - type

        In addition, a resource object MAY contain any of these top-level members:

        attributes: an attributes object representing some of the resource’s data.
        relationships: a relationships object describing relationships
                        between the resource and other JSON API resources.
        links: a links object containing links related to the resource.
        meta: a meta object containing non-standard meta-information
                about a resource that can not be represented as an attribute or relationship.

        e.g.
        {
            "id": "1f1c0e90-9e93-4242-9b8c-56ac24e505e4",
            "type": "car",
            "attributes": {
                "color": "red"
            },
            "relationships": {
                "driver": {
                    "data": {
                        "id": "55550e90-9e93-4242-9b8c-56ac24e505e5",
                        "type": "person"
                    }
                }
        }

        A resource object’s attributes and its relationships are collectively called its “fields”.
    """

    default_order = None  # used by sqla order_by
    object_id = None

    def __init__(self, *args, **kwargs):
        """
            - object_id is the function used to create the url parameter name
            (eg "User" -> "UserId" )
            - this parameter is used in the swagger endpoint spec,
            eg. /Users/{UserId} where the UserId parameter is the id of
            the underlying SAFRSObject.
        """
        self.object_id = self.SAFRSObject.object_id
        self.target = self.SAFRSObject

    def get(self, **kwargs):
        """
            summary : Retrieve a {class_name} object
            description : Retrieve {class_name} from {collection_name}
            responses :
                200 :
                    description : Request fulfilled, document follows
                403 :
                    description : Forbidden
                404 :
                    description : Not Found
            ---
            HTTP GET: return instances
            If no id is given: return all instances
            If an id is given, get an instance by id
            If a method is given, call the method on the instance

            http://jsonapi.org/format/#document-top-level

            A JSON object MUST be at the root of every JSON API request
            and response containing data. This object defines a document’s “top level”.

            A document MUST contain at least one of the following top-level members:
            - data: the document’s “primary data”
            - errors: an array of error objects
            - meta: a meta object that contains non-standard meta-information.

            A document MAY contain any of these top-level members:
            - jsonapi: an object describing the server’s implementation
            - links: a links object related to the primary data.
            - included: an array of resource objects that are related
            to the primary data and/or each other (“included resources”).
        """
        data = None
        meta = {}
        errors = None
        links = None

        id = kwargs.get(self.object_id, None)
        # method_name = kwargs.get('method_name','')

        if id:
            # Retrieve a single instance
            instance = self.SAFRSObject.get_instance(id)
            data = instance
            links = {"self": instance._s_url}
            if request.url != instance._s_url:
                links["related"] = request.url
            count = 1
            meta.update(dict(instance_meta=instance._s_meta()))

        else:
            # retrieve a collection, filter and sort
            instances = jsonapi_filter(self.SAFRSObject)
            instances = jsonapi_sort(instances, self.SAFRSObject)
            links, data, count = paginate(instances, self.SAFRSObject)
        # format the response: add the included objects
        result = jsonapi_format_response(data, meta, links, errors, count)
        return jsonify(result)

    def patch(self, **kwargs):
        """
            summary : Update {class_name}
            description: Update {class_name} attributes
            responses:
                200 :
                    description : Accepted
                201 :
                    description : Created
                204 :
                    description : No Content
                403:
                    description : Forbidden
                404 :
                    description : Not Found
                409 :
                    description : Conflict
            ---
            Update the object with the specified id
        """
        id = kwargs.get(self.object_id, None)

        payload = request.get_jsonapi_payload()
        if not isinstance(payload, dict):
            raise ValidationError("Invalid Object Type")

        data = payload.get("data")
        if id is None and isinstance(data, list):
            # Bulk patch request
            for item in data:
                if not isinstance(item, dict):
                    raise ValidationError("Invalid Data Object")
                instance = self._patch_instance(item)
            response = make_response({}, HTTPStatus.CREATED)

        elif not data or not isinstance(data, dict):
            raise ValidationError("Invalid Data Object")
        elif id is None:
            raise ValidationError("Invalid ID")
        else:
            path_id = self.SAFRSObject.id_type.validate_id(id)
            instance = self._patch_instance(data, path_id)
            """
            attributes = data.get("attributes", {})
            attributes["id"] = body_id
            # Create the object instance with the specified id and json data
            # If the instance (id) already exists, it will be updated with the data
            instance = self._parse_target_data(data)
            if not instance:
                raise ValidationError("No instance with ID")
            instance._s_patch(**attributes)
            """

            # object id is the endpoint parameter, for example "UserId" for a User SAFRSObject
            obj_args = {instance.object_id: instance.jsonapi_id}
            # Retrieve the object json and return it to the client
            obj_data = self.get(**obj_args)
            response = make_response(obj_data, HTTPStatus.CREATED)
            # Set the Location header to the newly created object
            response.headers["Location"] = url_for(self.endpoint, **obj_args)
        return response

    def _patch_instance(self, data, path_id=None):
        """
        
        """
        # Check that the id in the body is equal to the id in the url
        body_id = data.get("id", None)
        if body_id is None:
            raise ValidationError("No ID in body")

        body_id = self.SAFRSObject.id_type.validate_id(body_id)
        if path_id is not None and path_id != body_id:
            raise ValidationError("Invalid ID {} {} != {} {}".format(type(path_id), path_id, type(body_id), body_id))

        attributes = data.get("attributes", {})
        attributes["id"] = body_id
        # Create the object instance with the specified id and json data
        # If the instance (id) already exists, it will be updated with the data
        instance = self._parse_target_data(data)
        if not instance:
            raise ValidationError("No instance with ID")
        instance._s_patch(**attributes)

        return instance

    def post(self, **kwargs):
        """
            summary : Create {class_name}
            responses :
                403:
                    description : Forbidden
                201:
                    description: Created
                202:
                    description : Accepted
                404:
                    description : Not Found
                409:
                    description : Conflict
            ---
            http://jsonapi.org/format/#crud-creating
            Creating Resources
            A resource can be created by sending a POST request to a URL
            that represents a collection of resources.
            The request MUST include a single resource object as primary data.
            The resource object MUST contain at least a type member.

            If a relationship is provided in the relationships member of the resource object,
            its value MUST be a relationship object with a data member.
            The value of this key represents the linkage the new resource is to have.

            Response:
            403: This implementation does not accept client-generated IDs
            201: Created
            202: Accepted
            404: Not Found
            409: Conflict

            Location Header identifying the location of the newly created resource
            Body : created object

            TODO:
            409 Conflict
              A server MUST return 409 Conflict when processing a POST request
              to create a resource with a client-generated ID that already exists.
              A server MUST return 409 Conflict when processing a POST request
              in which the resource object’s type is not among the type(s) that
              constitute the collection represented by the endpoint.
              A server SHOULD include error details and provide enough
              information to recognize the source of the conflict.
        """
        payload = request.get_jsonapi_payload()
        method_name = payload.get("meta", {}).get("method", None)

        id = kwargs.get(self.object_id, None)
        if id is not None:
            # POSTing to an instance isn't jsonapi-compliant (https://jsonapi.org/format/#crud-creating-client-ids)
            raise ValidationError("POSTing to instance is not allowed {}".format(self), status_code=HTTPStatus.METHOD_NOT_ALLOWED)

        # Create a new instance of the SAFRSObject
        data = payload.get("data")
        if data is None:
            raise ValidationError("Request contains no data")
        if isinstance(data, list):
            # http://springbot.github.io/json-api/extensions/bulk/
            # We should verify that the bulk extension is requested
            # Accept it by default now
            if not request.is_bulk:
                safrs.log.warning("Client sent a bulk POST but did not specify the bulk extension")
            for item in data:
                instance = self._create_instance(item)
            resp_data = {}
            location = None
        else:
            instance = self._create_instance(data)
            # object_id is the endpoint parameter, for example "UserId" for a User SAFRSObject
            obj_args = {instance.object_id: instance.jsonapi_id}
            # Retrieve the object json and return it to the client
            resp_data = self.get(**obj_args)
            location = url_for(self.endpoint, **obj_args)

        response = make_response(resp_data, HTTPStatus.CREATED)
        # Set the Location header to the newly created object(s)
        if location:
            response.headers["Location"] = location

        return response

    def _create_instance(self, data):
        """
            Create an instance with the
            :param data: dictionary with {"type": ... , "attributes": ...}
            :return: created instance
        """
        if not isinstance(data, dict):
            raise ValidationError("Data is not a dict object")

        obj_type = data.get("type", None)
        if not obj_type or not obj_type == self.SAFRSObject._s_type:
            raise ValidationError("Invalid type member: {} != {}".format(obj_type, self.SAFRSObject._s_type))

        attributes = data.get("attributes", {})
        # Remove 'id' (or other primary keys) from the attributes, unless it is allowed by the
        # SAFRSObject allow_client_generated_ids attribute
        for col_name in self.SAFRSObject.id_type.column_names:
            attributes.pop(col_name, None)

        # remove attributes that have relationship names
        attributes = {
            attr_name: attributes[attr_name] for attr_name in attributes if attr_name not in self.SAFRSObject._s_relationship_names
        }

        if getattr(self.SAFRSObject, "allow_client_generated_ids", False) is True:
            # todo, this isn't required per the jsonapi spec, doesn't work well and isn't documented, maybe later
            id = data.get("id")
            self.SAFRSObject.id_type.get_pks(id)

        # Create the object instance with the specified id and json data
        # If the instance (id) already exists, it will be updated with the data
        # pylint: disable=not-callable
        instance = self.SAFRSObject(**attributes)

        if not instance._s_auto_commit:
            #
            # The item has not yet been added/commited by the SAFRSBase,
            # in that case we have to do it ourselves
            #
            safrs.DB.session.add(instance)
            try:
                safrs.DB.session.commit()
            except sqlalchemy.exc.SQLAlchemyError as exc:
                # Exception may arise when a db constrained has been violated
                # (e.g. duplicate key)
                safrs.log.warning(str(exc))
                raise GenericError(str(exc))

        return instance

    def delete(self, **kwargs):
        """
            summary: Delete {class_name} from {collection_name}
            responses :
                202 :
                    description: Accepted
                204 :
                    description: Request fulfilled, nothing follows
                200 :
                    description: Success
                403 :
                    description: Forbidden
                404 :
                    description: Not Found

            ---
            Delete an object by id or by filter

            http://jsonapi.org/format/1.1/#crud-deleting:
            Responses :
                202 : Accepted
                If a deletion request has been accepted for processing,
                but the processing has not been completed by the time the server
                responds, the server MUST return a 202 Accepted status code.

                204 No Content
                A server MUST return a 204 No Content status code if a deletion
                request is successful and no content is returned.

                200 OK
                A server MUST return a 200 OK status code if a deletion request
                is successful and the server responds with only top-level meta data.

                404 NOT FOUND
                A server SHOULD return a 404 Not Found status code
                if a deletion request fails due to the resource not existing.
        """
        id = kwargs.get(self.object_id, None)

        if not id:
            # This endpoint shouldn't be exposed so this code is not reachable
            raise ValidationError("", status_code=HTTPStatus.METHOD_NOT_ALLOWED)

        instance = self.SAFRSObject.get_instance(id)
        safrs.DB.session.delete(instance)

        return {}, HTTPStatus.NO_CONTENT


class SAFRSRestRelationshipAPI(Resource):
    """
        Flask webservice wrapper for the underlying sqla relationships db model

        The endpoint url is of the form
        "/Parents/{ParentId}/children/{ChildId}"
        (cfr RELATIONSHIP_URL_FMT in API.expose_relationship)
        where "children" is the relationship attribute of the parent

        3 types of relationships (directions) exist in the sqla orm:
        MANYTOONE ONETOMANY MANYTOMANY

        Following attributes are set on this class:
            - SAFRSObject: the sqla object which has been set with the type
             constructor in expose_relationship
            - parent_class: class of the parent ( e.g. Parent, __tablename__ : Parents )
            - target : class of the child
            - rel_name : name of the relationship ( e.g. children )
            - parent_object_id : url parameter name of the parent ( e.g. {ParentId} )
            - child_object_id : url parameter name of the child ( e.g. {ChildId} )

        http://jsonapi.org/format/#crud-updating-relationships

        Updating To-Many Relationships
        A server MUST respond to PATCH, POST, and DELETE requests to a URL
        from a to-many relationship link as described below.

        For all request types, the body MUST contain a data member
        whose value is an empty array or an array of resource identifier objects.

        If a client makes a PATCH request to a URL from a to-many relationship link,
        the server MUST either completely replace every member of the relationship,
        return an appropriate error response if some resources can not be
        found or accessed, or return a 403 Forbidden response if complete
        replacement is not allowed by the server.
    """

    SAFRSObject = None

    def __new__(cls, *args, **kwargs):
        cls.relationship = cls.SAFRSObject.relationship
        return super().__new__(cls, *args, **kwargs)

    # pylint: disable=unused-argument
    def __init__(self, *args, **kwargs):

        self.parent_class = self.SAFRSObject.relationship.parent.class_
        self.target = self.SAFRSObject.relationship.mapper.class_
        self.rel_name = self.SAFRSObject.relationship.key
        # The object_ids are the ids in the swagger path e.g {FileId}
        self.parent_object_id = self.parent_class.object_id
        self.child_object_id = self.target.object_id

        if self.parent_object_id == self.child_object_id:
            # see expose_relationship: if a relationship consists of
            # two same objects, the object_id should be different (i.e. append "2")
            self.child_object_id += "2"

    # Retrieve relationship data
    def get(self, **kwargs):
        """
            summary : Retrieve {child_name} from {cls.relationship.key}
            description : Retrieve {child_name} items from the {parent_name} {cls.relationship.key} "{direction}" relationship
            ---
            https://jsonapi.org/format/#fetching-relationships

            Retrieve a relationship or list of relationship member ids

            http://jsonapi.org/format/#fetching-relationships-responses :
            A server MUST respond to a successful request to fetch a
            relationship with a 200 OK response.The primary data in the response
            document MUST match the appropriate value for resource linkage.
            The top-level links object MAY contain self and related links,
            as described above for relationship objects.
        """
        parent, relation = self.parse_args(**kwargs)
        child_id = kwargs.get(self.child_object_id)
        errors = {}
        count = 1
        meta = {}
        data = None

        if relation is None:
            # child may have been deleted
            return "Not Found", HTTPStatus.NOT_FOUND
        if child_id:
            safrs.log.warning("Fetching relationship items by path id is deprecated and will be removed")
            child = self.target.get_instance(child_id)
            links = {"self": child._s_url}
            # If {ChildId} is passed in the url, return the child object
            # there's a difference between to-one and -to-many relationships:
            if isinstance(relation, SAFRSBase):
                if child != relation:
                    raise NotFoundError()
            elif child not in relation:
                raise NotFoundError()
            else:
                return jsonify({"data": child, "links": {"self": request.url, "related": child._s_url}})
        # elif type(relation) == self.target: # ==>
        elif self.SAFRSObject.relationship.direction == MANYTOONE:
            data = instance = relation
            links = {"self": request.url}
            if request.url != instance._s_url:
                links["related"] = instance._s_url
            meta.update(dict(instance_meta=instance._s_meta()))
        elif isinstance(relation, sqlalchemy.orm.collections.InstrumentedList):
            instances = [item for item in relation if isinstance(item, SAFRSBase)]
            instances = jsonapi_sort(instances, self.target)
            links, data, count = paginate(instances, self.target)
            count = len(data)
        else:
            instances = jsonapi_sort(relation, self.target)
            links, data, count = paginate(instances, self.target)

        result = jsonapi_format_response(data, meta, links, errors, count)
        return jsonify(result)

    # Relationship patching
    def patch(self, **kwargs):
        """
            summary : Update {cls.relationship.key}
            description : Update the {parent_name} {cls.relationship.key} "{direction}" relationship
            responses:
                200 :
                    description : Accepted
                201 :
                    description: Created
                204 :
                    description : No Content
                403:
                    description : Forbidden
                404 :
                    description : Not Found
                409 :
                    description : Conflict
            ----
            Update or create a relationship child item
            to be used to create or update one-to-many mappings
            but also works for many-to-many etc.

            # Updating To-One Relationships

            http://jsonapi.org/format/#crud-updating-to-one-relationships:
            A server MUST respond to PATCH requests to a URL
            from a to-one relationship link as described below

            The PATCH request MUST include a top-level member named data containing one of:
            a resource identifier object corresponding to the new related resource.
            null, to remove the relationship.
        """
        parent, relation = self.parse_args(**kwargs)
        payload = request.get_jsonapi_payload()
        if not isinstance(payload, dict):
            raise ValidationError("Invalid Object Type")

        data = payload.get("data")
        relation = getattr(parent, self.rel_name)
        obj_args = {self.parent_object_id: parent.jsonapi_id}

        if isinstance(data, dict):
            # https://jsonapi.org/format/#crud-updating-to-one-relationships
            # server MUST respond to PATCH requests to a URL from a to-one relationship link as described below.
            #   The PATCH request MUST include a top-level member named data containing one of:
            #   a resource identifier object corresponding to the new related resource.
            #   null, to remove the relationship.

            if self.SAFRSObject.relationship.direction != MANYTOONE:
                raise GenericError("Provide a list o PATCH a TOMANY relationship")
            child = self._parse_target_data(data)
            setattr(parent, self.rel_name, child)
            obj_args[self.child_object_id] = child.jsonapi_id

        elif isinstance(data, list) and not self.SAFRSObject.relationship.direction == MANYTOONE:
            """
                http://jsonapi.org/format/#crud-updating-to-many-relationships

                If a client makes a PATCH request to a URL from a to-many relationship link,
                the server MUST either completely replace every member of the relationship,
                return an appropriate error response if some resourcescan not be found
                or accessed, or return a 403 Forbidden response if complete
                replacement is not allowed by the server.
            """
            # first remove all items, then append the new items
            # if the relationship has been configured with lazy="dynamic"
            # then it is a subclass of AppenderBaseQuery and
            # we should empty the relationship by setting it to []
            # otherwise it is an instance of InstrumentedList and we have to empty it
            # ( we could loop all items but this is slower for large collections )
            tmp_rel = []
            for child_data in data:
                child = self._parse_target_data(child_data)
                tmp_rel.append(child)

            if isinstance(relation, sqlalchemy.orm.collections.InstrumentedList):
                relation[:] = tmp_rel
            else:
                setattr(parent, self.rel_name, tmp_rel)

        elif data is None and self.SAFRSObject.relationship.direction == MANYTOONE:
            # { data : null } //=> clear the relationship
            child = getattr(parent, self.SAFRSObject.relationship.key)
            if child:
                pass
            setattr(parent, self.rel_name, None)
        else:
            raise ValidationError(
                'Invalid data object type "{}" for this "{}"" relationship'.format(type(data), self.SAFRSObject.relationship.direction)
            )

        if data is None:
            # item removed from relationship => 202 accepted
            # TODO: add response to swagger
            # add meta?
            response = {}, HTTPStatus.ACCEPTED
        else:
            obj_data = self.get(**obj_args)
            response = make_response(obj_data, HTTPStatus.CREATED)
        return response

    # Adding items to a relationship
    def post(self, **kwargs):
        """
            summary: Add {child_name} items to {cls.relationship.key}
            description : Add {child_name} items to the {parent_name} {cls.relationship.key} "{direction}" relationship
            responses :
                202:
                    description : Accepted
                204:
                    description : No Content
                404:
                    description : Not Found
                409:
                    description : Conflict
            ---
            Add a child to a relationship
            202 Accepted
            If a relationship update request has been accepted for processing, but the processing has not
            been completed by the time the server responds, the server MUST return a 202 Accepted status code.

            204 No Content
            A server MUST return a 204 No Content status code if an update is successful and the representation
            of the resource in the request matches the result.
        """
        kwargs["require_child"] = True
        parent, relation = self.parse_args(**kwargs)
        payload = request.get_jsonapi_payload()
        if not isinstance(payload, dict):
            raise ValidationError("Invalid Object Type")
        data = payload.get("data")

        if self.SAFRSObject.relationship.direction == MANYTOONE:
            # https://jsonapi.org/format/#crud-updating-to-one-relationships
            # We should only use patch to update a relationship
            child_data = data
            if isinstance(child_data, list):
                raise ValidationError(
                    """
                    Invalid data payload: MANYTOONE relationship can only hold a single item,
                    please provide a dictionary object
                    """,
                    HTTPStatus.FORBIDDEN,
                )
            if child_data:
                child = self._parse_target_data(child_data)
                # result = [child]

        else:  # direction is TOMANY => append the items to the relationship
            for child_data in data:
                child = self._parse_target_data(child_data)
                if child not in relation:
                    relation.append(child)
            # result = [child for child in relation]

        # we can return result too but it's not necessary per the spec
        return {}, 204

    def delete(self, **kwargs):
        """
            summary : Delete {child_name} from {cls.relationship.key}
            description : Delete {child_name} items from the {parent_name} {cls.relationship.key} "{direction}" relationship
            responses:
                202 :
                    description: Accepted
                204 :
                    description: Request fulfilled, nothing follows
                200 :
                    description: Success
                403 :
                    description: Forbidden
                404 :
                    description: Not Found
            ----
            Remove an item from a relationship
        """
        kwargs["require_child"] = True
        # pylint: disable=unused-variable
        # (parent is unused)
        parent, relation = self.parse_args(**kwargs)

        # No child id=> delete specified items from the relationship
        payload = request.get_jsonapi_payload()
        if not isinstance(payload, dict):
            raise ValidationError("Invalid Object Type")
        data = payload.get("data")

        if self.SAFRSObject.relationship.direction == MANYTOONE:
            # https://jsonapi.org/format/#crud-updating-to-one-relationships
            # We should only use patch to update
            # previous versions incorrectly implemented the jsonapi spec for updating manytoone relationships
            # keep things backwards compatible for now
            child = data
            if isinstance(data, list):
                if data and isinstance(data[0], dict):
                    # invalid, try to fix it by deleting the firs item from the list
                    safrs.log.warning("Invalid Payload to delete from MANYTOONE relationship")
                    data = data[0]
                else:
                    raise ValidationError("Invalid data payload")
            child_id = data.get("id", None)
            child_type = data.get("type", None)

            if not child_id or not child_type:
                raise ValidationError("Invalid data payload", HTTPStatus.FORBIDDEN)

            if child_type != self.target._s_type:
                raise ValidationError("Invalid type", HTTPStatus.FORBIDDEN)

            child = self.target.get_instance(child_id)
            if child == relation and getattr(parent, self.rel_name, None) == child:
                # Delete the item from the many-to-one relationship
                delattr(parent, self.rel_name)
            else:
                safrs.log.warning("child not in relation")

        else:
            # https://jsonapi.org/format/#crud-updating-to-many-relationships
            children = data
            if not isinstance(data, list) or not children:
                raise ValidationError("Invalid data payload")
            for child in children:
                child_id = child.get("id", None)
                child_type = child.get("type", None)

                if not child_id or not child_type:
                    raise ValidationError("Invalid data payload", HTTPStatus.FORBIDDEN)

                if child_type != self.target._s_type:
                    raise ValidationError("Invalid type", HTTPStatus.FORBIDDEN)

                child = self.target.get_instance(child_id)
                if child in relation:
                    relation.remove(child)
                else:
                    safrs.log.warning("Item with id {} not in relation".format(child_id))

        return {}, HTTPStatus.NO_CONTENT

    def parse_args(self, **kwargs):
        """
            Parse relationship args
            An error is raised if the parent doesn't exist.
            An error is raised if the child doesn't exist and the
            "require_child" argument is set in kwargs,

            :return: parent, child, relation
        """
        parent_id = kwargs.get(self.parent_object_id, None)
        if parent_id is None:
            raise ValidationError("Invalid Parent Id")

        parent = self.parent_class.get_instance(parent_id)
        relation = getattr(parent, self.rel_name)

        return parent, relation


class SAFRSJSONRPCAPI(Resource):
    """
        Route wrapper for the underlying SAFRSBase jsonapi_rpc

        Only HTTP POST is supported
    """

    SAFRSObject = None  # Flask views will need to set this to the SQLAlchemy safrs.DB.Model class
    method_name = None

    def __init__(self, *args, **kwargs):
        """
            -object_id is the function used to create the url parameter name
            (eg "User" -> "UserId" )
            -this parameter is used in the swagger endpoint spec,
            eg. /Users/{UserId} where the UserId parameter is the id of the underlying SAFRSObject.
        """
        self.object_id = self.SAFRSObject.object_id
        self.target = self.SAFRSObject

    def post(self, **kwargs):
        """
            summary : call             
            responses :
                403:
                    description :
                201:
                    description: Created
                202:
                    description : Accepted
                403 :
                    description : Forbidden
                404:
                    description : Not Found
                409:
                    description : Conflict
            ---
            HTTP POST: apply actions, return 200 regardless.
            The actual jsonapi_rpc method may return other codes
        """
        id = kwargs.get(self.object_id, None)

        if id is not None:
            instance = self.SAFRSObject.get_instance(id)
            if not instance:
                # If no instance was found this means the user supplied
                # an invalid ID
                raise ValidationError("Invalid ID")

        else:
            # No ID was supplied, apply method to the class itself
            instance = self.SAFRSObject

        method = getattr(instance, self.method_name, None)

        if not method:
            # Only call methods for Campaign and not for superclasses (e.g. safrs.DB.Model)
            raise ValidationError('Invalid method "{}"'.format(self.method_name))
        if not is_public(method):
            raise ValidationError("Method is not public")

        args = dict(request.args)
        payload = request.get_jsonapi_payload()
        if payload:
            args = payload.get("meta", {}).get("args", {})

        safrs.log.debug("method {} args {}".format(self.method_name, args))
        result = method(**args)

        if isinstance(result, SAFRSFormattedResponse):
            response = result
        else:
            response = {"meta": {"result": result}}

        return jsonify(response)  # 200 : default

    def get(self, **kwargs):
        """
            responses :
                404 :
                    description : Not Found
                403 :
                    description : Forbidden

            ---
        """
        id = kwargs.get(self.object_id, None)

        if id is not None:
            instance = self.SAFRSObject.get_instance(id)
            if not instance:
                # If no instance was found this means the user supplied
                # an invalid ID
                raise ValidationError("Invalid ID")

        else:
            # No ID was supplied, apply method to the class itself
            instance = self.SAFRSObject

        method = getattr(instance, self.method_name, None)

        if not method:
            # Only call methods for Campaign and not for superclasses (e.g. safrs.DB.Model)
            raise ValidationError('Invalid method "{}"'.format(self.method_name))
        if not is_public(method):
            raise ValidationError("Method is not public")

        args = dict(request.args)
        safrs.log.debug("method {} args {}".format(self.method_name, args))
        result = method(**args)

        if isinstance(result, SAFRSFormattedResponse):
            response = result
        else:
            response = {"meta": {"result": result}}

        return jsonify(response)  # 200 : default


# pylint: disable=too-few-public-methods
class SAFRSRelationship:
    """
        Relationship object, used to emulate a SAFRSBase object for the swagger for relationship targets
    """

    _s_class_name = None
    __name__ = "name"

    @classmethod
    def get_swagger_doc(cls, http_method):
        """
            Create a swagger api model based on the sqlalchemy schema
            if an instance exists in the DB, the first entry is used as example
        """
        body = {}
        responses = {}
        object_name = cls.__name__

        object_model = {}
        responses = {str(HTTPStatus.OK.value): {"description": "{} object".format(object_name), "schema": object_model}}

        if http_method.upper() in ("POST", "GET"):
            responses = {
                str(HTTPStatus.OK.value): {"description": HTTPStatus.OK.description},
                str(HTTPStatus.NOT_FOUND.value): {"description": HTTPStatus.NOT_FOUND.description},
            }

        return body, responses

    @classproperty
    def _s_relationship_names(cls):
        return cls._target._s_relationship_names

    @classproperty
    def _s_jsonapi_attrs(cls):
        return cls._target._s_relationship_names

    @classproperty
    def _s_type(cls):
        return cls._target._s_type

    @classproperty
    def _s_column_names(cls):
        return cls._target._s_column_names

    @classproperty
    def _s_class_name(cls):
        return cls._target.__name__
