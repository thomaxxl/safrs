# -*- coding: utf-8 -*-
#
# This module defines jsonapi-related "Resource" objects:
# - SAFRSRestAPI for exposed database objects
# - SAFRSRestRelationshipAPI for exposed database relationships
# - SAFRSRestMethodAPI for exposed jsonapi_rpc methods
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
import re
import sqlalchemy
import sqlalchemy.orm.dynamic
import sqlalchemy.orm.collections
from sqlalchemy.orm.interfaces import MANYTOONE
from flask import make_response, url_for
from flask import jsonify, request
from flask_restful.utils import cors
from flask_restful_swagger_2 import Resource
import safrs
from .db import SAFRSBase
from .swagger_doc import is_public
from .errors import ValidationError, GenericError, NotFoundError
from .config import get_config
from .json_encoder import SAFRSFormattedResponse
from urllib.parse import urlparse

INCLUDE_ALL = "+all"


def get_legacy(param, default=0):
    """
        retrieve request parameters
        Used for backwards compatibility (with safrs < 2.x)
        :param param: parameter to retrieve
        :param default:
        :return: prequest parameter or None
    """
    result = getattr(request, param, None)
    if result is None:
        safrs.log.error(
            'Legacy Request parameter "{}", consider upgrading'.format(param)
        )
        result = default
    return result

# results for GET requests will go through filter -> sort -> paginate
def jsonapi_filter(safrs_object):
    """
        Apply the request.args filters to the object
        :parameter safrs_object:
        :return: a sqla query object
    """
    
    # First check if a filter= URL query parameter has been used
    filter_args = get_legacy('filter')
    if filter_args:
        result = safrs_object._s_filter(filter_args)
        return result
    
    filtered = []
    filters = get_legacy("filters", {})
    for col_name, val in filters.items():
        if not col_name in safrs_object._s_column_names:
            safrs.log.warning("Invalid Column {}".format(col_name))
            continue
        column = getattr(safrs_object, col_name)
        filtered.append(safrs_object.query.filter(column.in_(val.split(","))))

    if filtered:
        result = filtered[0].union_all(*filtered).distinct()
    else:
        result = safrs_object.query

    return result


def jsonapi_sort(object_query, safrs_object):
    """
        http://jsonapi.org/format/#fetching-sorting
        sort by csv sort= values
    """
    sort_columns = request.args.get("sort", None)
    if not sort_columns is None:
        for sort_column in sort_columns.split(","):
            if sort_column.startswith("-"):
                attr = getattr(safrs_object, sort_column[1:], None).desc()
                object_query = object_query.order_by(attr)
            else:
                attr = getattr(safrs_object, sort_column, None)
                object_query = object_query.order_by(attr)

    return object_query


def paginate(object_query, SAFRSObject=None):
    """
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

        :parameter object_query: SQLAalchemy query object
        :prameter SAFRSObject: optional
        :return: links, instances, count
    """

    def get_link(count, limit):
        result = SAFRSObject._s_url if SAFRSObject else ""
        result += "?" + "&".join(
            ["{}={}".format(k, v) for k, v in request.args.items()]
            + ["page[offset]={}&page[limit]={}".format(count, limit)]
        )
        return result

    page_offset = get_legacy("page_offset")
    limit = get_legacy("page_limit", get_config("MAX_PAGE_LIMIT"))
    page_base = int(page_offset / limit) * limit

    # Counting may take > 1s for a table with millions of records, depending on the storage engine :|
    # Make it configurable
    # With mysql innodb we can use following to retrieve the count:
    # select TABLE_ROWS from information_schema.TABLES where TABLE_NAME = 'TableName';
    #
    if (
        SAFRSObject is None
    ):  # for backwards compatibility, ie. when not passed as an arg to paginate()
        count = object_query.count()
    else:
        count = SAFRSObject._s_count()
    if count is None:
        count = object_query.count()

    first_args = (0, limit)
    last_args = (int(int(count / limit) * limit), limit)  # round down
    self_args = (page_base if page_base <= last_args[0] else last_args[0], limit)
    next_args = (
        (page_offset + limit, limit)
        if page_offset + limit <= last_args[0]
        else last_args
    )
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

    res_query = object_query.offset(page_offset).limit(limit)
    instances = res_query.all()
    return links, instances, count


def get_included(data, limit, include="", level=0):
    """
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
        for included in [
            get_included(obj, limit, include, level=level + 1) for obj in data
        ]:
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
            if included and isinstance(included, SAFRSBase) and not included in result:
                # convert single instance to a list so we can generically add the includes
                included = [included]
            elif isinstance(included, sqlalchemy.orm.collections.InstrumentedList):
                pass
            elif not included or included in result:
                continue
            try:
                # This works on sqlalchemy.orm.dynamic.AppenderBaseQuery
                included = included[:limit]
                result = result.union(included)
            except Exception as exc:
                safrs.log.critical(
                    "Failed to add included for {} (included: {} - {})".format(
                        relationship, type(included), included
                    )
                )
                result.add(included)

        if INCLUDE_ALL in includes:
            for nested_included in [
                get_included(result, limit, level=level + 1) for obj in result
            ]:  # Removed recursion with get_included(result, limit, INCLUDE_ALL)
                result = result.union(nested_included)

        elif nested_rel:
            for nested_included in [
                get_included(result, limit, nested_rel, level=level + 1)
                for obj in result
            ]:
                result = result.union(nested_included)

    return result


def jsonapi_format_response(data, meta=None, links=None, errors=None, count=None):
    """
    Create a response dict according to the json:api schema spec
    :param data : the objects that will be serialized
    :return: jsonapi formatted dictionary
    """

    limit = get_legacy("page_limit", get_config("MAX_PAGE_LIMIT"))
    try:
        limit = int(limit)
    except ValueError:
        raise ValidationError("page[limit] error")
    meta["limit"] = limit
    meta["count"] = count

    jsonapi = dict(version="1.0")
    included = list(
        get_included(
            data,
            limit,
            include=request.args.get("include", safrs.SAFRS.DEFAULT_INCLUDED),
        )
    )
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

    SAFRSObject = (
        None
    )  # Flask views will need to set this to the SQLAlchemy safrs.DB.Model class
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

    def get(self, **kwargs):
        """
            responses :
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
            ---
            Create or update the object specified by id
        """
        id = kwargs.get(self.object_id, None)
        if not id:
            raise ValidationError("Invalid ID")

        req_json = request.get_jsonapi_payload()
        if not isinstance(req_json, dict):
            raise ValidationError("Invalid Object Type")

        data = req_json.get("data")

        if not data or not isinstance(data, dict):
            raise ValidationError("Invalid Data Object")

        # Check that the id in the body is equal to the id in the url
        body_id = data.get("id", None)
        if body_id is None or self.SAFRSObject.id_type.validate_id(
            id
        ) != self.SAFRSObject.id_type.validate_id(body_id):
            raise ValidationError("Invalid ID")

        attributes = data.get("attributes", {})
        attributes["id"] = id
        # Create the object instance with the specified id and json data
        # If the instance (id) already exists, it will be updated with the data
        instance = self.SAFRSObject.get_instance(id)
        if not instance:
            raise ValidationError("Invalid ID")
        instance._s_patch(**attributes)

        # object id is the endpoint parameter, for example "UserId" for a User SAFRSObject
        obj_args = {instance.object_id: instance.jsonapi_id}
        # Retrieve the object json and return it to the client
        obj_data = self.get(**obj_args)
        response = make_response(obj_data, 201)
        # Set the Location header to the newly created object
        response.headers["Location"] = url_for(self.endpoint, **obj_args)
        return response

    def post(self, **kwargs):
        """
            responses :
                403:
                    description : This implementation does not accept client-generated IDs
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
            # "A server MUST return 403 Forbidden in response to an
            # unsupported request to create a resource with a client-generated ID"
            response = {"meta": {"error": "Unsupported JSONAPI Request"}}, 403
            return response

        else:
            # Create a new instance of the SAFRSObject
            data = payload.get("data")
            if data is None:
                raise ValidationError("Request contains no data")
            if not isinstance(data, dict):
                raise ValidationError("data is not a dict object")

            obj_type = data.get("type", None)
            if not obj_type:  # or type..
                raise ValidationError("Invalid type member")

            attributes = data.get("attributes", {})
            # Remove 'id' (or other primary keys) from the attributes, unless it is allowed by the
            # SAFRSObject allow_client_generated_ids attribute
            for col_name in [c.name for c in self.SAFRSObject.id_type.columns]:
                attributes.pop(col_name, None)

            if getattr(self.SAFRSObject, "allow_client_generated_ids", False) is True:
                # todo, this isn't required per the jsonapi spec, doesn't work well and isn't documented, maybe later
                id = data.get("id")
                self.SAFRSObject.id_type.get_pks(id)

            # Create the object instance with the specified id and json data
            # If the instance (id) already exists, it will be updated with the data
            # pylint: disable=not-callable
            instance = self.SAFRSObject(**attributes)

            if not instance.db_commit:
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

            # object_id is the endpoint parameter, for example "UserId" for a User SAFRSObject
            obj_args = {instance.object_id: instance.jsonapi_id}
            # Retrieve the object json and return it to the client
            obj_data = self.get(**obj_args)
            response = make_response(obj_data, 201)
            # Set the Location header to the newly created object
            response.headers["Location"] = url_for(self.endpoint, **obj_args)

        return response

    def delete(self, **kwargs):
        """
            responses:
                202 :
                    description: Accepted
                204 :
                    description: No Content
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

        if id:
            instance = self.SAFRSObject.get_instance(id)
            safrs.DB.session.delete(instance)
        else:
            raise NotFoundError(id, status_code=404)

        return jsonify({})

    def call_method_by_name(self, instance, method_name, args):
        """
            Call the instance method specified by method_name
        """

        method = getattr(instance, method_name, False)

        if not method:
            # Only call methods for Campaign and not for superclasses (e.g. safrs.DB.Model)
            raise ValidationError('Invalid method "{}"'.format(method_name))
        if not is_public(method):
            raise ValidationError("Method is not public")

        if not args:
            args = {}

        result = method(**args)
        return result

    def get_instances(self, filter, method_name, sort, search=""):
        """
            Get all instances. Subclasses may want to override this
            (for example to sort results)
        """

        if method_name:
            method(**args)

        instances = self.SAFRSObject.query.filter_by(**filter).order_by(None)

        return instances


class SAFRSRestMethodAPI(Resource):
    """
        Route wrapper for the underlying SAFRSBase jsonapi_rpc

        Only HTTP POST is supported
    """

    SAFRSObject = (
        None
    )  # Flask views will need to set this to the SQLAlchemy safrs.DB.Model class
    method_name = None

    def __init__(self, *args, **kwargs):
        """
            -object_id is the function used to create the url parameter name
            (eg "User" -> "UserId" )
            -this parameter is used in the swagger endpoint spec,
            eg. /Users/{UserId} where the UserId parameter is the id of the underlying SAFRSObject.
        """
        self.object_id = self.SAFRSObject.object_id

    def post(self, **kwargs):
        """
            responses :
                403:
                    description : 
                201:
                    description: Created
                202:
                    description : Accepted
                404:
                    description : Not Found
                409:
                    description : Conflict
            ---
            HTTP POST: apply actions, return 200 regardless
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
        json_data = request.get_jsonapi_payload()
        if json_data:
            args = json_data.get("meta", {}).get("args", {})

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

        response = {"meta": {"result": result}}

        return jsonify(response)  # 200 : default


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
            - child_class : class of the child
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

    # pylint: disable=unused-argument
    def __init__(self, *args, **kwargs):

        self.parent_class = self.SAFRSObject.relationship.parent.class_
        self.child_class = self.SAFRSObject.relationship.mapper.class_
        self.rel_name = self.SAFRSObject.relationship.key
        # The object_ids are the ids in the swagger path e.g {FileId}
        self.parent_object_id = self.parent_class.object_id
        self.child_object_id = self.child_class.object_id

        if self.parent_object_id == self.child_object_id:
            # see expose_relationship: if a relationship consists of
            # two same objects, the object_id should be different (i.e. append "2")
            self.child_object_id += "2"

    def get(self, **kwargs):
        """
            ---
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

        if child_id:
            child = self.child_class.get_instance(child_id)
            # If {ChildId} is passed in the url, return the child object
            # there's a difference between to-one and -to-many relationships:
            if isinstance(relation, SAFRSBase):
                result = [child]
            elif child in relation:
                # item is in relationship, return the child
                result = [child]
            else:
                return "Not Found", 404
        # elif type(relation) == self.child_class: # ==>
        elif self.SAFRSObject.relationship.direction == MANYTOONE:
            data = instance = relation
            meta = {"direction": "TOONE"}
            links = {"self": instance._s_url}
            if request.url != instance._s_url:
                links["related"] = request.url
            count = 1
            meta.update(dict(instance_meta=instance._s_meta()))

        else:
            # No {ChildId} given:
            # return a list of all relationship items
            data = [item for item in relation if isinstance(item, SAFRSBase)]
            meta = {"direction": "TOMANY"}
            instances = jsonapi_filter(self.child_class)
            instances = jsonapi_sort(instances, self.child_class)
            links, data, count = paginate(instances, self.child_class)

        result = jsonapi_format_response(data, meta, links, errors, count)
        return jsonify(result)

    # Relationship patching
    def patch(self, **kwargs):
        """
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
        json_reponse = request.get_jsonapi_payload()
        if not isinstance(json_reponse, dict):
            raise ValidationError("Invalid Object Type")

        data = json_reponse.get("data")
        relation = getattr(parent, self.rel_name)
        obj_args = {self.parent_object_id: parent.jsonapi_id}

        if isinstance(data, dict):
            # => Update TOONE Relationship
            # TODO!!!
            if self.SAFRSObject.relationship.direction != MANYTOONE:
                raise GenericError(
                    "To PATCH a TOMANY relationship you should provide a list"
                )
            child = self.child_class.get_instance(data.get("id", None))
            setattr(parent, self.rel_name, child)
            obj_args[self.child_object_id] = child.jsonapi_id

        elif isinstance(data, list):
            """
                http://jsonapi.org/format/#crud-updating-to-many-relationships

                If a client makes a PATCH request to a URL from a to-many relationship link,
                the server MUST either completely replace every member of the relationship,
                return an appropriate error response if some resourcescan not be found
                or accessed, or return a 403 Forbidden response if complete
                replacement is not allowed by the server.
            """
            if self.SAFRSObject.relationship.direction == MANYTOONE:
                raise GenericError(
                    "To PATCH a MANYTOONE relationship you \
                should provide a dictionary instead of a list"
                )
            # first remove all items, then append the new items
            # if the relationship has been configured with lazy="dynamic"
            # then it is a subclass of AppenderBaseQuery and
            # we should empty the relationship by setting it to []
            # otherwise it is an instance of InstrumentedList and we have to empty it
            # ( we could loop all items but this is slower for large collections )
            tmp_rel = []
            for child in data:
                if not isinstance(child, dict):
                    raise ValidationError("Invalid data object")
                child_instance = self.child_class.get_instance(child["id"])
                tmp_rel.append(child_instance)

            if isinstance(relation, sqlalchemy.orm.collections.InstrumentedList):
                relation[:] = tmp_rel
            else:
                setattr(parent, self.rel_name, tmp_rel)

        elif data is None:
            # { data : null } //=> clear the relationship
            if self.SAFRSObject.relationship.direction == MANYTOONE:
                child = getattr(parent, self.SAFRSObject.relationship.key)
                if child:
                    pass
                setattr(parent, self.rel_name, None)
            else:
                #
                # should we allow this??
                # maybe we just want to raise an error here ...???
                setattr(parent, self.rel_name, [])
        else:
            raise ValidationError("Invalid Data Object Type")

        if data is None:
            # item removed from relationship => 202 accepted
            # TODO: add response to swagger
            # add meta?

            response = {}, 200
        else:
            obj_data = self.get(**obj_args)
            # Retrieve the object json and return it to the client
            response = make_response(obj_data, 201)
            # Set the Location header to the newly created object
            # todo: set location header
            # response.headers['Location'] = url_for(self.endpoint, **obj_args)
        return response

    def post(self, **kwargs):
        """
            responses :
                403:
                    description : This implementation does not accept client-generated IDs
                201:
                    description: Created
                202:
                    description : Accepted
                404:
                    description : Not Found
                409:
                    description : Conflict
            ---
            Add a child to a relationship
        """
        errors = []
        kwargs["require_child"] = True
        parent, relation = self.parse_args(**kwargs)

        json_response = request.get_jsonapi_payload()
        if not isinstance(json_response, dict):
            raise ValidationError("Invalid Object Type")
        data = json_response.get("data")

        if self.SAFRSObject.relationship.direction == MANYTOONE:
            # pylint: disable=len-as-condition
            if len(data) == 0:
                setattr(parent, self.SAFRSObject.relationship.key, None)
            if len(data) > 1:
                raise ValidationError(
                    "Too many items for a MANYTOONE relationship", 403
                )
            child_id = data[0].get("id")
            child_type = data[0].get("type")
            if not child_id or not child_type:
                raise ValidationError("Invalid data payload", 403)

            if child_type != self.child_class.__name__:
                raise ValidationError("Invalid type", 403)

            child = self.child_class.get_instance(child_id)
            setattr(parent, self.SAFRSObject.relationship.key, child)
            result = [child]

        else:  # direction is TOMANY => append the items to the relationship
            for item in data:
                if not isinstance(json_response, dict):
                    raise ValidationError("Invalid data type")
                child_id = item.get("id", None)
                if child_id is None:
                    errors.append("no child id {}".format(data))
                    safrs.log.error(errors)
                    continue
                child = self.child_class.get_instance(child_id)

                if not child:
                    errors.append("invalid child id {}".format(child_id))
                    safrs.log.error(errors)
                    continue
                if not child in relation:
                    relation.append(child)
            result = [item for item in relation]

        return jsonify({"data": result})

    def delete(self, **kwargs):
        """
            responses:
                202 :
                    description: Accepted
                204 :
                    description: No Content
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
        child_id = kwargs.get(self.child_object_id, None)
        child = self.child_class.get_instance(child_id)
        if child in relation:
            relation.remove(child)
        else:
            safrs.log.warning("Child not in relation")

        return jsonify({})

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
