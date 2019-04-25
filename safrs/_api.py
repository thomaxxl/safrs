"""
flask_restful_swagger2 API subclass
"""
import traceback
import copy
import logging
import werkzeug
from flask_restful import abort
from flask_restful_swagger_2 import Api as FRSApiBase
from flask_restful_swagger_2.swagger import create_swagger_endpoint, add_parameters
from flask_restful_swagger_2 import validate_definitions_object, parse_method_doc
from flask_restful_swagger_2 import validate_path_item_object
from flask_restful_swagger_2 import extract_swagger_path, Extractor
import safrs

# Import here in order to avoid circular dependencies, (todo: fix)
from .swagger_doc import swagger_doc, swagger_method_doc, default_paging_parameters
from .swagger_doc import parse_object_doc, swagger_relationship_doc, get_http_methods
from .errors import ValidationError, GenericError, NotFoundError
from .config import get_config
from .jsonapi import SAFRSRestAPI, SAFRSRestMethodAPI, SAFRSRestRelationshipAPI
from flask_restful.representations.json import output_json
from flask_restful.utils import OrderedDict
from functools import wraps

HTTP_METHODS = ["GET", "PUT", "POST", "DELETE", "PATCH"]
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
        swagger_doc = self.get_swagger_doc()
        safrs.dict_merge(swagger_doc, custom_swagger)
        self.representations = OrderedDict(DEFAULT_REPRESENTATIONS)

    def expose_object(self, safrs_object, url_prefix="", **properties):
        """
            This methods creates the API url endpoints for the SAFRObjects
            :param safrs_object: SAFSBase subclass that we would like to expose
        """

        """
            creates a class of the form

            @api_decorator
            class Class_API(SAFRSRestAPI):
                SAFRSObject = safrs_object

            add the class as an api resource to /SAFRSObject and /SAFRSObject/{id}

            tablename: safrs_object.__tablename__, e.g. "Users"
            classname: safrs_object.__name__, e.g. "User"

        """
        self.safrs_object = safrs_object
        safrs_object.url_prefix = url_prefix
        api_class_name = "{}_API".format(safrs_object._s_type)

        # tags indicate where in the swagger hierarchy the endpoint will be shown
        tags = [safrs_object._s_type]
        # Expose the methods first
        self.expose_methods(url_prefix, tags=tags)

        RESOURCE_URL_FMT = get_config("RESOURCE_URL_FMT")
        url = RESOURCE_URL_FMT.format(url_prefix, safrs_object._s_type)

        endpoint = safrs_object.get_endpoint()

        properties["SAFRSObject"] = safrs_object
        swagger_decorator = swagger_doc(safrs_object)

        # Create the class and decorate it
        api_class = api_decorator(
            type(api_class_name, (SAFRSRestAPI,), properties), swagger_decorator
        )

        # Expose the collection
        safrs.log.info(
            "Exposing %s on %s, endpoint: %s", safrs_object._s_type, url, endpoint
        )
        resource = self.add_resource(
            api_class, url, endpoint=endpoint, methods=["GET", "POST"]
        )

        INSTANCE_URL_FMT = get_config("INSTANCE_URL_FMT")
        url = INSTANCE_URL_FMT.format(
            url_prefix, safrs_object._s_type, safrs_object.__name__
        )
        endpoint = safrs_object.get_endpoint(type="instance")
        # Expose the instances
        self.add_resource(api_class, url, endpoint=endpoint)
        safrs.log.info(
            "Exposing {} instances on {}, endpoint: {}".format(
                safrs_object._s_type, url, endpoint
            )
        )

        object_doc = parse_object_doc(safrs_object)
        object_doc["name"] = safrs_object._s_type
        self._swagger_object["tags"].append(object_doc)

        relationships = safrs_object.__mapper__.relationships
        for relationship in relationships:
            self.expose_relationship(relationship, url, tags=tags)

    def expose_methods(self, url_prefix, tags):
        """
            Expose the safrs "documented_api_method" decorated methods
        """
        safrs_object = self.safrs_object
        api_methods = safrs_object._s_get_jsonapi_rpc_methods()
        for api_method in api_methods:
            method_name = api_method.__name__
            api_method_class_name = "method_{}_{}".format(
                safrs_object.__tablename__, method_name
            )
            if (
                isinstance(
                    safrs_object.__dict__.get(method_name, None),
                    (classmethod, staticmethod),
                )
                or getattr(api_method, "__self__", None) is safrs_object
            ):
                # method is a classmethod or static method, make it available at the class level
                CLASSMETHOD_URL_FMT = get_config("CLASSMETHOD_URL_FMT")
                url = CLASSMETHOD_URL_FMT.format(
                    url_prefix, safrs_object.__tablename__, method_name
                )
            else:
                # expose the method at the instance level
                INSTANCEMETHOD_URL_FMT = get_config("INSTANCEMETHOD_URL_FMT")
                url = INSTANCEMETHOD_URL_FMT.format(
                    url_prefix,
                    safrs_object.__tablename__,
                    safrs_object.object_id,
                    method_name,
                )

            ENDPOINT_FMT = get_config("ENDPOINT_FMT")
            endpoint = ENDPOINT_FMT.format(
                url_prefix, safrs_object.__tablename__ + "." + method_name
            )
            swagger_decorator = swagger_method_doc(safrs_object, method_name, tags)
            properties = {"SAFRSObject": safrs_object, "method_name": method_name}
            api_class = api_decorator(
                type(api_method_class_name, (SAFRSRestMethodAPI,), properties),
                swagger_decorator,
            )
            meth_name = safrs_object.__tablename__ + "." + api_method.__name__
            safrs.log.info(
                "Exposing method {} on {}, endpoint: {}".format(
                    meth_name, url, endpoint
                )
            )
            self.add_resource(
                api_class, url, endpoint=endpoint, methods=get_http_methods(api_method)
            )

    def expose_relationship(self, relationship, url_prefix, tags):
        """
            Expose a relationship tp the REST API:
            A relationship consists of a parent and a child class
            creates a class of the form

            @api_decorator
            class Parent_X_Child_API(SAFRSRestAPI):
                SAFRSObject = safrs_object

            add the class as an api resource to /SAFRSObject and /SAFRSObject/{id}
        """

        API_CLASSNAME_FMT = "{}_X_{}_API"

        properties = {}
        safrs_object = relationship.mapper.class_
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
        decorators = getattr(parent_class, "custom_decorators", []) + getattr(
            parent_class, "decorators", []
        )
        rel_object = type(
            rel_name,
            (SAFRSRelationshipObject,),
            {
                "relationship": relationship,
                # Merge the relationship decorators from the classes
                # This makes things really complicated!!!
                # TODO: simplify this by creating a proper superclass
                "custom_decorators": decorators,
            },
        )

        properties["SAFRSObject"] = rel_object
        swagger_decorator = swagger_relationship_doc(rel_object, tags)

        api_class = api_decorator(
            type(api_class_name, (SAFRSRestRelationshipAPI,), properties),
            swagger_decorator,
        )

        # Expose the relationship for the parent class:
        # GET requests to this endpoint retrieve all item ids
        safrs.log.info(
            "Exposing relationship {} on {}, endpoint: {}".format(
                rel_name, url, endpoint
            )
        )
        self.add_resource(
            api_class, url, endpoint=endpoint, methods=["GET", "POST", "PATCH"]
        )

        #
        try:
            child_object_id = safrs_object.object_id
        except Exception as exc:
            safrs.log.exception(exc)
            safrs.log.error("No object id for {}".format(safrs_object))
            child_object_id = safrs_object.__name__

        if safrs_object == parent_class:
            # Avoid having duplicate argument ids in the url:
            # append a 2 in case of a self-referencing relationship
            # todo : test again
            child_object_id += "2"

        # Expose the relationship for <string:ChildId>, this lets us
        # query and delete the class relationship properties for a given
        # child id
        url = (RELATIONSHIP_URL_FMT + "/<string:{}>").format(
            url_prefix, rel_name, child_object_id
        )
        endpoint = "{}api.{}Id".format(url_prefix, rel_name)

        safrs.log.info(
            "Exposing {} relationship {} on {}, endpoint: {}".format(
                parent_name, rel_name, url, endpoint
            )
        )

        self.add_resource(
            api_class,
            url,
            relationship=rel_object.relationship,
            endpoint=endpoint,
            methods=["GET", "DELETE"],
        )

    def add_resource(self, resource, *urls, **kwargs):
        """
            This method is partly copied from flask_restful_swagger_2/__init__.py

            I changed it because we don't need path id examples when
            there's no {id} in the path. We filter out the unwanted parameters
        """
        relationship = kwargs.pop("relationship", False)  # relationship object
        SAFRS_INSTANCE_SUFFIX = get_config("OBJECT_ID_SUFFIX") + "}"

        path_item = {}
        definitions = {}
        resource_methods = kwargs.get("methods", HTTP_METHODS)
        kwargs.pop("safrs_object", None)
        for method in [m.lower() for m in resource.methods]:
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

        validate_definitions_object(definitions)
        self._swagger_object["definitions"].update(definitions)

        if path_item:
            validate_path_item_object(path_item)
            for url in urls:
                if not url.startswith("/"):
                    raise ValidationError("paths must start with a /")
                swagger_url = extract_swagger_path(url)
                for method in [m.lower() for m in resource.methods]:

                    if method == "post" and swagger_url.strip("/").endswith(
                        SAFRS_INSTANCE_SUFFIX
                    ):
                        # POSTing to an instance isn't jsonapi-compliant (https://jsonapi.org/format/#crud-creating-client-ids)
                        # "A server MUST return 403 Forbidden in response to an
                        # unsupported request to create a resource with a client-generated ID"
                        # the method has already been added before, remove it & continue
                        path_item.pop(method, None)
                        continue

                    method_doc = copy.deepcopy(path_item.get(method))
                    if not method_doc:
                        continue

                    filtered_parameters = []
                    for parameter in method_doc.get("parameters", []):
                        object_id = "{%s}" % parameter.get("name")

                        if method == "get" and relationship:
                            default_include = ",".join(
                                [
                                    rel.key
                                    for rel in relationship.mapper.class_.__mapper__.relationships
                                ]
                            )
                            param = {
                                "default": default_include,
                                "type": "string",
                                "name": "include",
                                "in": "query",
                                "format": "string",
                                "required": False,
                                "description": "Related relationships to include (csv)",
                            }
                            if param not in filtered_parameters:
                                filtered_parameters.append(param)

                        if method == "get" and not swagger_url.endswith(
                            SAFRS_INSTANCE_SUFFIX
                        ):
                            # limit parameter specifies the number of items to return

                            for param in default_paging_parameters():
                                if param not in filtered_parameters:
                                    filtered_parameters.append(param)

                            default_include = ",".join(
                                [
                                    rel.key
                                    for rel in self.safrs_object.__mapper__.relationships
                                ]
                            )

                            param = {
                                "default": default_include,
                                "type": "string",
                                "name": "include",
                                "in": "query",
                                "format": "string",
                                "required": False,
                                "description": "Related relationships to include (csv)",
                            }
                            if param not in filtered_parameters:
                                filtered_parameters.append(param)

                            param = {
                                "default": ",".join(self.safrs_object._s_jsonapi_attrs),
                                "type": "string",
                                "name": "fields[{}]".format(self.safrs_object._s_type),
                                "in": "query",
                                "format": "string",
                                "required": False,
                                "description": "Related relationships to include (csv)",
                            }
                            if param not in filtered_parameters:
                                filtered_parameters.append(param)

                            param = {
                                "default": ",".join(self.safrs_object._s_jsonapi_attrs),
                                "type": "string",
                                "name": "sort",
                                "in": "query",
                                "format": "string",
                                "required": False,
                                "description": "Sort order",
                            }
                            if param not in filtered_parameters:
                                filtered_parameters.append(param)

                            for column_name in self.safrs_object._s_column_names:
                                param = {
                                    "default": "",
                                    "type": "string",
                                    "name": "filter[{}]".format(column_name),
                                    "in": "query",
                                    "format": "string",
                                    "required": False,
                                    "description": "{} attribute filter (csv)".format(
                                        column_name
                                    ),
                                }
                                if param not in filtered_parameters:
                                    filtered_parameters.append(param)

                            param = {
                                "default": "",
                                "type": "string",
                                "name": "filter",
                                "in": "query",
                                "format": "string",
                                "required": False,
                                "description": "Custom filter",
                            }
                            if param not in filtered_parameters:
                                filtered_parameters.append(param)


                        if not (
                            parameter.get("in") == "path"
                            and not object_id in swagger_url
                        ):
                            # Only if a path param is in path url then we add the param
                            filtered_parameters.append(parameter)

                    method_doc["parameters"] = filtered_parameters
                    method_doc["operationId"] = self.get_operation_id(
                        path_item.get(method).get("summary", "")
                    )
                    path_item[method] = method_doc

                    if method == "get" and not swagger_url.endswith(
                        SAFRS_INSTANCE_SUFFIX
                    ):
                        # If no {id} was provided, we return a list of all the objects
                        # pylint: disable=invalid-formatstring
                        try:
                            method_doc[
                                "description"
                            ] += " list (See GET /{{} for details)".format(
                                SAFRS_INSTANCE_SUFFIX
                            )
                            method_doc["responses"]["200"]["schema"] = ""
                        except:
                            pass

                self._swagger_object["paths"][swagger_url] = path_item

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
    """
        Decorator for the API views:
            - add swagger documentation ( swagger_decorator )
            - add cors
            - add generic exception handling

        We couldn't use inheritance because the rest method decorator
        references the cls.SAFRSObject which isn't known
    """

    cors_domain = get_config("cors_domain")
    cls.http_methods = (
        {}
    )  # holds overridden http methods, note: cls also has the "methods" set, but it's not related to this
    for method_name in [
        "get",
        "post",
        "delete",
        "patch",
        "put",
        "options",
    ]:  # HTTP methods
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
            cls.http_methods[method_name] = lambda *args, **kwargs: parent_method(
                *args, **kwargs
            )

        # Apply custom decorators, specified as class variable list
        try:
            # Add swagger documentation
            decorated_method = swagger_decorator(decorated_method)
        except RecursionError:
            # Got this error when exposing WP DB, TODO: investigate where it comes from
            safrs.log.error(
                "Failed to generate documentation for {} {} (Recursion Error)".format(
                    cls, decorated_method
                )
            )
        # pylint: disable=broad-except
        except Exception as exc:
            safrs.log.exception(exc)
            safrs.log.error(
                "Failed to generate documentation for {}".format(decorated_method)
            )

        # Add cors
        if cors_domain is not None:
            decorated_method = cors.crossdomain(origin=cors_domain)(decorated_method)
        # Add exception handling
        decorated_method = http_method_decorator(decorated_method)

        setattr(decorated_method, "SAFRSObject", cls.SAFRSObject)
        for custom_decorator in getattr(cls.SAFRSObject, "custom_decorators", []):
            decorated_method = custom_decorator(decorated_method)

        setattr(cls, method_name, decorated_method)

    return cls


def http_method_decorator(fun):
    """
        Decorator for the REST methods
        - commit the database
        - convert all exceptions to a JSON serializable GenericError

        This method will be called for all requests
    """

    @wraps(fun)
    def method_wrapper(*args, **kwargs):
        try:
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
            traceback.print_exc()
            if safrs.log.getEffectiveLevel() > logging.DEBUG:
                message = "Unknown Error"
            else:
                message = str(exc)

        safrs.DB.session.rollback()
        errors = dict(detail=message)
        abort(status_code, errors=[errors])

    return method_wrapper


class SAFRSRelationshipObject:
    """
        Relationship object
    """

    __tablename__ = "tabname"
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
        responses = {
            "200": {
                "description": "{} object".format(object_name),
                "schema": object_model,
            }
        }

        if http_method == "post":
            responses = {"200": {"description": "Success"}}

        if http_method == "get":
            responses = {"200": {"description": "Success"}}
            # responses['200']['schema'] = {'$ref': '#/definitions/{}'.format(object_model.__name__)}

        return body, responses
