"""
flask_restful_swagger2 API subclass
"""
import copy
from http import HTTPStatus
import logging
import werkzeug
from flask_restful import abort
from flask_restful.representations.json import output_json
from flask_restful.utils import OrderedDict
from flask_restful.utils import cors
from flask_restful_swagger_2 import Api as FRSApiBase
from flask_restful_swagger_2 import validate_definitions_object, parse_method_doc
from flask_restful_swagger_2 import validate_path_item_object
from flask_restful_swagger_2 import extract_swagger_path, Extractor, ValidationError as FRSValidationError
from flask import request
from functools import wraps
import collections
import safrs
from .swagger_doc import swagger_doc, swagger_method_doc, default_paging_parameters
from .swagger_doc import parse_object_doc, swagger_relationship_doc, get_http_methods
from .errors import ValidationError, GenericError, NotFoundError
from .config import get_config
from .jsonapi import SAFRSRestAPI, SAFRSJSONRPCAPI, SAFRSRestRelationshipAPI
from ._safrs_relationship import SAFRSRelationshipObject
import json

HTTP_METHODS = ["GET", "POST", "PATCH", "DELETE", "PUT"]
DEFAULT_REPRESENTATIONS = [("application/vnd.api+json", output_json)]


# pylint: disable=protected-access,invalid-name,line-too-long,logging-format-interpolation,fixme,too-many-branches
class Api(FRSApiBase):
    """
        Subclass of the flask_restful_swagger API class where we add the expose_object method
        this method creates an API endpoint for the SAFRSBase object and corresponding swagger
        documentation
    """

    _operation_ids = {}

    def __init__(self, *args, **kwargs):
        """
            http://jsonapi.org/format/#content-negotiation-servers
            Servers MUST send all JSON:API data in response documents with
            the header Content-Type: application/vnd.api+json without any media type parameters.

            Servers MUST respond with a 415 Unsupported Media Type status code if
            a request specifies the header Content-Type: application/vnd.api+json with any media type parameters.

            Servers MUST respond with a 406 Not Acceptable status code if
            a request’s Accept header contains the JSON:API media type and
            all instances of that media type are modified with media type parameters.
        """

        custom_swagger = kwargs.pop("custom_swagger", {})
        kwargs["default_mediatype"] = "application/vnd.api+json"
        super(Api, self).__init__(*args, **kwargs)
        self.representations = OrderedDict(DEFAULT_REPRESENTATIONS)
        self.update_spec(custom_swagger)

    def update_spec(self, custom_swagger):
        """
            :param custom_swagger: swagger spec to be added to the swagger.json
        """
        _swagger_doc = self.get_swagger_doc()
        safrs.dict_merge(_swagger_doc, custom_swagger)

    def expose_object(self, safrs_object, url_prefix="", **properties):
        """ This methods creates the API url endpoints for the SAFRObjects
            :param safrs_object: SAFSBase subclass that we would like to expose

            creates a class of the form

            @api_decorator
            class Class_API(SAFRSRestAPI):
                SAFRSObject = safrs_object

            add the class as an api resource to /SAFRSObject and /SAFRSObject/{id}

            tablename/collectionname: safrs_object._s_collection_name, e.g. "Users"
            classname: safrs_object.__name__, e.g. "User"
        """
        self.safrs_object = safrs_object
        safrs_object.url_prefix = url_prefix
        api_class_name = "{}_API".format(safrs_object._s_type)

        # tags indicate where in the swagger hierarchy the endpoint will be shown
        tags = [safrs_object._s_collection_name]
        # Expose the methods first
        self.expose_methods(url_prefix, tags=tags)

        RESOURCE_URL_FMT = get_config("RESOURCE_URL_FMT")
        url = RESOURCE_URL_FMT.format(url_prefix, safrs_object._s_collection_name)

        endpoint = safrs_object.get_endpoint()

        properties["SAFRSObject"] = safrs_object
        properties["http_methods"] = safrs_object.http_methods

        # Expose the collection: Create the class and decorate it
        swagger_decorator = swagger_doc(safrs_object)
        api_class = api_decorator(type(api_class_name, (SAFRSRestAPI,), properties), swagger_decorator)

        safrs.log.info("Exposing {} on {}, endpoint: {}".format(safrs_object._s_type, url, endpoint))
        self.add_resource(api_class, url, endpoint=endpoint, methods=["GET", "POST"])

        INSTANCE_URL_FMT = get_config("INSTANCE_URL_FMT")
        url = INSTANCE_URL_FMT.format(url_prefix, safrs_object._s_collection_name, safrs_object.__name__)
        endpoint = safrs_object.get_endpoint(type="instance")

        # Expose the instances
        safrs.log.info("Exposing {} instances on {}, endpoint: {}".format(safrs_object._s_collection_name, url, endpoint))
        self.add_resource(api_class, url, endpoint=endpoint)

        object_doc = parse_object_doc(safrs_object)
        object_doc["name"] = safrs_object._s_collection_name
        self._swagger_object["tags"].append(object_doc)

        for relationship in safrs_object._s_relationships:
            self.expose_relationship(relationship, url, tags=tags)

    def expose_methods(self, url_prefix, tags):
        """ Expose the safrs "documented_api_method" decorated methods
            :param url_prefix: api url prefix
            :param tags: swagger tags
            :return: None
        """

        safrs_object = self.safrs_object
        api_methods = safrs_object._s_get_jsonapi_rpc_methods()
        for api_method in api_methods:
            method_name = api_method.__name__
            api_method_class_name = "method_{}_{}".format(safrs_object._s_class_name, method_name)
            if (
                isinstance(safrs_object.__dict__.get(method_name, None), (classmethod, staticmethod))
                or getattr(api_method, "__self__", None) is safrs_object
            ):
                # method is a classmethod or static method, make it available at the class level
                CLASSMETHOD_URL_FMT = get_config("CLASSMETHOD_URL_FMT")
                url = CLASSMETHOD_URL_FMT.format(url_prefix, safrs_object._s_collection_name, method_name)
            else:
                # expose the method at the instance level
                INSTANCEMETHOD_URL_FMT = get_config("INSTANCEMETHOD_URL_FMT")
                url = INSTANCEMETHOD_URL_FMT.format(url_prefix, safrs_object._s_collection_name, safrs_object._s_object_id, method_name)

            ENDPOINT_FMT = get_config("ENDPOINT_FMT")
            endpoint = ENDPOINT_FMT.format(url_prefix, safrs_object._s_collection_name + "." + method_name)
            swagger_decorator = swagger_method_doc(safrs_object, method_name, tags)
            properties = {"SAFRSObject": safrs_object, "method_name": method_name}
            properties["http_methods"] = safrs_object.http_methods
            api_class = api_decorator(type(api_method_class_name, (SAFRSJSONRPCAPI,), properties), swagger_decorator)
            meth_name = safrs_object._s_class_name + "." + api_method.__name__
            safrs.log.info("Exposing method {} on {}, endpoint: {}".format(meth_name, url, endpoint))
            self.add_resource(api_class, url, endpoint=endpoint, methods=get_http_methods(api_method), jsonapi_rpc=True)

    def expose_relationship(self, relationship, url_prefix, tags):
        """
            Expose a relationship tp the REST API:
            A relationship consists of a parent and a target class
            creates a class of the form

            @api_decorator
            class Parent_X_target_API(SAFRSRestAPI):
                SAFRSObject = safrs_object

            add the class as an api resource to /SAFRSObject and /SAFRSObject/{id}

            :param relationship: relationship
            :param url_prefix: api url prefix
            :param tags: swagger tags
            :return: None
        """
        # safrs_object is the target class, if this is not a SAFRSBase class, then we shouldn't expose it
        # the _s_expose attribute indicates we're dealing with a SAFRSBase instance
        # if the relationship is not an sql sqlalchemy.orm.relationships.RelationshipProperty instance
        # then we should have defined the _target
        target_object = relationship.mapper.class_
        if not getattr(target_object, "_s_expose", False):
            safrs.log.debug("Not exposing {}".format(target_object))
            return

        API_CLASSNAME_FMT = "{}_X_{}_API"

        properties = {}
        rel_name = relationship.key

        parent_class = relationship.parent.class_
        parent_name = parent_class.__name__

        # Name of the endpoint class
        RELATIONSHIP_URL_FMT = get_config("RELATIONSHIP_URL_FMT")
        api_class_name = API_CLASSNAME_FMT.format(parent_name, rel_name)
        url = RELATIONSHIP_URL_FMT.format(url_prefix, rel_name)

        ENDPOINT_FMT = get_config("ENDPOINT_FMT")
        endpoint = ENDPOINT_FMT.format(url_prefix, rel_name)

        # Relationship object
        decorators = getattr(parent_class, "custom_decorators", []) + getattr(parent_class, "decorators", [])
        rel_object = type(
            "{}.{}".format(parent_name, rel_name),  # Name of the class we're creating here
            (SAFRSRelationshipObject,),
            {
                "relationship": relationship,
                # Merge the relationship decorators from the classes
                # This makes things really complicated!!!
                # TODO: simplify this by creating a proper superclass
                "custom_decorators": decorators,
                "parent": parent_class,
                "_target": target_object,
            },
        )

        properties["SAFRSObject"] = rel_object
        properties["http_methods"] = target_object.http_methods
        swagger_decorator = swagger_relationship_doc(rel_object, tags)
        api_class = api_decorator(type(api_class_name, (SAFRSRestRelationshipAPI,), properties), swagger_decorator)

        # Expose the relationship for the parent class:
        # GET requests to this endpoint retrieve all item ids
        safrs.log.info("Exposing relationship {} on {}, endpoint: {}".format(rel_name, url, endpoint))
        # Check if there are custom http methods specified
        methods = getattr(relationship, "http_methods", parent_class.http_methods)
        self.add_resource(api_class, url, endpoint=endpoint, methods=methods)

        try:
            target_object_id = target_object._s_object_id
        except Exception as exc:
            safrs.log.exception(exc)
            safrs.log.error("No object id for {}".format(target_object))
            target_object_id = target_object.__name__

        if target_object == parent_class:
            # Avoid having duplicate argument ids in the url:
            # append a 2 in case of a self-referencing relationship
            # todo : test again
            target_object_id += "2"

        # Expose the relationship for <string:targetId>, this lets us
        # query and delete the class relationship properties for a given
        # target id
        # nb: this is not really documented in the jsonapi spec, remove??
        url = (RELATIONSHIP_URL_FMT + "/<string:{}>").format(url_prefix, rel_name, target_object_id)
        endpoint = "{}api.{}Id".format(url_prefix, rel_name)

        safrs.log.info("Exposing {} relationship {} on {}, endpoint: {}".format(parent_name, rel_name, url, endpoint))
        self.add_resource(
            api_class, url, relationship=rel_object.relationship, endpoint=endpoint, methods=["GET", "DELETE"], deprecated=True
        )

    @staticmethod
    def get_resource_methods(resource, ordered_methods=None):
        """ :param ordered_methods:
            :return: the http methods from the SwaggerEndpoint and SAFRS Resources,
            in the order specified by ordered_methods
        """
        if ordered_methods is None:
            ordered_methods = HTTP_METHODS
        om = ordered_methods
        safrs_object = getattr(resource, "SAFRSObject", None)
        if safrs_object:
            om = [m.upper() for m in safrs_object.http_methods if m.upper() in ordered_methods]

        resource_methods = [m.lower() for m in ordered_methods if m in resource.methods and m.upper() in om]
        return resource_methods

    def add_resource(self, resource, *urls, **kwargs):
        """
            This method is partly copied from flask_restful_swagger_2/__init__.py

            I changed it because we don't need path id examples when
            there's no {id} in the path.
            We also have to filter out the unwanted parameters
        """
        #
        # This function has grown out of proportion and should be refactored, disable lint warning for now
        #
        # pylint: disable=too-many-nested-blocks,too-many-statements, too-many-locals
        #
        kwargs.pop("relationship", False)  # relationship object
        SAFRS_INSTANCE_SUFFIX = get_config("OBJECT_ID_SUFFIX") + "}"

        path_item = collections.OrderedDict()
        definitions = {}
        resource_methods = kwargs.get("methods", HTTP_METHODS)
        kwargs.pop("safrs_object", None)
        is_jsonapi_rpc = kwargs.pop("jsonapi_rpc", False)  # check if the exposed method is a jsonapi_rpc method
        deprecated = kwargs.pop("deprecated", False)  # TBD!!
        for method in self.get_resource_methods(resource):
            if deprecated:
                continue
            if not method.upper() in resource_methods:
                continue
            f = getattr(resource, method, None)
            if not f:
                continue

            operation = getattr(f, "__swagger_operation_object", None)
            if operation:
                # operation, definitions_ = self._extract_schemas(operation)
                operation, definitions_ = Extractor.extract(operation)
                path_item[method] = operation
                definitions.update(definitions_)
                summary = parse_method_doc(f, operation)
                if summary:
                    operation["summary"] = summary.split("<br/>")[0]

        try:
            validate_definitions_object(definitions)
        except FRSValidationError:
            safrs.log.critical("Validation failed for {}".format(definitions))
            exit()

        self._swagger_object["definitions"].update(definitions)

        if path_item:
            for url in urls:
                if not url.startswith("/"):
                    raise ValidationError("paths must start with a /")
                swagger_url = extract_swagger_path(url)

                # exposing_instance tells us whether we're exposing an instance (as opposed to a collection)
                exposing_instance = swagger_url.strip("/").endswith(SAFRS_INSTANCE_SUFFIX)

                for method in self.get_resource_methods(resource):
                    if method == "post" and exposing_instance:
                        # POSTing to an instance isn't jsonapi-compliant (https://jsonapi.org/format/#crud-creating-client-ids)
                        # "A server MUST return 403 Forbidden in response to an
                        # unsupported request to create a resource with a client-generated ID"
                        # the method has already been added before, remove it & continue
                        path_item.pop(method, None)
                        continue

                    method_doc = copy.deepcopy(path_item.get(method))
                    if not method_doc:
                        continue

                    collection_summary = method_doc.pop("collection_summary", method_doc.get("summary", None))
                    if not exposing_instance and collection_summary:
                        method_doc["summary"] = collection_summary

                    parameters = []
                    for parameter in method_doc.get("parameters", []):
                        object_id = "{%s}" % parameter.get("name")
                        if method == "get":
                            # Get the jsonapi included resources, ie the exposed relationships
                            param = resource.get_swagger_include()
                            parameters.append(param)

                            # Get the jsonapi fields[], ie the exposed attributes/columns
                            param = resource.get_swagger_fields()
                            parameters.append(param)

                        #
                        # Add the sort, filter parameters to the swagger doc when retrieving a collection
                        #
                        if method == "get" and not (exposing_instance or is_jsonapi_rpc):
                            # limit parameter specifies the number of items to return
                            parameters += default_paging_parameters()

                            param = resource.get_swagger_sort()
                            parameters.append(param)

                            parameters += list(resource.get_swagger_filters())

                        if not (parameter.get("in") == "path" and object_id not in swagger_url) and parameter not in parameters:
                            # Only if a path param is in path url then we add the param
                            parameters.append(parameter)

                    unique_params = OrderedDict()  # rm duplicates
                    for param in parameters:
                        unique_params[param["name"]] = param
                    method_doc["parameters"] = list(unique_params.values())
                    method_doc["operationId"] = self.get_operation_id(path_item.get(method).get("summary", ""))
                    path_item[method] = method_doc

                    instance_schema = method_doc.get("responses", {}).get("200", {})
                    if instance_schema and exposing_instance and method_doc["responses"]["200"].get("schema", None):
                        method_doc["responses"]["200"]["schema"] = resource.SAFRSObject.swagger_models["instance"].reference()
                        # add this later
                        method_doc["responses"]["200"]["schema"] = {}

                    try:
                        validate_path_item_object(path_item)
                    except FRSValidationError as exc:
                        safrs.log.exception(exc)
                        safrs.log.critical("Validation failed for {}".format(path_item))
                        exit()

                self._swagger_object["paths"][swagger_url] = path_item
                # Check whether we manage to convert to json
                try:
                    json.dumps(self._swagger_object)
                except Exception:
                    safrs.log.critical("Json encoding failed for")
                    # safrs.log.debug(self._swagger_object)

        # disable API methods that were not set by the SAFRSObject
        for http_method in HTTP_METHODS:
            hm = http_method.lower()
            if hm not in self.get_resource_methods(resource):
                setattr(resource, hm, lambda x: ({}, HTTPStatus.METHOD_NOT_ALLOWED))

        # pylint: disable=bad-super-call
        super(FRSApiBase, self).add_resource(resource, *urls, **kwargs)

    @classmethod
    def get_operation_id(cls, summary):
        """
        get_operation_id
        """
        summary = "".join(c for c in summary if c.isalnum())
        if summary not in cls._operation_ids:
            cls._operation_ids[summary] = 0
        else:
            cls._operation_ids[summary] += 1
        return "{}_{}".format(summary, cls._operation_ids[summary])


def api_decorator(cls, swagger_decorator):
    """ Decorator for the API views:
            - add swagger documentation ( swagger_decorator )
            - add cors
            - add generic exception handling

        We couldn't use inheritance because the rest method decorator
        references the cls.SAFRSObject which isn't known

        :param cls: The class that will be decorated
        :param swagger_decorator: function that will generate the swagger
        :return: decorated class
    """

    cors_domain = get_config("cors_domain")
    cls.http_methods = {}  # holds overridden http methods, note: cls also has the "methods" set, but it's not related to this
    for method_name in ["patch", "post", "delete", "get", "put", "options"]:  # HTTP methods
        method = getattr(cls, method_name, None)
        if not method:
            continue

        decorated_method = method
        # if the SAFRSObject has a custom http method decorator, use it
        # e.g. SAFRSObject.get
        custom_method = getattr(cls.SAFRSObject, method_name, None)
        if custom_method and callable(custom_method):
            decorated_method = custom_method
            # keep the default method as parent_<method_name>, e.g. parent_get
            parent_method = getattr(cls, method_name)
            cls.http_methods[method_name] = parent_method

        # Add cors
        if cors_domain is not None:
            decorated_method = cors.crossdomain(origin=cors_domain)(decorated_method)
        # Add exception handling
        decorated_method = http_method_decorator(decorated_method)

        setattr(decorated_method, "SAFRSObject", cls.SAFRSObject)

        try:
            # Add swagger documentation
            decorated_method = swagger_decorator(decorated_method)
        except RecursionError:
            # Got this error when exposing WP DB, TODO: investigate where it comes from
            safrs.log.error("Failed to generate documentation for {} {} (Recursion Error)".format(cls, decorated_method))
        # pylint: disable=broad-except
        except Exception as exc:
            safrs.log.exception(exc)
            safrs.log.error("Failed to generate documentation for {}".format(decorated_method))

        # The user can add custom decorators
        # Apply the custom decorators, specified as class variable list
        for custom_decorator in getattr(cls.SAFRSObject, "custom_decorators", []) + getattr(cls.SAFRSObject, "decorators", []):
            # update_wrapper(custom_decorator, decorated_method)
            swagger_operation_object = getattr(decorated_method, "__swagger_operation_object", {})
            decorated_method = custom_decorator(decorated_method)
            decorated_method.__swagger_operation_object = swagger_operation_object

        setattr(cls, method_name, decorated_method)
    return cls


def http_method_decorator(fun):
    """ Decorator for the supported jsonapi HTTP methods (get, post, patch, delete)
        - commit the database
        - convert all exceptions to a JSON serializable GenericError

        This method will be called for all requests
        :param fun:
        :return: wrapped fun
    """

    @wraps(fun)
    def method_wrapper(*args, **kwargs):
        """ Wrap the method and perform error handling
            :param *args:
            :param **kwargs:
            :return: result of the wrapped method
        """
        try:
            if not request.is_jsonapi and fun.__name__ not in ["get"]:
                # reuire jsonapi content type for requests to these routes
                raise GenericError("Unsupported Content-Type", 415)
            result = fun(*args, **kwargs)
            safrs.DB.session.commit()
            return result

        except (ValidationError, GenericError, NotFoundError) as exc:
            safrs.log.exception(exc)
            status_code = getattr(exc, "status_code")
            message = exc.message

        except werkzeug.exceptions.NotFound:
            status_code = 404
            message = "Not Found"

        except Exception as exc:
            status_code = getattr(exc, "status_code", 500)
            safrs.log.exception(exc)
            if safrs.log.getEffectiveLevel() > logging.DEBUG:
                message = "Logging Disabled"
            else:
                message = str(exc)

        safrs.DB.session.rollback()
        safrs.log.error(message)
        errors = dict(detail=message)
        abort(status_code, errors=[errors])

    return method_wrapper
