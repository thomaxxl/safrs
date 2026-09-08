# flask_restful_swagger2 API subclass
from collections.abc import Mapping
from http import HTTPStatus
import logging
import inspect
import werkzeug
from flask_restful import abort, Resource
from flask_restful.representations.json import output_json
from flask_restful.utils import OrderedDict
from flask_restful.utils import cors
from flask_restful_swagger_2 import Api as FRSApiBase
from flask_restful_swagger_2 import validate_definitions_object, parse_method_doc
from flask_restful_swagger_2 import validate_path_item_object, Schema
from flask_restful_swagger_2 import extract_swagger_path, Extractor, ValidationError as FRSValidationError
from flask import request
from functools import wraps
import safrs
from .swagger_doc import swagger_doc, swagger_method_doc, default_paging_parameters
from .swagger_doc import parse_object_doc, swagger_relationship_doc
from .api_doc import get_http_methods
from .errors import GenericError, JsonapiError, SystemValidationError, ValidationError, log_integrity_error_details
from .config import get_config
from .json_encoder import SAFRSJSONProvider, SAFRSJSONEncoder
from ._safrs_relationship import SAFRSRelationshipObject
from . import tx
from .runtime import bind_db, get_db
from sqlalchemy.orm.interfaces import MANYTOONE
import sqlalchemy
from flask import current_app, Response
import json
import yaml  # type: ignore[import-untyped]
from contextlib import contextmanager
from flask.app import Flask
from typing import Any, Callable, Optional, Type, cast
from sqlalchemy.orm.exc import FlushError

HTTP_METHODS = ["GET", "POST", "PATCH", "DELETE", "PUT"]
RESOURCE_METHODS = ["patch", "post", "delete", "get", "put", "head", "options"]
DEFAULT_REPRESENTATIONS = [("application/vnd.api+json", output_json)]
WRITE_HTTP_METHODS = {"POST", "PATCH", "DELETE", "PUT"}


def _is_relationship_pk_disassociation_assertion(exc: AssertionError) -> bool:
    message = str(exc).lower()
    return "blank-out primary key" in message or ("dependency rule" in message and "primary key" in message)


def _model_decorators(model: Any) -> list[Any]:
    return list(getattr(model, "custom_decorators", [])) + list(getattr(model, "decorators", []))


def _method_decorators_configured(configured: Any) -> bool:
    """Whether a ``method_decorators`` value configures at least one decorator."""
    if isinstance(configured, Mapping):
        return any(value for value in configured.values())
    return bool(configured)


def _model_has_authorization_policy(model: Any) -> bool:
    """Whether a model uses SAFRS authorization hooks: route or class
    decorators, or an instance-level ``_s_check_perm`` override.

    Authentication applied outside the SAFRS contract (middleware,
    ``before_request``, query-level checks) is not visible and not reported.
    """
    if _model_decorators(model):
        return True
    for klass in model.__mro__:
        if klass is not object and "_s_check_perm" in getattr(klass, "__dict__", {}):
            # SAFRSBase defines the default; only overrides count as policy.
            if not (getattr(klass, "__module__", "").startswith("safrs.")):
                return True
    return False


def _dedupe_decorators(decorators: Any) -> list[Any]:
    """Deduplicate decorators by identity while preserving configured order."""
    result: list[Any] = []
    seen: set[int] = set()
    for decorator in decorators:
        decorator_id = id(decorator)
        if decorator_id in seen:
            continue
        seen.add(decorator_id)
        result.append(decorator)
    return result


def _http_method_set(methods: Any) -> set[str]:
    return {str(method).upper() for method in methods or []}


class SAFRSAPI(FRSApiBase):
    """
    Subclass of the flask_restful_swagger API class where we add the expose_object method
    this method creates an API endpoint for the SAFRSBase object and corresponding swagger
    documentation
    """

    _operation_ids: dict[str, int] = {}
    _custom_swagger: dict[str, Any] = {}
    _als_resources: list[Any] = []
    client_uri = ""

    def runtime_context(self: Any) -> Any:
        """Bind this API's database for work outside a Flask request."""
        @contextmanager
        def context() -> Any:
            with self._safrs_app.app_context(), bind_db(self.db):
                yield

        return context()

    def __init__(self: Any, app: Flask, host: str='localhost', port: int=5000, prefix: str='', description: str='SAFRSAPI', json_encoder: Optional[Type[SAFRSJSONProvider]]=None, swaggerui_blueprint: bool=True, docs_decorators: Any=None, **kwargs: Any) -> None:
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

        self._custom_swagger = kwargs.pop("custom_swagger", {})
        self._safrs_app = app
        self._operation_ids = {}
        self._als_resources = []
        self._model_method_decorators: dict[Any, Any] = {}
        self._response_authorizers: dict[Any, list[Any]] = {}
        self._model_url_prefix: dict[Any, str] = {}
        self.authorization = kwargs.pop("authorization", None)
        self.principal_provider = kwargs.pop("principal_provider", None)
        if (self.authorization is None) != (self.principal_provider is None):
            raise ValueError("authorization and principal_provider must be configured together")
        self.swaggerui_blueprint = swaggerui_blueprint
        kwargs["default_mediatype"] = "application/vnd.api+json"
        app_db = kwargs.pop("app_db", None)
        self.db = app_db if app_db is not None else app.extensions["sqlalchemy"]
        if self.authorization is not None:
            metadata = getattr(self.db, "metadata", None)
            if metadata is None:
                metadata = self.db.Model.metadata
            self.authorization.bind(metadata)
            self.authorization.freeze()
        safrs.SAFRS(app, app_db=app_db, prefix=prefix, json_encoder=json_encoder, swaggerui_blueprint=swaggerui_blueprint, docs_decorators=docs_decorators, **kwargs)
        # the host shown in the swagger ui
        # this host may be different from the hostname of the server and
        # sometimes we don't want to show the port (eg when proxied)
        # in that case the port may be None
        if port:
            host = f"{host}:{port}"

        super().__init__(
            app,
            api_spec_url=kwargs.pop("api_spec_url", "/swagger"),
            host=host,
            description=description,
            prefix=prefix,
            base_path=prefix,
            **kwargs,
        )
        app.json = SAFRSJSONProvider(app)
        app.json_encoder = SAFRSJSONEncoder  # type: ignore[attr-defined]  # deprecated, but used by the swaggerui blueprint
        self.init_app(app)
        self._protect_docs_views(app)
        self.representations = OrderedDict(DEFAULT_REPRESENTATIONS)
        self.update_spec()
        self._register_public_docs_warning(app)
        app.extensions["safrs_api"] = self
        SAFRSAPI.client_uri = host

    def _protect_docs_views(self: Any, app: Any) -> None:
        """SEC-06: apply the configured documentation protection to the spec
        views registered by flask-restful-swagger (``swagger`` serves
        swagger.json and swagger.html). The ALS schema resource applies the
        same decorators in ``expose_als_schema``.
        """
        docs_decorators = list(app.extensions.get("safrs_docs_decorators", []))
        if not docs_decorators:
            return
        for endpoint in ("swagger",):
            view = app.view_functions.get(endpoint)
            if view is None:
                continue
            for decorator in reversed(docs_decorators):
                view = decorator(view)
            app.view_functions[endpoint] = view

    def _register_public_docs_warning(self: Any, app: Any) -> None:
        """SEC-06: warn once (on first request) when models carry SAFRS
        authorization policies but the documentation routes are public.
        """
        if app.extensions.get("safrs_docs_decorators"):
            return
        state: dict[str, bool] = {"warned": False}

        def maybe_warn() -> None:
            if state["warned"]:
                return
            state["warned"] = True
            protected = sorted(
                {
                    getattr(model, "_s_collection_name", getattr(model, "__name__", str(model)))
                    for model in self._model_method_decorators
                    if _model_has_authorization_policy(model)
                    or (
                        self.authorization is not None
                        and self.authorization.is_registered(model)
                    )
                    or _method_decorators_configured(self._model_method_decorators.get(model))
                }
            )
            if not protected:
                return
            safrs.log.warning(
                "SAFRS API documentation routes are publicly accessible although models %s "
                "carry SAFRS authorization policies. Protect them with docs_decorators=... "
                "Authentication configured outside "
                "SAFRS hooks (middleware, before_request, app-level dependencies) is not detected, "
                "so verify the docs routes match your authentication boundary.",
                protected,
            )

        app.before_request(maybe_warn)

    def update_spec(self: Any) -> None:
        """
        :param custom_swagger: swagger spec to be added to the swagger.json
        """
        _swagger_doc = self.get_swagger_doc()
        safrs.dict_merge(_swagger_doc, self._custom_swagger)

    def expose_object(self: Any, safrs_object: Any, url_prefix: Any='', **properties: Any) -> Any:
        """This methods creates the API url endpoints for the SAFRObjects
        :param safrs_object: SAFSBase subclass that we would like to expose
        :param url_prefix: url prefix
        :param properties: additional flask-restful properties

        creates a class of the form

        @api_decorator
        class Class_API(SAFRSRestAPI):
            SAFRSObject = safrs_object

        add the class as an api resource to /SAFRSObject and /SAFRSObject/{id}

        tablename/collectionname: safrs_object._s_collection_name, e.g. "Users"
        classname: safrs_object.__name__, e.g. "User"
        """
        if not current_app:
            safrs.log.error("Working outside of app context!")
        if not getattr(safrs_object, "_s_expose", True):
            raise SystemValidationError(f"Refusing to expose {safrs_object}: _s_expose is set to False")
        rest_api = safrs_object._rest_api  # => SAFRSRestAPI

        SAFRSAPI._ensure_authorization_state(self)
        configured_method_decorators = properties.get("method_decorators", [])
        response_authorizer = properties.pop("response_authorizer", None)
        self._response_authorizers[safrs_object] = (
            [response_authorizer] if response_authorizer is not None else []
        )
        if isinstance(configured_method_decorators, Mapping) and "head" not in configured_method_decorators:
            configured_method_decorators = dict(configured_method_decorators)
            configured_method_decorators["head"] = list(configured_method_decorators.get("get", []) or [])
            properties["method_decorators"] = configured_method_decorators
        self._model_method_decorators[safrs_object] = configured_method_decorators
        self._model_url_prefix[safrs_object] = str(url_prefix)
        # Policies registered for a related model must not be copied onto all
        # routes of the parent.  Concrete related resources are authorized
        # when they are serialized, and relationship routes carry only their
        # direct parent/relationship/target decorators.

        properties["SAFRSObject"] = safrs_object
        properties["http_methods"] = safrs_object.http_methods
        endpoint = SAFRSAPI._get_model_endpoint(safrs_object, url_prefix)

        # tags indicate where in the swagger hierarchy the endpoint will be shown
        tags = [safrs_object._s_collection_name]

        # Expose the methods first
        self.expose_methods(url_prefix, tags, safrs_object, properties)

        # Expose the collection: Create the class and decorate it
        api_class_name = f"{safrs_object._s_type}_API"  # name for dynamically generated classes
        RESOURCE_URL_FMT = cast(str, get_config("RESOURCE_URL_FMT"))  # configurable resource collection url formatter
        url = RESOURCE_URL_FMT.format(url_prefix, safrs_object._s_collection_name)
        swagger_decorator = swagger_doc(safrs_object) if self.swaggerui_blueprint else lambda x: x
        api_class = api_decorator(type(api_class_name, (rest_api,), properties), swagger_decorator)

        safrs.log.info(f"Exposing {safrs_object._s_collection_name} on {url}, endpoint: {endpoint}")
        self.add_resource(api_class, url, endpoint=endpoint, methods=["GET", "POST"])

        INSTANCE_URL_FMT = cast(str, get_config("INSTANCE_URL_FMT"))
        url = INSTANCE_URL_FMT.format(url_prefix, safrs_object._s_collection_name, safrs_object.__name__)
        endpoint = SAFRSAPI._get_model_endpoint(safrs_object, url_prefix, type="instance")

        # Expose the instances
        safrs.log.info(f"Exposing {safrs_object._s_type} instances on {url}, endpoint: {endpoint}")
        api_class = api_decorator(type(api_class_name + "_i", (rest_api,), properties), swagger_decorator)
        self.add_resource(api_class, url, endpoint=endpoint, methods=["GET", "PATCH", "DELETE"])

        try:
            object_doc = parse_object_doc(safrs_object)
        except Exception as exc:
            safrs.log.error("Failed to parse model documentation (%s)", type(exc).__name__)
            object_doc = {}
        object_doc["name"] = safrs_object._s_collection_name
        self._swagger_object["tags"].append(object_doc)

        for relationship in safrs_object._s_relationships.values():
            self.expose_relationship(relationship, url, tags, properties)

        # Add only definitions reachable from this API's paths. Schema's
        # registry is process-global in flask-restful-swagger-2; copying every
        # entry would disclose model schemas belonging to another Flask app.
        SAFRSAPI._sync_swagger_definitions(self)

        self.update_spec()
        self._als_resources.append(safrs_object)

    def expose(self: Any, *safrs_objects: Any, url_prefix: Any='', **properties: Any) -> Any:
        """
        Expose multiple objects at once
        """
        for obj in safrs_objects:
            self.expose_object(obj, url_prefix, **properties)

    def expose_methods(self: Any, url_prefix: Any, tags: Any, safrs_object: Any, properties: Any) -> Any:
        """
        Expose the safrs "documented_api_method" decorated methods
        :param url_prefix: api url prefix
        :param tags: swagger tags
        :return: None
        """
        rpc_api = safrs_object._rpc_api  # => SAFRSJSONRPCAPI
        api_methods = safrs_object._s_get_jsonapi_rpc_methods()
        for api_method in api_methods:
            method_name = api_method.__name__
            api_method_class_name = f"method_{safrs_object._s_class_name}_{method_name}"
            if self._is_class_level_rpc_method(safrs_object, method_name, api_method):
                # method is a classmethod or static method, make it available at the class level
                CLASSMETHOD_URL_FMT = cast(str, get_config("CLASSMETHOD_URL_FMT"))
                url = CLASSMETHOD_URL_FMT.format(url_prefix, safrs_object._s_collection_name, method_name)
            else:
                # expose the method at the instance level
                INSTANCEMETHOD_URL_FMT = cast(str, get_config("INSTANCEMETHOD_URL_FMT"))
                url = INSTANCEMETHOD_URL_FMT.format(url_prefix, safrs_object._s_collection_name, safrs_object._s_object_id, method_name)

            ENDPOINT_FMT = cast(str, get_config("ENDPOINT_FMT"))
            endpoint = ENDPOINT_FMT.format(url_prefix, safrs_object._s_collection_name + "." + method_name)
            swagger_decorator = swagger_method_doc(safrs_object, method_name, tags)
            properties.update({"method_name": method_name, "http_methods": safrs_object.http_methods})
            api_class = api_decorator(type(api_method_class_name, (rpc_api,), properties), swagger_decorator)
            meth_name = safrs_object._s_class_name + "." + api_method.__name__
            safrs.log.info(f"Exposing method {meth_name} on {url}, endpoint: {endpoint}")
            self.add_resource(api_class, url, endpoint=endpoint, methods=get_http_methods(api_method), jsonapi_rpc=True)

    @staticmethod
    def _is_class_level_rpc_method(safrs_object: Any, method_name: str, api_method: Any) -> bool:
        raw_method = inspect.getattr_static(safrs_object, method_name, None)
        if isinstance(raw_method, (classmethod, staticmethod)):
            return True
        if isinstance(safrs_object.__dict__.get(method_name, None), (classmethod, staticmethod)):
            return True
        return getattr(api_method, "__self__", None) is safrs_object

    def _ensure_authorization_state(self) -> None:
        """Initialize policy state for normal and partially constructed API instances."""
        if not hasattr(self, "_model_method_decorators"):
            self._model_method_decorators = {}
        if not hasattr(self, "_response_authorizers"):
            self._response_authorizers = {}
        if not hasattr(self, "_model_url_prefix"):
            self._model_url_prefix = {}

    @staticmethod
    def _get_model_endpoint(model: Any, url_prefix: str, **kwargs: Any) -> str:
        """Resolve an endpoint without storing the prefix on a shared model."""
        parameters = inspect.signature(model.get_endpoint).parameters
        if "url_prefix" in parameters:
            kwargs["url_prefix"] = url_prefix
        return str(model.get_endpoint(**kwargs))

    def expose_relationship(self: Any, relationship: Any, url_prefix: Any, tags: Any, properties: Any) -> Any:
        """
        Expose a relationship tp the REST API:
        A relationship consists of a parent and a target class
        creates a class of the form

        @api_decorator
        class Parent_X_target_API(SAFRSRestRelationshipAPI):
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
        relationship_api = target_object._relationship_api  # => SAFRSRestRelationshipAPI
        if not getattr(target_object, "_s_expose", False):  # todo: add test
            safrs.log.debug(f"Not exposing {target_object}")
            return

        API_CLASSNAME_FMT = "{}_X_{}_API"  # api class name for generated relationship classes
        rel_name = relationship.key
        parent_class = relationship.parent.class_
        parent_name = parent_class.__name__
        configured_methods = _http_method_set(getattr(relationship, "http_methods", parent_class.http_methods))
        allowed_methods = configured_methods & _http_method_set(parent_class.http_methods) & _http_method_set(target_object.http_methods)

        # Name of the endpoint class
        RELATIONSHIP_URL_FMT = cast(str, get_config("RELATIONSHIP_URL_FMT"))
        api_class_name = API_CLASSNAME_FMT.format(parent_name, rel_name)
        url = RELATIONSHIP_URL_FMT.format(url_prefix, rel_name)

        ENDPOINT_FMT = cast(str, get_config("ENDPOINT_FMT"))
        endpoint = ENDPOINT_FMT.format(url_prefix, rel_name)

        # Relationship object
        decorators = _dedupe_decorators(
            getattr(parent_class, "custom_decorators", [])
            + getattr(parent_class, "decorators", [])
            + getattr(relationship, "decorators", [])
            + _model_decorators(target_object)
        )
        rel_object = type(
            f"{parent_name}.{rel_name}",  # Name of the class we're creating here
            (SAFRSRelationshipObject,),
            {
                "relationship": relationship,
                # Merge the relationship decorators from the classes
                # This makes things really complicated!!!
                # TODO: simplify this by creating a proper superclass
                "custom_decorators": decorators,
                "parent": parent_class,
                "_target": target_object,
                "http_methods": allowed_methods,
            },
        )

        properties["SAFRSObject"] = rel_object
        properties["http_methods"] = allowed_methods
        swagger_decorator = swagger_relationship_doc(rel_object, tags)
        api_class = api_decorator(type(api_class_name, (relationship_api,), properties), swagger_decorator)

        # Expose the relationship for the parent class:
        # GET requests to this endpoint retrieve all item ids
        safrs.log.info(f"Exposing relationship {rel_name} on {url}, endpoint: {endpoint}")
        # Check if there are custom http methods specified
        self.add_resource(api_class, url, endpoint=endpoint, methods=sorted(allowed_methods), relationship=relationship)

        try:
            target_object_id = target_object._s_object_id
        except Exception as exc:
            safrs.log.error("Failed to resolve relationship target identifier (%s)", type(exc).__name__)
            safrs.log.error(f"No object id for {target_object}")
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
        endpoint = f"{url_prefix}api.{rel_name}Id"

        safrs.log.info(f"Exposing {parent_name} relationship {rel_name} on {url}, endpoint: {endpoint}")
        item_methods = [method for method in ["GET", "PATCH", "DELETE"] if method in allowed_methods]
        self.add_resource(
            api_class,
            url,
            relationship=cast(Any, rel_object).relationship,
            endpoint=endpoint,
            methods=item_methods,
            deprecated=True,
        )

    @staticmethod
    def get_resource_methods(resource: Any, ordered_methods: Any=None) -> Any:
        """
        :param ordered_methods:
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

    @staticmethod
    def _is_resource_method_allowed(method: str, methods: Optional[list[Any]]) -> bool:
        if not methods:
            return True
        return method.upper() in [str(m).upper() for m in methods]

    @staticmethod
    def _is_exposing_instance(swagger_url: str, safrs_instance_suffix: str, relationship: Any) -> bool:
        exposing_instance = swagger_url.strip("/").endswith(safrs_instance_suffix)
        if relationship:
            exposing_instance = relationship.direction == MANYTOONE
        return exposing_instance

    def _update_path_item_method(
        self,
        resource: Any,
        path_item: dict[str, Any],
        method: str,
        exposing_instance: bool,
        is_jsonapi_rpc: bool,
        swagger_url: str,
        relationship: Any,
    ) -> None:
        method_doc = path_item.get(method)
        if not method_doc:
            return

        collection_summary = method_doc.pop("collection_summary", method_doc.get("summary", None))
        if not exposing_instance and collection_summary:
            method_doc["summary"] = collection_summary

        path_item_method = cast(dict[str, Any], path_item.get(method))
        method_doc["operationId"] = self._get_operation_id(path_item_method.get("summary", ""))

        self._add_oas_req_params(resource, path_item, method, exposing_instance, is_jsonapi_rpc, swagger_url)
        self._add_oas_references(resource.SAFRSObject, path_item, method, exposing_instance, relationship)

        try:  # pragma: no cover
            validate_path_item_object(path_item)
        except FRSValidationError as exc:
            # Path items can contain user-supplied examples.  Never echo the
            # generated document or validator message into logs.
            safrs.log.critical("OpenAPI path validation failed (%s)", type(exc).__name__)
            exit(1)

    def _build_swagger_path_item(
        self,
        resource: Any,
        path_item: dict[str, Any],
        url: str,
        relationship: Any,
        is_jsonapi_rpc: bool,
        deprecated: bool,
        methods: Optional[list[Any]],
        safrs_instance_suffix: str,
    ) -> None:
        if deprecated:
            # functionality still works, but there will be no swagger
            return
        if not url.startswith("/"):  # pragma: no cover
            raise SystemValidationError("paths must start with a /")

        swagger_url = extract_swagger_path(url)
        exposing_instance = self._is_exposing_instance(swagger_url, safrs_instance_suffix, relationship)
        for method in self.get_resource_methods(resource):
            if not self._is_resource_method_allowed(method, methods):
                path_item.pop(method, None)
                continue
            if method == "post" and exposing_instance:
                # POSTing to an instance isn't jsonapi-compliant
                path_item.pop(method, None)
                continue
            self._update_path_item_method(
                resource,
                path_item,
                method,
                exposing_instance,
                is_jsonapi_rpc,
                swagger_url,
                relationship,
            )

        self._swagger_object["paths"][swagger_url] = path_item
        try:
            json.dumps(self._swagger_object)
        except Exception:  # pragma: no cover
            safrs.log.critical("Json encoding failed")

    @staticmethod
    def _set_method_not_allowed_handlers(resource: Any) -> None:
        def method_not_allowed(*_args: Any, **_kwargs: Any) -> tuple[dict[str, Any], HTTPStatus]:
            return {}, HTTPStatus.METHOD_NOT_ALLOWED

        for http_method in HTTP_METHODS:
            hm = http_method.lower()
            if hm not in SAFRSAPI.get_resource_methods(resource):
                setattr(resource, hm, method_not_allowed)

    def add_resource(self: Any, resource: Any, *urls: Any, **kwargs: Any) -> Any:
        """
        This method is partly copied from flask_restful_swagger_2/__init__.py

        Changed because we don't need path id examples when there's no {id} in the path.
        We also have to filter out the unwanted parameters
        """
        relationship = kwargs.pop("relationship", False)  # relationship object
        SAFRS_INSTANCE_SUFFIX = cast(str, get_config("OBJECT_ID_SUFFIX")) + "}"
        methods = kwargs.get("methods", None)

        path_item: dict[str, Any] = {}
        self._add_oas_resource_definitions(resource, path_item)
        is_jsonapi_rpc = kwargs.pop("jsonapi_rpc", False)  # check if the exposed method is a jsonapi_rpc method
        deprecated = kwargs.pop("deprecated", False)  # deprecated functionality: still working but not shown in swagger

        for url in urls:
            self._build_swagger_path_item(
                resource,
                path_item,
                str(url),
                relationship,
                is_jsonapi_rpc,
                deprecated,
                methods,
                SAFRS_INSTANCE_SUFFIX,
            )

        # disable API methods that were not set by the SAFRSObject
        self._set_method_not_allowed_handlers(resource)
        # pylint: disable=bad-super-call
        super(FRSApiBase, self).add_resource(resource, *urls, **kwargs)

    def _add_oas_req_params(self: Any, resource: Any, path_item: Any, method: Any, exposing_instance: Any, is_jsonapi_rpc: Any, swagger_url: Any) -> Any:
        """
        Add the request parameters to the swagger (filter, sort)
        """
        method_doc = path_item[method]
        parameters = []
        for parameter in method_doc.get("parameters", []):
            object_id = "{%s}" % parameter.get("name")
            if method == "get":
                # Get the jsonapi included resources, ie the exposed relationships
                param = resource.get_swagger_include()
                parameters.append(param)

                # Get the jsonapi fields[], ie the exposed attributes/columns
                # only required for collections though
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
        path_item[method] = method_doc

    def _add_oas_references(self: Any, safrs_object: Any, path_item: Any, method: Any, exposing_instance: Any, relationship: Any) -> Any:
        """
        substitute the swagger references in the response objects
        references are created and added to the safrs_object.swagger_models in swagger_doc

        the params are
        :param safrs_object:
        :param path_item:

        """
        inst_ref = None
        coll_ref = None

        if getattr(safrs_object, "swagger_models", {}).get("instance"):
            # instance reference
            inst_ref = safrs_object.swagger_models["instance"].reference()

        if getattr(safrs_object, "swagger_models", {}).get("collection"):
            # collection reference
            coll_ref = safrs_object.swagger_models["collection"].reference()

        if not inst_ref and not coll_ref:
            return

        method_doc = path_item[method]
        response = method_doc.get("responses", {})
        if "200" in response:
            # add the "example" response schema references
            if exposing_instance:
                response["200"]["schema"] = inst_ref
            elif coll_ref:
                response["200"]["schema"] = coll_ref
            response["200"].pop("type", None)

        if "201" in response:
            if method == "post":
                # Posting to a collection returns the instance (except when using bulk post, but this isn't shown atm)
                response["201"]["schema"] = inst_ref
            elif exposing_instance:
                # patching an instance
                response["201"]["schema"] = inst_ref
            elif coll_ref:
                # patching a
                response["201"]["schema"] = coll_ref
            response["201"]["schema"].pop("type", None)

    def _add_oas_resource_definitions(self: Any, resource: Any, path_item: Any) -> Any:
        """
        add the resource method schema references to the swagger "definitions"
        :param resource:
        :param path_item:
        """
        definitions = {}

        for method in self.get_resource_methods(resource):
            if not method.upper() in HTTP_METHODS:
                continue
            f = getattr(resource, method, None)
            if not f:
                continue

            operation = getattr(f, "__swagger_operation_object", None)
            if operation:
                operation, definitions_ = Extractor.extract(operation)
                path_item[method] = operation
                definitions.update(definitions_)
                summary = parse_method_doc(f, operation)
                if summary:
                    operation["summary"] = summary.split("<br/>")[0]

        try:
            validate_definitions_object(definitions)
        except FRSValidationError:
            safrs.log.critical(f"Validation failed for {definitions}")
            exit()

        self._swagger_object["definitions"].update(definitions)

    @staticmethod
    def _referenced_definition_names(value: Any) -> set[str]:
        result: set[str] = set()
        if isinstance(value, dict):
            reference = value.get("$ref")
            prefix = "#/definitions/"
            if isinstance(reference, str) and reference.startswith(prefix):
                result.add(reference[len(prefix) :])
            for nested_value in value.values():
                result.update(SAFRSAPI._referenced_definition_names(nested_value))
        elif isinstance(value, list):
            for nested_value in value:
                result.update(SAFRSAPI._referenced_definition_names(nested_value))
        return result

    def _sync_swagger_definitions(self) -> None:
        pending = list(
            SAFRSAPI._referenced_definition_names(self._swagger_object.get("paths", {}))
        )
        visited: set[str] = set()
        while pending:
            def_name = pending.pop()
            if def_name in visited:
                continue
            visited.add(def_name)
            if def_name in self._swagger_object["definitions"]:
                definition_value = self._swagger_object["definitions"][def_name]
                pending.extend(
                    SAFRSAPI._referenced_definition_names(definition_value) - visited
                )
                continue
            definition = Schema._references.get(def_name)
            if definition is None:
                continue
            try:
                validate_definitions_object(definition.properties)
            except Exception as exc:  # pragma: no cover
                safrs.log.warning("Failed to validate OpenAPI definition (%s)", type(exc).__name__)
                continue
            definition_value = {"properties": definition.properties}
            self._swagger_object["definitions"][def_name] = definition_value
            pending.extend(
                SAFRSAPI._referenced_definition_names(definition_value) - visited
            )

    def _get_operation_id(self: Any, summary: str) -> str:
        """
        :param summary:
        """
        summary = "".join(c for c in summary if c.isalnum())
        if summary not in self._operation_ids:
            self._operation_ids[summary] = 0
        else:
            self._operation_ids[summary] += 1
        return f"{summary}_{self._operation_ids[summary]}"

    def expose_als_schema(self: Any, api_root: Any='/api', schema_loc: Any='/als_schema') -> Any:
        """
        Generate the resource specification for apilogicserver
        """
        resources: dict[str, Any] = {}
        result = {"resources": resources, "api_root": api_root}
        for resource in self._als_resources:
            resource_data = {"type": resource._s_type, "label": None}
            attributes = []
            for name, attr_def in resource._s_jsonapi_attrs.items():
                attr = {}
                attr["name"] = name
                # column["type"] = col.python_type
                attributes.append(attr)
            resource_data["attributes"] = attributes
            resource_data["perPage"] = 10
            relations = []
            for rel_name, rel in resource._s_relationships.items():
                relation = {}
                relation["name"] = rel_name
                relation["resource"] = str(rel.target.key)
                relation["fks"] = [str(c.key) for c in rel._calculated_foreign_keys]
                relation["direction"] = "toone" if rel.direction == MANYTOONE else "tomany"
                relations.append(relation)
            resource_data["tab_groups"] = relations

            resources[resource._s_collection_name] = resource_data

        class ApiSchema(Resource):
            def get(self: Any) -> Any:
                if request.args.get("yaml"):
                    return Response(yaml.dump(result), content_type="text/yaml")
                return result

        # SEC-06: apply the configured documentation protection (empty in
        # DEBUG mode, see SAFRS.init_app). flask-restful dispatches
        # ``Resource.method_decorators`` for every request.
        app = getattr(self, "app", None)
        ApiSchema.method_decorators = list(
            (getattr(app, "extensions", {}) or {}).get("safrs_docs_decorators", [])
        )
        self.add_resource(ApiSchema, schema_loc)
        return json.dumps(result, indent=4)


def api_decorator(cls: Any, swagger_decorator: Any) -> Any:
    """Decorator for the API views:
        - add swagger documentation ( swagger_decorator )
        - add cors
        - add generic exception handling

    We couldn't use inheritance because the rest method decorator
    references the cls.SAFRSObject which isn't known

    :param cls: The class that will be decorated (e.g. SAFRSRestAPI, SAFRSRestRelationshipAPI)
    :param swagger_decorator: function that will generate the swagger
    :return: decorated class
    """

    cors_domain = get_config("cors_domain")
    cls.http_methods = {}  # holds overridden http methods, note: cls also has "methods" set, but it's not related to this
    for method_name in [
        "patch",
        "post",
        "delete",
        "get",
        "put",
        "head",
        "options",
    ]:  # HTTP methods, "put" may be used by a custom implementation
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

        if method_name not in {"head", "options"}:
            try:
                # Add swagger documentation
                decorated_method = swagger_decorator(decorated_method)
            except RecursionError:  # pragma: no cover
                # Got this error when exposing WP DB, TODO: investigate where it comes from
                safrs.log.error(f"Failed to generate documentation for {cls} {decorated_method} (Recursion Error)")

            except Exception as exc:
                safrs.log.error("Failed to generate documentation (%s)", type(exc).__name__)
                safrs.log.error(f"Failed to generate documentation for {decorated_method}")

            # The user can add custom decorators
            # Apply the custom decorators, specified as class variable list
            custom_decorators = list(getattr(cls.SAFRSObject, "custom_decorators", [])) + list(
                getattr(cls.SAFRSObject, "decorators", [])
            )
            for custom_decorator in _dedupe_decorators(custom_decorators):
                # update_wrapper(custom_decorator, decorated_method)
                swagger_operation_object = getattr(decorated_method, "__swagger_operation_object", {})
                decorated_method = custom_decorator(decorated_method)
                decorated_method.__swagger_operation_object = swagger_operation_object

        elif method_name == "head":
            custom_decorators = list(getattr(cls.SAFRSObject, "custom_decorators", [])) + list(
                getattr(cls.SAFRSObject, "decorators", [])
            )
            # HEAD inherits GET authorization semantics. Temporarily expose a
            # GET function name so conditional decorators such as the
            # documented per-method pattern select their read policy.
            decorated_method.__name__ = "get"
            for custom_decorator in _dedupe_decorators(custom_decorators):
                decorated_method = custom_decorator(decorated_method)
            decorated_method.__name__ = "head"

        setattr(cls, method_name, decorated_method)
    return cls


def http_method_decorator(fun: Callable) -> Callable:
    """Decorator for the supported jsonapi HTTP methods (get, post, patch, delete)
    - commit the database
    - convert all exceptions to a JSON serializable GenericError

    This method will be called for all requests
    :param fun:
    :return: wrapped fun
    """

    @wraps(fun)
    def method_wrapper(*args: Any, **kwargs: Any) -> Any:
        """Wrap the method and perform error handling
        :param *args:
        :param **kwargs:
        :return: result of the wrapped method
        """
        safrs_exception: Any = None
        status_code: int = 500
        message: str = ""
        resource_name: Optional[str] = None
        object_id = kwargs.get("object_id", kwargs.get("id"))
        if args:
            safrs_object = getattr(args[0], "SAFRSObject", None)
            if safrs_object is not None:
                resource_name = getattr(safrs_object, "_s_collection_name", None)
                if resource_name is None:
                    parent = getattr(safrs_object, "parent", None)
                    if parent is not None:
                        resource_name = getattr(parent, "_s_collection_name", None)
        token = tx.begin_request()
        try:
            try:
                filter_error = getattr(cast(Any, request), "filter_validation_error", "")
                if filter_error:
                    raise ValidationError(
                        str(filter_error).removeprefix("Validation Error: ")
                    )
                if not cast(Any, request).is_jsonapi and fun.__name__ not in ["get", "head", "options", "delete"]:  # pragma: no cover
                    # reuire jsonapi content type for requests to these routes
                    raise GenericError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE.description, HTTPStatus.UNSUPPORTED_MEDIA_TYPE.value)

                request_method = str(getattr(request, "method", "")).upper()
                if request_method in WRITE_HTTP_METHODS and args:
                    safrs_object = getattr(args[0], "SAFRSObject", None)
                    if safrs_object is not None:
                        # Relationship resources expose a synthetic wrapper class.
                        # Track writes against underlying models so db_commit opt-out
                        # on parent/target classes is honored.
                        parent = getattr(safrs_object, "parent", None)
                        target = getattr(safrs_object, "_target", None)
                        if parent is not None:
                            tx.note_write(parent)
                        if target is not None:
                            tx.note_write(target)
                        if parent is None and target is None:
                            tx.note_write(safrs_object)

                result = fun(*args, **kwargs)
                if request_method in WRITE_HTTP_METHODS and tx.should_autocommit():
                    get_db().session.commit()
                else:
                    get_db().session.rollback()
                return result

            except werkzeug.exceptions.NotFound as exc:
                # this also catches safrs.errors.NotFoundError
                status_code = 404
                safrs_exception = exc
                message = HTTPStatus.NOT_FOUND.description

            except JsonapiError as exc:
                safrs.log.info("JSON:API request rejected (%s)", type(exc).__name__)
                safrs_exception = exc

            except sqlalchemy.exc.IntegrityError as exc:
                log_integrity_error_details(
                    exc,
                    resource=str(resource_name) if resource_name else None,
                    object_id=str(object_id) if object_id is not None else None,
                )
                get_db().session.rollback()
                errors = dict(
                    title=HTTPStatus.CONFLICT.description,
                    detail="Database constraint violation",
                    code=str(HTTPStatus.CONFLICT.value),
                )
                abort(HTTPStatus.CONFLICT.value, errors=[errors])

            except (sqlalchemy.exc.DataError, sqlalchemy.exc.StatementError, OverflowError):
                get_db().session.rollback()
                errors = dict(
                    title=HTTPStatus.BAD_REQUEST.description,
                    detail="Invalid attribute value",
                    code=str(HTTPStatus.BAD_REQUEST.value),
                )
                abort(HTTPStatus.BAD_REQUEST.value, errors=[errors])

            except (FlushError, sqlalchemy.exc.InvalidRequestError):
                get_db().session.rollback()
                errors = dict(
                    title=HTTPStatus.CONFLICT.description,
                    detail="Relationship update violates DB constraints",
                    code=str(HTTPStatus.CONFLICT.value),
                )
                abort(HTTPStatus.CONFLICT.value, errors=[errors])

            except AssertionError as exc:
                if not _is_relationship_pk_disassociation_assertion(exc):
                    raise
                get_db().session.rollback()
                errors = dict(
                    title=HTTPStatus.CONFLICT.description,
                    detail="Relationship update violates DB constraints",
                    code=str(HTTPStatus.CONFLICT.value),
                )
                abort(HTTPStatus.CONFLICT.value, errors=[errors])

            except werkzeug.exceptions.HTTPException as exc:
                status_code = cast(int, exc.code)
                message = cast(str, exc.description)
                safrs.log.info("HTTP request rejected (%s)", status_code)

            except Exception as exc:
                safrs.log.error("Unhandled request failure (%s)", type(exc).__name__)
                safrs_exception = exc
                safrs_exception.message = "Internal Server Error"

            status_code = getattr(safrs_exception, "status_code", status_code)
            api_code = getattr(safrs_exception, "api_code", status_code)
            title = getattr(safrs_exception, "message", message)
            detail = getattr(safrs_exception, "detail", title)

            get_db().session.rollback()
            errors = dict(title=title, detail=detail, code=str(api_code))
            abort(status_code, errors=[errors])
        finally:
            tx.end_request(token)

    return method_wrapper
