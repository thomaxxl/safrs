from collections.abc import Mapping
from typing import Any, Callable, Optional, cast
#  This file contains jsonapi-related flask-restful "Resource" objects:
#  - SAFRSRestAPI for exposed database instances and collections
#  - SAFRSRestRelationshipAPI for exposed database relationships
#  - SAFRSRestMethodAPI for exposed jsonapi_rpc methods
#
# Configuration parameters:
# - endpoint
#
# to do:
# - expose canonical endpoints
# - move all swagger formatting to swagger_doc
#
# Some linting errors to ignore
# pylint: disable=redefined-builtin,invalid-name, line-too-long, protected-access, no-member, too-many-lines
# pylint: disable=fixme, logging-format-interpolation
#
import safrs
import sqlalchemy
import sqlalchemy.orm.dynamic
import sqlalchemy.orm.collections
from flask import current_app, jsonify, make_response as flask_make_response, url_for, request
from flask_restful_swagger_2 import Resource as FRSResource
from http import HTTPStatus
from sqlalchemy.orm.interfaces import MANYTOONE, MANYTOMANY
from urllib.parse import urljoin
from .api_doc import is_public
from . import base as _safrs_base
from .errors import ValidationError, NotFoundError, UnAuthorizedError
from .jsonapi_attr import jsonapi_attr_is_write_only
from .jsonapi_formatting import jsonapi_filter_query, jsonapi_filter_list, jsonapi_sort, jsonapi_format_response, paginate
from .jsonapi_filters import get_swagger_filters
from .rpc import bind_rpc_kwargs, normalize_rpc_result, parse_rpc_args
from .config import get_config
from .request import validate_json_payload


def make_response(*args: Any, **kwargs: Any) -> Any:
    """
    Customized flask-restful make_response
    """
    response = flask_make_response(*args, **kwargs)
    if cast(Any, request).is_jsonapi:
        # Only use "application/vnd.api+json" if the client sent this with the request
        response.headers["Content-Type"] = "application/vnd.api+json"
    return response


def _rpc_jsonapi_doc(data: Any = None, errors: Any = None, included: Any = None, meta: Any = None) -> Any:
    """
    Build a minimal JSON:API document for RPC result normalization.
    """
    doc: dict[str, Any] = {"jsonapi": {"version": "1.0"}}
    if data is not None:
        doc["data"] = data
    if errors is not None:
        doc["errors"] = errors
    if included is not None:
        doc["included"] = included
    if meta is not None:
        doc["meta"] = meta
    return doc


def _rpc_query_items() -> list[tuple[str, Any]]:
    try:
        return list(cast(Any, request).args.items(multi=True))
    except TypeError:
        return list(cast(Any, request).args.items())


def _build_location_header(endpoint: str, instance: Any) -> str:
    """
    Build a location header for a newly created instance.

    Use `url_for` with route params so Flask percent-encodes unsafe path bytes
    (e.g. CR/LF from client-generated IDs) instead of emitting invalid header values.
    """
    object_id = getattr(instance, "_s_object_id", None)
    if object_id is None:
        return str(url_for(endpoint))
    return str(url_for(endpoint, **{object_id: instance.jsonapi_id}))


def _validate_collection_size(data: Any, label: str) -> None:
    """Bound attacker-controlled bulk and relationship arrays."""
    if not isinstance(data, list):
        return
    configured_max = get_config("MAX_BULK_ITEMS")
    max_items = int(
        configured_max if configured_max is not None else safrs.SAFRS.MAX_BULK_ITEMS
    )
    if max_items > 0 and len(data) > max_items:
        raise ValidationError(f"{label} exceeds maximum item count {max_items}")


class Resource(FRSResource):
    """
    Superclass for the exposed endpoints
    * Collections and instances : SAFRSRestAPI
    * Relationships : SAFRSRestRelationshipAPI
    * RPC methods : SAFRSJSONRPCAPI
    """

    # SAFRSObject: the class that will be returned when a http method is invoked
    # Flask views will need to set this to the SQLAlchemy safrs.DB.Model class
    SAFRSObject = None
    # relationship target in SAFRSRestRelationshipAPI, identical to self.SAFRSObject in SAFRSRestAPI
    target = None
    # Swagger filter spec
    get_swagger_filters = get_swagger_filters

    def head(self: Any, *args: Any, **kwargs: Any) -> Any:
        """
        HTTP HEAD
        """
        _super = super()
        if hasattr(_super, "head"):
            response = _super.head(*args, **kwargs)
        else:
            response = make_response()
        return response

    def options(self: Any, *args: Any, **kwargs: Any) -> Any:
        """
        HTTP OPTIONS
        """
        _super = super()
        if hasattr(_super, "options"):
            response = _super.options(*args, **kwargs)
        else:
            response = make_response()
        return response

    def _run_read_authorized(self: Any, callback: Callable[[], Any]) -> Any:
        """Authorize a representation returned from a non-GET operation.

        Model and relationship decorators are already embedded in ``self.get``.
        Flask-RESTful mapping decorators are normally applied only by request
        dispatch, so internal POST/PATCH calls must apply the mapping's GET
        policy explicitly before serializing a resource.
        """
        method_decorators = getattr(self, "method_decorators", [])
        if not isinstance(method_decorators, Mapping):
            return callback()

        callback.__name__ = "get"
        setattr(callback, "SAFRSObject", self.SAFRSObject)
        decorated_callback = callback
        for decorator in list(method_decorators.get("get", []) or []):
            decorated_callback = decorator(decorated_callback)
        return decorated_callback()

    def _parse_target_data(self: Any, target_data: Any, action: str = "link") -> Any:
        """
        Validate the jsonapi payload for patch requests (to self.target):
        - the payload must contain "id" and "type" keys.
        - the type must match the target type
        - an object with the specified id must exist
        - the target's object-level policy (SEC-02) must allow the row

        :param target_data: jsonapi instance payload
        :param action: relationship operation for the object-level policy
        :return: sqla/safrs orm instance
        """
        if not isinstance(target_data, dict):
            raise ValidationError("Invalid relationship data type")
        target_id = target_data.get("id", None)
        if target_id is None:
            raise ValidationError("Missing relationship target id")
        target_type = target_data.get("type")
        if not target_id:
            raise ValidationError("Invalid id in data", HTTPStatus.FORBIDDEN)
        if not target_type:
            raise ValidationError("Invalid type in data", HTTPStatus.FORBIDDEN)
        if target_type != self.target._s_type:
            raise ValidationError("Invalid relationship target type", HTTPStatus.FORBIDDEN)
        target = self.target.get_instance(target_id)
        if not target:
            raise ValidationError("Invalid relationship target id")
        _safrs_base.run_instance_access_check(self.target, target, action)
        return target

    @classmethod
    def get_swagger_include(cls: Any) -> Any:
        """
        :return: JSON:API "include" query string swagger spec
        """
        default_include = ",".join(cls.SAFRSObject._s_relationships.keys())
        include_description = f"{cls.SAFRSObject._s_class_name} relationships to include (csv)"
        if default_include:
            include_description = (
                f"{cls.SAFRSObject._s_class_name} relationships to include (csv, ex.: {default_include})"
            )

        param = {
            "default": default_include,
            "type": "string",
            "name": "include",
            "in": "query",
            "format": "string",
            "required": False,
            "description": include_description,
        }
        return param

    @classmethod
    def get_swagger_fields(cls: Any) -> Any:
        """
        :return: JSON:API fields[] swagger spec (the model instance fields to be included)
        """
        attr_list = [
            attr_name
            for attr_name, attr in cls.SAFRSObject._s_jsonapi_attrs.items()
            if not jsonapi_attr_is_write_only(attr)
        ]
        # Add the fields query string swagger
        # todo: get the columns of the target
        param = {
            "default": ",".join(attr_list),
            "type": "string",
            "name": f"fields[{cls.SAFRSObject._s_class_name}]",
            "in": "query",
            "format": "string",
            "required": False,
            "description": f"{cls.SAFRSObject._s_class_name} fields to include (csv)",
        }
        return param

    @classmethod
    def get_swagger_sort(cls: Any) -> Any:
        """
        :return: JSON:API sort swagger spec (the collection sort key)
        """
        attr_list = ["id"]
        for attr_name, col in cls.SAFRSObject._s_jsonapi_attrs.items():
            # only use string or numbers for sortable examples in the swagger
            # other column datatypes may not be sortable
            if getattr(col, "type", None) in [sqlalchemy.String, sqlalchemy.Integer]:
                attr_list.append(attr_name)

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

    def __init__(self: Any, *args: Any, **kwargs: Any) -> None:
        """
        - object_id is the function used to create the url parameter name
        (eg "User" -> "UserId" )
        - this parameter is used in the swagger endpoint spec,
        eg. /Users/{UserId} where the UserId parameter is the id of
        the underlying SAFRSObject.
        """
        self._s_object_id = self.SAFRSObject._s_object_id
        self.target = self.SAFRSObject

    def get(self: Any, **kwargs: Any) -> Any:
        """
        summary : Retrieve {class_name} instance
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

        id is specified by self._s_object_id, f.i. {UserId}

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

        if self._s_object_id in kwargs:
            # Retrieve a single instance
            id = kwargs[self._s_object_id]
            instance = self.SAFRSObject.get_instance(id)
            if instance is not None:
                # SEC-02: object-level policies apply to direct reads too.
                _safrs_base.run_instance_access_check(self.SAFRSObject, instance, "read")
            data = instance
            count = 1
            if instance is not None:
                links = {"self": instance._s_url}
                if request.full_path.strip("?").strip("/") != instance._s_url.strip("?").strip("/"):
                    links["related"] = urljoin(instance._s_url_root, request.full_path)
                meta.update(dict(instance_meta=instance._s_meta()))
        else:
            # retrieve a collection, filter and sort
            instances = self.SAFRSObject._s_get()
            instances = _safrs_base.authorize_collection_before_metadata(self.SAFRSObject, instances)
            instances = jsonapi_sort(instances, self.SAFRSObject)
            links, data, count = paginate(instances, self.SAFRSObject)

        # format the response: add the included objects
        result = jsonapi_format_response(data, meta, links, errors, count)
        return jsonify(result)

    def patch(self: Any, **kwargs: Any) -> Any:
        """
        summary : Update {class_name}
        description: Update {class_name} attributes
        responses:
            200 :
                description : Request fulfilled, document follows
            202 :
                description : Accepted
            204 :
                description : No Content
            403:
                description : Forbidden
            404 :
                description : Not Found
            409 :
                description : Conflict
        ---
        https://jsonapi.org/format/#crud-updating-responses
        Update the object with the specified id
        """
        id = kwargs.get(self._s_object_id, None)

        payload = cast(Any, request).get_jsonapi_payload()
        if not isinstance(payload, dict):
            raise ValidationError("Invalid Object Type")

        data = payload.get("data")
        if id is None and isinstance(data, list):
            # Bulk patch request
            _validate_collection_size(data, "Bulk PATCH")
            for item in data:
                if not isinstance(item, dict):
                    raise ValidationError("Invalid Data Object")
                instance = self._patch_instance(item)
            response = make_response(jsonify({}), HTTPStatus.ACCEPTED)

        elif not data or not isinstance(data, dict):
            raise ValidationError("Invalid Data Object")
        elif id is None:
            raise ValidationError("Invalid ID")
        else:
            instance = self._patch_instance(data, id)
            # object id is the endpoint parameter, for example "UserId" for a User SAFRSObject
            obj_args = {instance._s_object_id: instance.jsonapi_id}
            # Retrieve the jsonapi encoded object and return it to the client
            obj_data = self._run_read_authorized(lambda: self.get(**obj_args))
            response = make_response(obj_data, HTTPStatus.OK)
            # Set the Location header to the newly created object
            response.headers["Location"] = url_for(self.endpoint, **obj_args)

        return response

    def _patch_instance(self: Any, data: Any, id: Any=None) -> Any:
        """
        Update the inst
        :param data: jsonapi payload
        :param id: jsonapi id
        :return: instance
        """
        # validate the jsonapi id in the url path and convert it to a database id
        path_id = self.SAFRSObject.id_type.validate_id(id)
        # Check that the id in the body is equal to the id in the url
        body_id = data.get("id", None)
        if body_id is None:
            raise ValidationError("No ID in body")

        body_id = self.SAFRSObject.id_type.validate_id(body_id)
        if path_id is not None and path_id != body_id:
            raise ValidationError("Body id does not match path id")

        attributes = data.get("attributes", {})
        attributes["id"] = body_id
        # Create the object instance with the specified id and json data
        # If the instance (id) already exists, it will be updated with the data
        instance = self._parse_target_data(data)
        if not instance:
            raise ValidationError("No instance with ID")
        instance._s_patch(**attributes)

        return instance

    def post(self: Any, **kwargs: Any) -> Any:
        """
        summary : Create {class_name}
        responses :
            200:
                description: Existing resource updated by upsert
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
        payload = cast(Any, request).get_jsonapi_payload()
        id = kwargs.get(self._s_object_id, None)
        if id is not None:
            # POSTing to an instance isn't jsonapi-compliant (https://jsonapi.org/format/#crud-creating-client-ids)
            # to do: modify Allow header
            raise ValidationError("POSTing to an instance is not allowed", status_code=HTTPStatus.METHOD_NOT_ALLOWED)

        # Create a new instance or explicitly authorize and update an upsert target.
        data = payload.get("data")
        resp_data: Any = {}  # response jsonapi "data"
        location: Optional[str] = ""  # response jsonapi "location"
        created_flags: list[bool] = []
        if data is None:
            raise ValidationError("Request contains no data")
        if isinstance(data, list):
            # http://springbot.github.io/json-api/extensions/bulk/
            # We should verify that the bulk extension is requested
            # Accept it by default now
            if not cast(Any, request).is_bulk:
                safrs.log.warning("Client sent a bulk POST but did not specify the bulk extension")
            _validate_collection_size(data, "Bulk POST")
            instances = []
            for item in data:
                self._s_last_post_created = True
                instance = self._create_instance(item)
                created = bool(self._s_last_post_created)
                instances.append(instance)
                created_flags.append(created)
            for instance in instances:
                _safrs_base.run_instance_access_check(
                    self.SAFRSObject, instance, "read"
                )
            resp_data = self._run_read_authorized(
                lambda: jsonify({"data": instances})
            )
            location = None
        else:
            self._s_last_post_created = True
            instance = self._create_instance(data)
            created = bool(self._s_last_post_created)
            created_flags.append(created)
            object_id = getattr(instance, "_s_object_id", None)
            if object_id is not None:
                # object_id is the endpoint parameter, for example "UserId" for a User SAFRSObject
                obj_args = {instance._s_object_id: instance.jsonapi_id}
                # Retrieve the object json and return it to the client
                resp_data = self._run_read_authorized(lambda: self.get(**obj_args))
                if created:
                    location = _build_location_header(self.endpoint, instance)
            else:
                safrs.log.warning("Created %s instance cannot be serialized", type(instance).__name__)

        status_code = HTTPStatus.CREATED if all(created_flags) else HTTPStatus.OK
        response = make_response(resp_data, status_code)
        # Set the Location header to the newly created object(s)
        if location:
            response.headers["Location"] = location

        return response

    def _run_upsert_authorized(self: Any, callback: Callable[[], Any]) -> Any:
        """Run an existing-row upsert through its operation-specific decorators.

        Flask-RESTful already applies a plain decorator list and the mapping's
        ``post`` decorators around this request. For a mapping, SAFRS applies
        ``upsert`` decorators to the update branch, falling back to ``patch``
        when no explicit upsert policy is configured.
        """
        method_decorators = getattr(self, "method_decorators", [])
        if not isinstance(method_decorators, Mapping):
            return callback()

        setattr(callback, "SAFRSObject", self.SAFRSObject)
        operation_name = "upsert" if "upsert" in method_decorators else "patch"
        upsert_decorators = list(method_decorators.get(operation_name, []) or [])
        post_decorator_ids = {id(decorator) for decorator in method_decorators.get("post", []) or []}
        decorated_callback = callback
        for decorator in upsert_decorators:
            if id(decorator) not in post_decorator_ids:
                decorated_callback = decorator(decorated_callback)
        return decorated_callback()

    def _create_instance(self: Any, data: Any) -> Any:
        """
        Create an instance or update an authorized upsert target.

        :param data: dictionary with {"type": ... , "attributes": ...}
        :return: created or updated instance

        ``post`` initializes ``_s_last_post_created`` before each call. Keeping
        the result as an instance preserves the protected helper's historical
        contract for subclasses while still allowing dynamic 200/201 status.
        """
        if not isinstance(data, dict):
            raise ValidationError("Data is not a dict object")

        obj_type = data.get("type", None)
        if not obj_type or not obj_type == self.SAFRSObject._s_type:
            raise ValidationError("Invalid resource type")

        attributes = dict(data.get("attributes") or {})
        client_generated_id = data.get("id", None)
        if self.SAFRSObject.allow_client_generated_ids:
            attributes["id"] = client_generated_id
        elif "id" in data:
            safrs.log.warning(f"Client-generated ids are not allowed for {self.SAFRSObject}")

        relationships = data.get("relationships", {})

        get_upsert_target = getattr(self.SAFRSObject, "_s_get_upsert_target", None)
        upsert_target = None
        if callable(get_upsert_target):
            upsert_target = get_upsert_target(client_generated_id, **attributes)
        if upsert_target is not None:
            callback = lambda: upsert_target._s_update_from_post(**attributes, **relationships)
            instance = self._run_upsert_authorized(callback)
            self._s_last_post_created = False
            return instance

        instance = self.SAFRSObject._s_post_prechecked(**attributes, **relationships)
        self._s_last_post_created = True
        return instance

    def delete(self: Any, **kwargs: Any) -> Any:
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
            409 :
                description: Conflict

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
        id = kwargs.get(self._s_object_id, None)

        if not id:
            # This endpoint shouldn't be exposed so this code is not reachable
            raise ValidationError("", status_code=HTTPStatus.METHOD_NOT_ALLOWED)

        instance = self.SAFRSObject.get_instance(id)
        instance._s_delete()

        return make_response(jsonify({}), HTTPStatus.NO_CONTENT)


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
        - source_class: class of the parent ( e.g. Parent, __tablename__ : Parents )
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

    # pylint: disable=unused-argument
    def __init__(self: Any, *args: Any, **kwargs: Any) -> None:
        """
        Initialize the relationship references:
        - relationship : sqla relationship
        -
        """
        self.relationship = self.SAFRSObject.relationship
        self.source_class = self.SAFRSObject.relationship.parent.class_
        self.target = self.SAFRSObject.relationship.mapper.class_
        self.rel_name = self.SAFRSObject.relationship.key
        # The object_ids are the ids in the swagger path e.g {FileId}
        self.parent_object_id = self.source_class._s_object_id
        self.child_object_id = self.target._s_object_id

        if self.parent_object_id == self.child_object_id:
            # see expose_relationship: if a relationship consists of
            # two same objects, the object_id should be different (i.e. append "2")
            self.child_object_id += "2"

    @staticmethod
    def _relationship_target_tables(relationship: Any) -> set[Any]:
        relationship_mapper = getattr(relationship, "mapper", None)
        return set(getattr(relationship_mapper, "tables", []) or [])

    @staticmethod
    def _column_belongs_to_target(column: Any, target_tables: set[Any]) -> bool:
        return bool(target_tables and getattr(column, "table", None) in target_tables)

    @staticmethod
    def _candidate_fk_column(local_col: Any, remote_col: Any, target_tables: set[Any]) -> Any:
        local_belongs = SAFRSRestRelationshipAPI._column_belongs_to_target(local_col, target_tables)
        remote_belongs = SAFRSRestRelationshipAPI._column_belongs_to_target(remote_col, target_tables)
        local_foreign_keys = getattr(local_col, "foreign_keys", None)
        remote_foreign_keys = getattr(remote_col, "foreign_keys", None)

        if local_belongs and local_foreign_keys:
            return local_col
        if remote_belongs and remote_foreign_keys:
            return remote_col
        if local_belongs and not remote_belongs:
            return local_col
        if remote_belongs and not local_belongs:
            return remote_col
        if local_foreign_keys:
            return local_col
        if remote_foreign_keys:
            return remote_col
        return None

    @staticmethod
    def _collect_fk_columns_from_pairs(relationship: Any, target_tables: set[Any]) -> list[Any]:
        fk_columns: list[Any] = []
        pair_sources = []
        pair_sources.extend(list(getattr(relationship, "synchronize_pairs", []) or []))
        pair_sources.extend(list(getattr(relationship, "local_remote_pairs", []) or []))
        for pair in pair_sources:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                continue
            local_col, remote_col = pair
            candidate = SAFRSRestRelationshipAPI._candidate_fk_column(local_col, remote_col, target_tables)
            if candidate is not None:
                fk_columns.append(candidate)
        return fk_columns

    @staticmethod
    def _fk_column_allows_disassociation(column: Any) -> bool:
        if getattr(column, "primary_key", False):
            return False
        if getattr(column, "nullable", True) is False:
            return False
        return True

    @staticmethod
    def _disassociation_is_safe(relationship: Any) -> bool:
        if relationship.direction == MANYTOMANY:
            return True

        cascade = getattr(relationship, "cascade", None)
        if cascade is not None and getattr(cascade, "delete_orphan", False):
            return True

        fk_columns = list(getattr(relationship, "_calculated_foreign_keys", []) or [])
        target_tables = SAFRSRestRelationshipAPI._relationship_target_tables(relationship)

        if not fk_columns:
            fk_columns.extend(SAFRSRestRelationshipAPI._collect_fk_columns_from_pairs(relationship, target_tables))

        for column in fk_columns:
            if not SAFRSRestRelationshipAPI._fk_column_allows_disassociation(column):
                return False
        return True

    def _ensure_disassociation_allowed(self: Any, operation_hint: str) -> None:
        if self._disassociation_is_safe(self.relationship):
            return
        raise ValidationError(
            f"Relationship operation '{operation_hint}' is not allowed for "
            f"{self.source_class.__name__}.{self.rel_name} (disassociation would violate DB constraints)",
            HTTPStatus.CONFLICT.value,
        )

    def _authorize_relationship_write(self: Any, parent: Any) -> None:
        """Enforce the parent's relationship-specific write policy."""
        _safrs_base.check_relationship_write_permission(parent, self.rel_name)

    # Retrieve relationship data
    def get(self: Any, **kwargs: Any) -> Any:
        """
        summary : Retrieve {child_name} from {parent_name}.{cls.relationship.key}
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
        ctx = _safrs_base.maybe_jsonapi_context()
        if ctx is not None and ctx.operation_authorizer is not None:
            ctx.operation_authorizer(self.target, "read")
        _, relation = self.parse_args(**kwargs)
        child_id = kwargs.get(self.child_object_id)
        errors: dict[str, Any] = {}
        count = 1
        meta = {}
        data = None

        if relation is None:
            # child may have been deleted
            return "Not Found", HTTPStatus.NOT_FOUND
        elif self.SAFRSObject.relationship.direction == MANYTOONE:
            data = instance = relation
            links = {"self": request.url}
            if request.url != instance._s_url:
                links["related"] = instance._s_url
            meta.update(dict(instance_meta=instance._s_meta()))
        elif child_id:
            data = child = self.target.get_instance(child_id)
            links = {"self": child._s_url}
            # If {ChildId} is passed in the url, return the child object
            # there's a difference between to-one and -to-many relationships:
            if isinstance(relation, safrs.SAFRSBase) and child != relation:
                raise NotFoundError()
            elif child not in relation:
                raise NotFoundError()
            else:
                links = {"self": request.url, "related": child._s_url}
        elif isinstance(relation, sqlalchemy.orm.collections.InstrumentedList):
            instances = jsonapi_filter_list(relation)
            instances = _safrs_base.authorize_collection_before_metadata(self.target, instances)
            instances = jsonapi_sort(instances, self.target)
            links, data, count = paginate(instances, self.target)
            count = len(data)
        else:
            # lazy='dynamic' relationships
            instances = jsonapi_filter_query(relation, self.target)
            instances = _safrs_base.authorize_collection_before_metadata(self.target, instances)
            instances = jsonapi_sort(instances, self.target)
            links, data, count = paginate(instances, self.target)

        result = jsonapi_format_response(data, meta, links, errors, count)
        return make_response(jsonify(result))

    # Relationship patching
    def patch(self: Any, **kwargs: Any) -> Any:
        """
        summary : Update {parent_name}.{cls.relationship.key}
        description : Update the {parent_name} {cls.relationship.key} "{direction}" relationship
        responses:
            200 :
                description : Accepted
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
        changed = False
        parent, relation = self.parse_args(**kwargs)
        self._authorize_relationship_write(parent)
        payload = cast(Any, request).get_jsonapi_payload()
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
                raise ValidationError("Provide a list to PATCH a TOMANY relationship")
            child = self._parse_target_data(data)
            _safrs_base.run_instance_access_check(self.target, child, "read")
            if getattr(parent, self.rel_name) != child:
                # change the relationship, i.e. add the child
                setattr(parent, self.rel_name, child)
                obj_args[self.child_object_id] = child.jsonapi_id
                changed = True

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
            # (we could loop all items but this is slower for large collections)
            _validate_collection_size(data, "Relationship PATCH")
            tmp_rel = []
            for child_data in data:
                child = self._parse_target_data(child_data)
                tmp_rel.append(child)
            for child in tmp_rel:
                _safrs_base.run_instance_access_check(self.target, child, "read")

            existing_children = list(relation)
            removed_children = [child for child in existing_children if child not in tmp_rel]
            if not tmp_rel and existing_children:
                # Explicit "replace with []" is a disassociation request.
                needs_disassociation = True
            else:
                needs_disassociation = bool(removed_children)
            if needs_disassociation:
                self._ensure_disassociation_allowed("patch")
                # SEC-02: removals are authorized like additions, for every
                # member of the replacement.
                for child in removed_children:
                    _safrs_base.run_instance_access_check(self.target, child, "unlink")

            if isinstance(relation, sqlalchemy.orm.collections.InstrumentedList):
                relation[:] = tmp_rel
            else:
                setattr(parent, self.rel_name, tmp_rel)

        elif data is None and self.SAFRSObject.relationship.direction == MANYTOONE:
            # { data : null } //=> clear the relationship
            child = getattr(parent, self.SAFRSObject.relationship.key)
            if child:
                # SEC-02: the cleared target row is a removal, authorize it.
                _safrs_base.run_instance_access_check(self.target, child, "unlink")
            self._ensure_disassociation_allowed("patch")
            setattr(parent, self.rel_name, None)
        else:
            raise ValidationError(
                f'Invalid data object type "{type(data)}" for this "{self.SAFRSObject.relationship.direction}"" relationship'
            )

        # Create the patch response
        # https://jsonapi.org/format/#crud-updating-responses
        # 200 OK
        # If a server accepts an update but also changes the resource(s) in ways other than those specified by the request
        # (for example, updating the updated-at attribute or a computed sha), it MUST return a 200 OK response. The response
        # document MUST include a representation of the updated resource(s) as if a GET request was made to the request URL.
        # A server MUST return a 200 OK status code if an update is successful, the client’s current attributes remain up to date,
        # and the server responds only with top-level meta data. In this case the server MUST NOT include a representation of the updated resource(s).
        # 204 No Content
        # If an update is successful and the server doesn’t update any attributes besides those provided, the server MUST return
        # either a 200 OK status code and response document (as described above) or a 204 No Content status code with no response document.

        if data is None:
            # item removed from relationship => 202 accepted
            data, status_code = {}, HTTPStatus.NO_CONTENT
        elif changed:
            return self.get(**obj_args)
        else:
            # Nothing changed, reflect the data
            data, status_code = {"data": data}, HTTPStatus.OK

        return make_response(jsonify(data), status_code)

    # Adding items to a relationship
    def post(self: Any, **kwargs: Any) -> Any:
        """
        summary: Add {child_name} items to {parent_name}.{cls.relationship.key}
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
        parent, relation = self.parse_args(**kwargs)
        self._authorize_relationship_write(parent)
        payload = cast(Any, request).get_jsonapi_payload()
        data = payload.get("data", None)

        if data is None:
            raise ValidationError("Invalid POST payload (no data)")

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
                setattr(parent, self.rel_name, child)
            return self._run_read_authorized(lambda: self.get(**kwargs))
        else:  # direction is TOMANY => append the items to the relationship
            _validate_collection_size(data, "Relationship POST")
            for child_data in data:
                child = self._parse_target_data(child_data)
                if child not in relation:
                    relation.append(child)
            data = {}
            status_code = HTTPStatus.NO_CONTENT

        # we can return result too but it's not necessary per the spec
        return make_response(jsonify(data), status_code)

    def delete(self: Any, **kwargs: Any) -> Any:
        """
        summary : Delete {child_name} from {parent_name}.{cls.relationship.key}
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
            409 :
                description: Conflict
        ----
        Remove an item from a relationship
        """
        # pylint: disable=unused-variable
        # (parent is unused)
        parent, relation = self.parse_args(**kwargs)
        self._authorize_relationship_write(parent)

        # No child id=> delete specified items from the relationship
        payload = cast(Any, request).get_jsonapi_payload()
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
            if not isinstance(data, dict):
                raise ValidationError("Invalid data payload")
            child_id = data.get("id", None)
            child_type = data.get("type", None)

            if child_id is None or child_type is None:
                raise ValidationError("Invalid data payload", HTTPStatus.FORBIDDEN)

            if child_type != self.target._s_type:
                raise ValidationError("Invalid type", HTTPStatus.FORBIDDEN)

            child = self.target.get_instance(child_id)
            if child == relation and getattr(parent, self.rel_name, None) == child:
                # Delete the item from the many-to-one relationship
                _safrs_base.run_instance_access_check(self.target, child, "unlink")
                self._ensure_disassociation_allowed("delete")
                delattr(parent, self.rel_name)
            else:
                safrs.log.warning("child not in relation")

        else:
            # https://jsonapi.org/format/#crud-updating-to-many-relationships
            children = data
            if not isinstance(data, list) or not children:
                raise ValidationError("Invalid data payload")
            _validate_collection_size(data, "Relationship DELETE")
            self._ensure_disassociation_allowed("delete")
            for child in children:
                child_id = child.get("id", None)
                child_type = child.get("type", None)

                if not child_id or not child_type:
                    raise ValidationError("Invalid data payload", HTTPStatus.FORBIDDEN)

                if child_type != self.target._s_type:
                    raise ValidationError("Invalid type", HTTPStatus.FORBIDDEN)

                child = self.target.get_instance(child_id)
                if child in relation:
                    # SEC-02: every removed member is authorized.
                    _safrs_base.run_instance_access_check(self.target, child, "unlink")
                    relation.remove(child)
                else:
                    safrs.log.warning("Requested item is not present in relationship")

        return make_response(jsonify({}), HTTPStatus.NO_CONTENT)

    def parse_args(self: Any, **kwargs: Any) -> Any:
        """
        Parse relationship args
        An error is raised if the parent doesn't exist.

        :return: parent, child, relation
        """
        parent_id = kwargs.get(self.parent_object_id, None)
        if parent_id is None:
            raise ValidationError("Invalid Parent Id")

        parent = self.source_class.get_instance(parent_id)
        relation = getattr(parent, self.rel_name)

        return parent, relation


class SAFRSJSONRPCAPI(Resource):
    """
    Route wrapper for the underlying SAFRSBase jsonapi_rpc

    Only HTTP POST is supported
    """

    SAFRSObject = None  # Flask views will need to set this to the SQLAlchemy safrs.DB.Model class
    method_name = None

    def __init__(self: Any, *args: Any, **kwargs: Any) -> None:
        """
        -object_id is the function used to create the url parameter name
        (eg "User" -> "UserId" )
        -this parameter is used in the swagger endpoint spec,
        eg. /Users/{UserId} where the UserId parameter is the id of the underlying SAFRSObject.
        """
        self._s_object_id = self.SAFRSObject._s_object_id
        self.target = self.SAFRSObject

    def post(self: Any, **kwargs: Any) -> Any:
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
        id = kwargs.get(self._s_object_id, None)

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
            raise ValidationError(f'Invalid method "{self.method_name}"')
        if not is_public(method):
            raise ValidationError("Method is not public")

        payload: Any
        if getattr(method, "valid_jsonapi", True):
            payload = cast(Any, request).get_jsonapi_payload()
        else:
            payload = request.get_json()
            validate_json_payload(payload)
        args = parse_rpc_args(
            http_method=request.method,
            valid_jsonapi=bool(getattr(method, "valid_jsonapi", True)),
            query_items=_rpc_query_items(),
            payload=payload,
        )

        return self._create_rpc_response(method, args)

    def get(self: Any, **kwargs: Any) -> Any:
        """
        responses :
            404 :
                description : Not Found
            403 :
                description : Forbidden

        ---
        """
        id = kwargs.get(self._s_object_id, None)

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
            raise ValidationError(f'Invalid method "{self.method_name}"')
        if not is_public(method):
            raise ValidationError("Method is not public")

        args = parse_rpc_args(
            http_method=request.method,
            valid_jsonapi=bool(getattr(method, "valid_jsonapi", True)),
            query_items=_rpc_query_items(),
            payload=None,
        )
        return self._create_rpc_response(method, args)

    def _create_rpc_response(self: Any, method: Any, args: Any) -> Any:
        safrs.log.debug(
            "RPC method %s argument names: %s",
            self.method_name,
            sorted(args) if isinstance(args, dict) else [],
        )
        if not isinstance(args, dict):
            raise ValidationError("Invalid RPC args (expected object)")
        bound_args = bind_rpc_kwargs(method, args)
        result = method(**bound_args)
        self._authorize_rpc_resources(result)

        response = normalize_rpc_result(
            result,
            valid_jsonapi=bool(getattr(method, "valid_jsonapi", True)),
            encode_value=lambda value: value,
            encode_resource=lambda value: value,
            jsonapi_doc=_rpc_jsonapi_doc,
        )

        return make_response(jsonify(response), HTTPStatus.OK)

    def _authorize_rpc_resources(self: Any, value: Any, seen: Optional[set[int]] = None) -> None:
        """Authorize concrete resources embedded anywhere in an RPC result."""
        if seen is None:
            seen = set()
        value_id = id(value)
        if value_id in seen:
            return
        seen.add(value_id)

        if isinstance(value, safrs.SAFRSBase):
            _safrs_base.run_instance_access_check(value.__class__, value, "read")
            return
        if isinstance(value, dict):
            resource_type = value.get("type")
            resource_id = value.get("id")
            api = current_app.extensions.get("safrs_api")
            models = getattr(api, "_model_method_decorators", {}) if api is not None else {}
            model = next(
                (candidate for candidate in models if candidate._s_type == resource_type),
                None,
            )
            if model is not None and resource_id is not None:
                instance = model.get_instance(resource_id)
                _safrs_base.run_instance_access_check(model, instance, "read")
            for nested in value.values():
                self._authorize_rpc_resources(nested, seen)
            return
        if isinstance(value, (list, tuple, set)):
            for nested in value:
                self._authorize_rpc_resources(nested, seen)
