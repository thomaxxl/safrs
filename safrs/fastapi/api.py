# -*- coding: utf-8 -*-

import datetime as dt
import inspect
import re
from enum import Enum
from http import HTTPStatus
from typing import Annotated, Any, Callable, Dict, Iterable, List, NoReturn, Optional, Sequence, Set, Tuple, Type, Union, cast, get_args, get_origin
from urllib.parse import quote

import safrs
import anyio
from safrs import tx
from safrs.base import (
    check_relationship_write_permission,
    model_has_resource_authorization,
    run_instance_access_check,
)
from safrs.api_doc import (
    FILTERABLE,
    PAGEABLE,
    get_doc,
    get_http_methods,
    jsonapi_rpc_meta_schema,
    resolve_rpc_method,
    schema_for_example_value,
)
from safrs.errors import (
    GenericError,
    JsonapiError,
    SystemValidationError,
    ValidationError,
    log_integrity_error_details,
    reset_fastapi_request_url,
    set_fastapi_request_url,
)
from safrs.jsonapi_context import JsonApiContext, maybe_jsonapi_context, reset_jsonapi_context, set_jsonapi_context
from safrs.jsonapi_formatting import jsonapi_format_response
from safrs.filtering import (
    apply_filter_read_permissions,
    bracket_filter_expression,
    coerce_filter_values,
    custom_filter_read_fields,
    filter_attribute_names,
    get_filterable_attribute,
    has_custom_instance_permission_check,
    materialize_for_authorization,
    parse_bracket_filter_name,
    require_filterable_attribute,
    uses_builtin_json_filter,
    validate_bracket_filter_count,
    validate_filter_result,
)
from safrs.rpc import (
    bind_rpc_kwargs as shared_bind_rpc_kwargs,
    is_resource_instance as shared_is_resource_instance,
    normalize_rpc_result as shared_normalize_rpc_result,
    parse_rpc_args as shared_parse_rpc_args,
    unwrap_formatted_response as shared_unwrap_formatted_response,
)
from safrs.config import get_config, is_debug

from fastapi import APIRouter, Body, Depends as FastAPIDepends, FastAPI, HTTPException, Path, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.params import Depends as DependsParam
from fastapi.routing import APIRoute
from pydantic import BaseModel
from pydantic.json_schema import models_json_schema
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse
from sqlalchemy.exc import CircularDependencyError, DataError, IntegrityError, InvalidRequestError, StatementError
from sqlalchemy.orm.interfaces import MANYTOMANY, ONETOMANY
from sqlalchemy.orm.exc import FlushError

from .relationships import relationship_is_exposed, relationship_property, resolve_relationships
from .schemas import SchemaRegistry
from .schemas.examples import (
    create_document_example,
    patch_document_example,
    relationship_to_many_example,
    relationship_to_one_example,
)
from .responses import JSONAPIResponse
from .authorization import AuthorizationContext, current_authorization
from safrs.request import validate_json_payload
from safrs.runtime import bind_db, get_db, reset_db, set_db
from safrs.authorization import (
    apply_authorization_scope,
    begin_current_protected_write,
    current_model_is_registered,
    current_query_fields,
    prepare_current_readable_fields,
    reject_current_rpc,
    require_current_instance,
)

JSONAPI_MEDIA_TYPE = "application/vnd.api+json"
DEFAULT_HTTP_METHODS = {"GET", "POST", "PATCH", "DELETE"}
WRITE_HTTP_METHODS = {"POST", "PATCH", "DELETE", "PUT"}
NonEmptyPathStr = Annotated[str, Path(min_length=1)]
ObjectIdParam = NonEmptyPathStr
TargetIdParam = NonEmptyPathStr


class _PayloadTooLarge(Exception):
    pass


class _RequestBodyLimitMiddleware:
    """Reject oversized ASGI request bodies, including streamed bodies."""

    def __init__(self, app: Any, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope.get("type") != "http" or self.max_bytes <= 0:
            await self.app(scope, receive, send)
            return
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                if int(content_length) > self.max_bytes:
                    await self._reject(scope, receive, send)
                    return
            except ValueError:
                await self._reject(scope, receive, send)
                return

        received = 0

        async def limited_receive() -> Any:
            nonlocal received
            message = await receive()
            if message.get("type") == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _PayloadTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _PayloadTooLarge:
            await self._reject(scope, receive, send)

    @staticmethod
    async def _reject(scope: Any, receive: Any, send: Any) -> None:
        response = JSONResponse(
            status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE.value,
            content={"errors": [{"status": "413", "title": "Request Entity Too Large"}]},
            media_type=JSONAPI_MEDIA_TYPE,
        )
        await response(scope, receive, send)


class _RuntimeBindingMiddleware:
    """Bind an adapter's database before FastAPI enters worker threads."""

    def __init__(self, app: Any, app_db: Any) -> None:
        self.app = app
        self.app_db = app_db

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        # Context is copied from the ASGI task into synchronous dependencies
        # and endpoints. Binding here therefore reaches every generated route
        # without consulting the mutable process-global database per request.
        db_token = set_db(self.app_db)
        request_url_token = set_fastapi_request_url(str(scope.get("path", "")))
        try:
            await self.app(scope, receive, send)
        finally:
            reset_fastapi_request_url(request_url_token)
            reset_db(db_token)


class RelationshipItemMode(str, Enum):
    DISABLED = "disabled"
    HIDDEN = "hidden"
    ENABLED = "enabled"


class JSONAPIHTTPError(Exception):
    def __init__(self, status_code: int, payload: Dict[str, Any]) -> None:
        self.status_code = status_code
        self.payload = payload


def _normalize_expected_validation_exception_types(
    exc_types: Optional[Sequence[Type[Exception]]],
) -> Tuple[Type[Exception], ...]:
    if not exc_types:
        return ()

    normalized: List[Type[Exception]] = []
    for exc_type in exc_types:
        if not inspect.isclass(exc_type) or not issubclass(exc_type, Exception):
            raise TypeError("expected_validation_exceptions must contain exception classes")
        if exc_type not in normalized:
            normalized.append(exc_type)
    return tuple(normalized)


def _coerce_expected_validation_exception(
    exc: Exception,
    expected_validation_exceptions: Sequence[Type[Exception]],
) -> Optional[ValidationError]:
    if not expected_validation_exceptions:
        return None
    if isinstance(exc, tuple(expected_validation_exceptions)):
        return ValidationError(str(exc))
    return None


def _escape_json_pointer_segment(segment: str) -> str:
    return segment.replace("~", "~0").replace("/", "~1")


def _json_pointer_from_loc(loc: Sequence[Union[str, int]]) -> Optional[str]:
    if not loc:
        return None
    if str(loc[0]) != "body":
        return None
    pointer_segments: List[str] = []
    for segment in loc[1:]:
        pointer_segments.append(_escape_json_pointer_segment(str(segment)))
    if not pointer_segments:
        return None
    return "/" + "/".join(pointer_segments)


def _jsonapi_error_document(errors: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"jsonapi": {"version": "1.0"}, "errors": errors}


def _jsonapi_validation_errors(exc: RequestValidationError) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for raw_error in exc.errors():
        location = raw_error.get("loc", ())
        loc_items: Sequence[Union[str, int]]
        if isinstance(location, tuple):
            loc_items = cast(Sequence[Union[str, int]], location)
        elif isinstance(location, list):
            loc_items = cast(Sequence[Union[str, int]], location)
        else:
            loc_items = ()

        error_item: Dict[str, Any] = {
            "status": str(HTTPStatus.UNPROCESSABLE_ENTITY.value),
            "title": "Validation Error",
            "detail": str(raw_error.get("msg", "Validation error")),
        }
        error_code = raw_error.get("type")
        if error_code is not None:
            error_item["code"] = str(error_code)

        source: Dict[str, Any] = {}
        root = str(loc_items[0]) if loc_items else ""
        if root == "body":
            pointer = _json_pointer_from_loc(loc_items)
            if pointer:
                source["pointer"] = pointer
        elif root == "query" and len(loc_items) > 1:
            source["parameter"] = str(loc_items[1])
        if source:
            error_item["source"] = source
        elif root in {"path", "header", "cookie"}:
            error_item["meta"] = {"location": [str(item) for item in loc_items]}
        result.append(error_item)
    if result:
        return result
    return [
        {
            "status": str(HTTPStatus.UNPROCESSABLE_ENTITY.value),
            "title": "Validation Error",
            "detail": "Request validation failed",
        }
    ]


def _jsonapi_http_exception_payload(exc: StarletteHTTPException) -> Dict[str, Any]:
    detail = exc.detail
    if isinstance(detail, str):
        detail_text = detail
    else:
        detail_text = str(detail)
    status_code = int(exc.status_code)
    try:
        title = HTTPStatus(status_code).phrase
    except ValueError:
        title = "HTTP Error"
    return _jsonapi_error_document(
        [
            {
                "status": str(status_code),
                "title": title,
                "detail": detail_text,
            }
        ]
    )


def install_jsonapi_exception_handlers(
    app: FastAPI,
    *,
    expected_validation_exceptions: Optional[Sequence[Type[Exception]]] = None,
) -> None:
    normalized_expected_validation_exceptions = _normalize_expected_validation_exception_types(
        expected_validation_exceptions
    )

    @app.exception_handler(JSONAPIHTTPError)
    async def _jsonapi_http_error_handler(_request: Request, exc: JSONAPIHTTPError):
        return JSONAPIResponse(status_code=exc.status_code, content=exc.payload)

    @app.exception_handler(RequestValidationError)
    async def _jsonapi_validation_error_handler(_request: Request, exc: RequestValidationError):
        payload = _jsonapi_error_document(_jsonapi_validation_errors(exc))
        return JSONAPIResponse(status_code=HTTPStatus.UNPROCESSABLE_ENTITY.value, content=payload)

    @app.exception_handler(StarletteHTTPException)
    async def _jsonapi_starlette_http_error_handler(_request: Request, exc: StarletteHTTPException):
        payload = _jsonapi_http_exception_payload(exc)
        return JSONAPIResponse(status_code=int(exc.status_code), content=payload)

    for expected_exception in normalized_expected_validation_exceptions:
        @app.exception_handler(expected_exception)
        async def _jsonapi_expected_validation_error_handler(_request: Request, exc: Exception):
            payload = _jsonapi_error_document(
                [
                    {
                        "status": str(HTTPStatus.BAD_REQUEST.value),
                        "title": "ValidationError",
                        "detail": str(exc),
                    }
                ]
            )
            return JSONAPIResponse(status_code=HTTPStatus.BAD_REQUEST.value, content=payload)

    @app.exception_handler(Exception)
    async def _jsonapi_unhandled_exception_handler(_request: Request, exc: Exception):
        try:
            get_db().session.rollback()
        except Exception as rollback_error:
            safrs.log.debug("Rollback during unhandled exception failed (%s)", type(rollback_error).__name__)
        safrs.log.error("Unhandled FastAPI exception (%s)", type(exc).__name__)
        payload = _jsonapi_error_document(
            [
                {
                    "status": str(HTTPStatus.INTERNAL_SERVER_ERROR.value),
                    "title": HTTPStatus.INTERNAL_SERVER_ERROR.phrase,
                    "detail": "Internal Server Error",
                }
            ]
        )
        return JSONAPIResponse(status_code=HTTPStatus.INTERNAL_SERVER_ERROR.value, content=payload)


class SafrsFastAPI:
    def runtime_context(self) -> Any:
        """Bind this API's database for a background task or script."""
        return bind_db(self.db if self.db is not None else get_db())

    def __init__(
        self,
        app: FastAPI,
        prefix: str = "",
        dependencies: Optional[List[Any]] = None,
        relationship_item_mode: Union[RelationshipItemMode, str] = RelationshipItemMode.HIDDEN,
        include_examples_in_openapi: bool = True,
        cleanup_session: bool = True,
        expected_validation_exceptions: Optional[Sequence[Type[Exception]]] = None,
        docs_dependencies: Optional[List[Any]] = None,
        *,
        app_db: Any = None,
        read_dependencies: Optional[List[Any]] = None,
        create_dependencies: Optional[List[Any]] = None,
        update_dependencies: Optional[List[Any]] = None,
        delete_dependencies: Optional[List[Any]] = None,
        response_authorizer: Optional[Callable[[Type[Any], Any, Request], Any]] = None,
        authorization: Any = None,
        principal_dependency: Optional[Callable[..., Any]] = None,
    ) -> None:
        self.app = app
        # Capture the legacy global once when ``app_db`` is omitted.  Looking
        # it up for every request would let another application silently
        # redirect this API to its session after construction.
        self.db = app_db if app_db is not None else safrs.DB
        self.authorization = authorization
        self.principal_dependency = principal_dependency
        if (self.authorization is None) != (self.principal_dependency is None):
            raise ValueError("authorization and principal_dependency must be configured together")
        if self.authorization is not None:
            metadata = getattr(self.db, "metadata", None)
            if metadata is None:
                metadata = self.db.Model.metadata
            self.authorization.bind(metadata)
            self.authorization.freeze()
        self.prefix = prefix
        self.cleanup_session = bool(cleanup_session)
        self.expected_validation_exceptions = _normalize_expected_validation_exception_types(
            expected_validation_exceptions
        )
        self.max_union_included_types = int(getattr(safrs.SAFRS, "MAX_UNION_INCLUDED_TYPES", 0))
        self.document_relationships = bool(getattr(safrs.SAFRS, "DOCUMENT_RELATIONSHIPS", True))
        self.validate_requests = bool(getattr(safrs.SAFRS, "VALIDATE_REQUESTS", False))
        self.validate_responses = bool(getattr(safrs.SAFRS, "VALIDATE_RESPONSES", False))
        self.include_examples_in_openapi = bool(include_examples_in_openapi)
        self.relationship_item_mode = self._coerce_relationship_item_mode(relationship_item_mode)
        self.max_request_body_bytes = int(getattr(safrs.SAFRS, "MAX_REQUEST_BODY_BYTES", 0) or 0)
        self.app.add_middleware(_RuntimeBindingMiddleware, app_db=self.db)
        self.app.add_middleware(
            _RequestBodyLimitMiddleware,
            max_bytes=self.max_request_body_bytes,
        )
        self.schemas = SchemaRegistry(
            document_relationships=self.document_relationships,
            max_union_included_types=self.max_union_included_types,
        )
        self._openapi_payload_models: Set[Type[BaseModel]] = set()
        self._model_dependencies: Dict[Type[Any], List[DependsParam]] = {}
        self._models_by_resource_type: Dict[str, Type[Any]] = {}
        self._authorization_limiter = anyio.CapacityLimiter(40)
        self._default_operation_dependencies = {
            "read": self._normalize_dependencies(read_dependencies),
            "create": self._normalize_dependencies(create_dependencies),
            "update": self._normalize_dependencies(update_dependencies),
            "delete": self._normalize_dependencies(delete_dependencies),
        }
        self._operation_dependencies: Dict[Type[Any], Dict[str, List[DependsParam]]] = {}
        self._default_response_authorizers = [response_authorizer] if response_authorizer else []
        self._response_authorizers: Dict[Type[Any], List[Callable[[Type[Any], Any, Request], Any]]] = {}
        self._docs_protected = bool(docs_dependencies)
        self._public_docs_warning_emitted = False
        self.default_dependencies = [
            FastAPIDepends(self._safrs_uow_dependency, scope="function"),
            FastAPIDepends(self._authorization_context_dependency, scope="function"),
        ]
        if self.authorization is not None and self.principal_dependency is not None:
            registry_dependency = self._make_registry_context_dependency(self.principal_dependency)
            self.default_dependencies.append(FastAPIDepends(registry_dependency, scope="function"))
        self.default_dependencies += self._normalize_dependencies(dependencies)
        self._install_swagger_ui_defaults()
        self._install_swagger_alias()
        self._install_docs_protection(docs_dependencies)
        install_jsonapi_exception_handlers(
            app,
            expected_validation_exceptions=self.expected_validation_exceptions,
        )
        self._install_openapi_schema_patch()
        safrs.log.info(
            "Initialized SafrsFastAPI (prefix=%s, relationship_item_mode=%s, cleanup_session=%s, expected_validation_exceptions=%s)",
            self.prefix,
            self.relationship_item_mode.value,
            self.cleanup_session,
            len(self.expected_validation_exceptions),
        )

    def _make_registry_context_dependency(
        self, principal_dependency: Callable[..., Any]
    ) -> Callable[..., Any]:
        registry = self.authorization

        async def registry_context(
            request: Request,
            principal: Any = FastAPIDepends(principal_dependency),
        ) -> Any:
            context = maybe_jsonapi_context()
            if context is None:
                raise RuntimeError("SAFRS authorization context is not active")
            context.authorization_registry = registry
            context.authorization_context = registry.validate_context(principal)
            request.state.safrs_auth_context = context.authorization_context
            try:
                yield
            finally:
                context.authorization_context = None
                context.authorization_field_masks.clear()
                context.authorization_decisions.clear()

        return registry_context

    @staticmethod
    def _coerce_relationship_item_mode(mode: Union[RelationshipItemMode, str]) -> RelationshipItemMode:
        if isinstance(mode, RelationshipItemMode):
            return mode
        normalized = str(mode).strip().lower()
        for candidate in RelationshipItemMode:
            if candidate.value == normalized:
                return candidate
        valid_values = ", ".join(candidate.value for candidate in RelationshipItemMode)
        raise ValueError(f"Invalid relationship_item_mode '{mode}', expected one of: {valid_values}")

    def _install_swagger_alias(self) -> None:
        for route in self.app.routes:
            if getattr(route, "path", None) == "/swagger.json":
                return

        @self.app.get("/swagger.json", include_in_schema=False)
        def swagger_json() -> Dict[str, Any]:
            return self.app.openapi()

    def _install_swagger_ui_defaults(self) -> None:
        params = dict(getattr(self.app, "swagger_ui_parameters", None) or {})
        params.setdefault("docExpansion", "none")
        params.setdefault("defaultModelsExpandDepth", -1)
        self.app.swagger_ui_parameters = params

    def _install_docs_protection(self, docs_dependencies: Optional[List[Any]]) -> None:
        """Protect documentation routes using FastAPI's dependency solver.

        Docs dependencies are route dependencies, not manually replayed
        callables.  This preserves nested ``Depends``/``Security``, dependency
        overrides, request caching, and generator cleanup.  Configuring a docs
        policy is security-sensitive and remains effective at DEBUG log level.
        """
        if not docs_dependencies:
            return
        dependencies = self._normalize_dependencies(list(docs_dependencies))
        protected_paths = {
            str(path).rstrip("/")
            for path in (
                getattr(self.app, "openapi_url", None),
                getattr(self.app, "docs_url", None),
                getattr(self.app, "redoc_url", None),
                "/swagger.json",
            )
            if path
        }

        original_routes = list(self.app.routes)
        protected_routes = [
            route
            for route in original_routes
            if str(getattr(route, "path", "")).rstrip("/") in protected_paths
        ]
        self.app.router.routes = [route for route in original_routes if route not in protected_routes]
        for route in protected_routes:
            endpoint = getattr(route, "endpoint", None)
            if endpoint is None:
                continue
            self.app.add_api_route(
                str(getattr(route, "path", "")),
                endpoint,
                methods=sorted(getattr(route, "methods", None) or {"GET"}),
                dependencies=dependencies,
                include_in_schema=False,
                name=getattr(route, "name", None),
            )

    def _install_openapi_schema_patch(self) -> None:
        if bool(getattr(self.app, "_safrs_openapi_patch_installed", False)):
            return

        original_openapi = self.app.openapi

        def patched_openapi() -> Dict[str, Any]:
            schema = original_openapi()
            components = schema.setdefault("components", {})
            if not isinstance(components, dict):
                return schema
            schemas = components.setdefault("schemas", {})
            if not isinstance(schemas, dict):
                return schema

            missing_models: List[Type[BaseModel]] = []
            for model in self._openapi_payload_models:
                model_name = str(getattr(model, "__name__", ""))
                if not model_name:
                    continue
                if model_name in schemas:
                    continue
                missing_models.append(model)

            if not missing_models:
                return schema

            try:
                _, json_schema = models_json_schema(
                    [(model, "validation") for model in missing_models],
                    ref_template="#/components/schemas/{model}",
                )
            except Exception as exc:
                safrs.log.debug("Failed to generate payload component schemas (%s)", type(exc).__name__)
                return schema

            definitions = json_schema.get("$defs", {})
            if not isinstance(definitions, dict):
                return schema

            for name, definition in definitions.items():
                if name in schemas:
                    continue
                if isinstance(definition, dict):
                    schemas[name] = definition

            self.app.openapi_schema = schema
            return schema

        cast(Any, self.app).openapi = patched_openapi
        setattr(self.app, "_safrs_openapi_patch_installed", True)

    @staticmethod
    def _with_slash_parity(path: str) -> List[str]:
        if path.endswith("/"):
            path = path.rstrip("/")
        return [path, path + "/"]

    def _normalize_dependencies(self, dependencies: Optional[List[Any]]) -> List[DependsParam]:
        if not dependencies:
            return []
        normalized: List[DependsParam] = []
        for dependency in dependencies:
            if isinstance(dependency, DependsParam):
                normalized.append(dependency)
                continue
            if callable(dependency):
                normalized.append(FastAPIDepends(dependency))
                continue
            raise TypeError("dependencies items must be callables or fastapi.Depends(...) instances")
        return normalized

    @staticmethod
    def _dependency_key(dependency: DependsParam) -> Tuple[Any, Tuple[str, ...], Any]:
        return (
            getattr(dependency, "dependency", None),
            tuple(getattr(dependency, "scopes", None) or ()),
            getattr(dependency, "use_cache", True),
        )

    def _authorize_operation(
        self, Model: Type[Any], action: str, request: Optional[Request] = None
    ) -> None:
        """Evaluate only policies explicitly registered for this operation."""
        context = current_authorization.get()
        dependencies = self._operation_dependencies.get(Model, self._default_operation_dependencies).get(action, [])
        if context is not None and action != "read":
            context.checked_resources.clear()
        if not dependencies:
            return
        if context is None:
            if request is None:
                raise RuntimeError("Authorization requires an active request")
            context = AuthorizationContext(request, self.app, self._authorization_limiter)
            async def check_direct() -> None:
                async with context.stack:
                    await context.check(dependencies)
            context.run(check_direct)
            return
        key = (Model, action)
        if key not in context.checked_operations:
            context.run(context.check, dependencies)
            context.checked_operations.add(key)

    def _authorize_instance_response(self, Model: Type[Any], obj_or_id: Any, request: Request) -> None:
        self._authorize_operation(Model, "read", request)
        obj = obj_or_id if hasattr(obj_or_id, "jsonapi_id") else Model.get_instance(obj_or_id)
        require_current_instance(
            obj,
            "read",
            response_check=str(request.method).upper() not in {"GET", "HEAD"},
        )
        context = current_authorization.get()
        key = (Model, id(obj))
        if context is not None and key in context.checked_resources:
            return
        callbacks = self._response_authorizers.get(Model, self._default_response_authorizers)
        if callbacks:
            callback_context = context or AuthorizationContext(request, self.app, self._authorization_limiter)
            for callback in callbacks:
                callback_context.authorize_response(callback, Model, obj)
        if context is not None:
            context.checked_resources.add(key)

    def _authorize_collection_before_metadata(
        self, Model: Type[Any], resources: Any, request: Request
    ) -> Any:
        """Apply object/response policies before exposing totals or ordering."""
        resources = apply_authorization_scope(
            Model, resources, fields=current_query_fields(Model)
        )
        callbacks = self._response_authorizers.get(Model, self._default_response_authorizers)
        if not callbacks and not model_has_resource_authorization(Model):
            return resources
        items = materialize_for_authorization(resources)
        for item in items:
            self._authorize_loaded_target(Model, item, request, "read")
        return items

    def _authorize_relationship_response(
        self, Model: Type[Any], object_id: Any, rel_name: str, request: Request
    ) -> None:
        self._authorize_operation(Model, "read", request)
        rel = self._resolve_relationship_properties(Model)[rel_name]
        self._authorize_operation(rel.mapper.class_, "read", request)

    def _authorize_context_resource(self, Model: Type[Any], obj: Any, action: str) -> None:
        context = current_authorization.get()
        if context is None:
            return
        if action == "read":
            self._authorize_instance_response(Model, obj, context.request)
        elif action == "cascade_delete":
            self._authorize_operation(Model, "delete")
        else:
            # Linking and unlinking require target update permission; row-level
            # decisions remain in _s_check_instance_access(action).
            self._authorize_operation(Model, "update")

    async def _authorization_context_dependency(self, request: Request):
        context = AuthorizationContext(request, self.app, self._authorization_limiter)
        token = current_authorization.set(context)
        jsonapi_token = set_jsonapi_context(self._build_jsonapi_context(request))
        try:
            # This dependency exits before the UOW dependency commits. A policy
            # generator that rejects during teardown still rolls back the write.
            async with context.stack:
                yield
        finally:
            reset_jsonapi_context(jsonapi_token)
            current_authorization.reset(token)

    def _build_jsonapi_context(self, request: Request) -> JsonApiContext:
        return JsonApiContext(
            query_params=request.query_params,
            prefix=self.prefix,
            resource_authorizer=self._authorize_context_resource,
            operation_authorizer=self._authorize_operation,
        )

    def _jsonapi_context_dependency(self, request: Request):
        context = self._build_jsonapi_context(request)
        token = set_jsonapi_context(context)
        try:
            yield
        finally:
            reset_jsonapi_context(token)

    def _cleanup_session(self) -> None:
        if not self.cleanup_session:
            return
        session = get_db().session
        info = getattr(session, "info", None)
        if isinstance(info, dict) and bool(info.get("_safrs_skip_cleanup", False)):
            return
        remove = getattr(session, "remove", None)
        if callable(remove):
            remove()
            return
        close = getattr(session, "close", None)
        if callable(close):
            close()

    @staticmethod
    def _rollback_session_quietly() -> None:
        try:
            get_db().session.rollback()
        except Exception as exc:
            safrs.log.debug("Session rollback failed (%s)", type(exc).__name__)

    @staticmethod
    def _uow_session_state() -> Dict[str, Any]:
        session = get_db().session
        info = getattr(session, "info", None)
        if isinstance(info, dict):
            return info
        state = cast(Optional[Dict[str, Any]], getattr(session, "_safrs_uow_state", None))
        if state is None:
            state = {}
            setattr(session, "_safrs_uow_state", state)
        return state

    def _reset_uow_state(self) -> None:
        state = self._uow_session_state()
        state["_safrs_uow_active"] = True
        state["_safrs_writes_seen"] = False
        state["_safrs_auto_commit_enabled"] = True

    def _note_write(self, Model: Type[Any]) -> None:
        tx.note_write(Model)

    def _safrs_uow_dependency(self, request: Request):
        # The ASGI middleware supplies this binding for real requests.  Keep a
        # nested token here as well so direct dependency use (tests and custom
        # integrations) has the same adapter-local database contract.
        db_token = set_db(self.db)
        self._reset_uow_state()
        try:
            yield
        except Exception:
            self._rollback_session_quietly()
            raise
        else:
            try:
                request_method = str(getattr(request, "method", "")).upper()
                if request_method in WRITE_HTTP_METHODS and tx.should_autocommit():
                    get_db().session.commit()
                else:
                    self._rollback_session_quietly()
            except Exception:
                self._rollback_session_quietly()
                raise
        finally:
            self._uow_session_state()["_safrs_uow_active"] = False
            try:
                self._cleanup_session()
            finally:
                reset_db(db_token)

    @staticmethod
    def _is_class_level_rpc_method(Model: Type[Any], method_name: str, api_method: Any) -> bool:
        raw_method = inspect.getattr_static(Model, method_name, None)
        if isinstance(raw_method, (classmethod, staticmethod)):
            return True
        return getattr(api_method, "__self__", None) is Model

    def _discover_rpc_methods(self, Model: Type[Any]) -> List[Tuple[str, bool, List[str]]]:
        rpc_methods: List[Tuple[str, bool, List[str]]] = []
        seen: Set[str] = set()
        try:
            discovered = Model._s_get_jsonapi_rpc_methods()
            for api_method in discovered:
                method_name = api_method.__name__
                if method_name in seen:
                    continue
                seen.add(method_name)
                class_level = self._is_class_level_rpc_method(Model, method_name, api_method)
                http_methods = [str(method).upper() for method in get_http_methods(api_method)]
                rpc_methods.append((method_name, class_level, http_methods))
            return rpc_methods
        except Exception as exc:
            safrs.log.debug("RPC method discovery fallback for %s (%s)", Model, type(exc).__name__)

        for klass in Model.__mro__:
            if klass is object:
                continue
            for method_name, raw_method in klass.__dict__.items():
                func = raw_method.__func__ if isinstance(raw_method, (classmethod, staticmethod)) else raw_method
                if method_name in seen or not callable(func):
                    continue
                if get_doc(func) is None:
                    continue
                seen.add(method_name)
                class_level = isinstance(raw_method, (classmethod, staticmethod))
                http_methods = [str(method).upper() for method in get_http_methods(func)]
                rpc_methods.append((method_name, class_level, http_methods))
        return rpc_methods

    def _add_route_with_slash_parity(
        self,
        router: APIRouter,
        path: str,
        endpoint: Any,
        methods: List[str],
        summary: str,
        dependencies: List[DependsParam],
        operation_id: str,
        status_code: Optional[int] = None,
        response_model: Optional[Type[Any]] = None,
        responses: Optional[Dict[Union[int, str], Dict[str, Any]]] = None,
        openapi_extra: Optional[Dict[str, Any]] = None,
        include_in_schema: bool = True,
    ) -> None:
        for method in methods:
            method_name = str(method).upper()
            method_operation_id = f"{operation_id}_{method_name.lower()}"
            for idx, variant in enumerate(self._with_slash_parity(path)):
                if idx == 0:
                    full_path = f"{self.prefix}{variant}" if self.prefix else variant
                    safrs.log.info(
                        "Exposing %s on %s, operation_id: %s",
                        method_name,
                        full_path,
                        method_operation_id,
                    )
                router.add_api_route(
                    variant,
                    endpoint,
                    methods=[method_name],
                    response_class=JSONAPIResponse,
                    summary=summary,
                    dependencies=dependencies,
                    operation_id=method_operation_id if idx == 0 else None,
                    include_in_schema=(idx == 0 and include_in_schema),
                    status_code=status_code,
                    response_model=response_model,
                    responses=responses,
                    openapi_extra=openapi_extra,
                )

    def _register_base_routes(
        self,
        router: APIRouter,
        Model: Type[Any],
        tag: str,
        collection_path: str,
        instance_path: str,
        route_dependencies: List[DependsParam],
    ) -> None:
        error_responses = self._jsonapi_error_responses()
        collection_response_model = self.schemas.document_collection(Model)
        instance_response_model = self.schemas.document_single(Model)
        post_status_codes = [200, 202] if Model._s_upsert and Model.allow_client_generated_ids else [202]
        collection_post_responses = self._merge_response_docs(
            error_responses,
            self._jsonapi_status_responses(post_status_codes),
        )
        instance_patch_responses = self._merge_response_docs(
            error_responses,
            self._jsonapi_status_responses([202, 204]),
        )
        instance_delete_responses = self._merge_response_docs(
            error_responses,
            self._jsonapi_status_responses([200, 202, 204]),
        )
        collection_query_openapi = self._openapi_query_parameters(
            self._jsonapi_query_parameters(
                Model,
                include_include=True,
                include_fields=True,
                include_pagination=True,
                include_sort=True,
                include_filter=True,
            )
        )
        instance_query_openapi = self._openapi_query_parameters(
            self._jsonapi_query_parameters(
                Model,
                include_include=True,
                include_fields=True,
            )
        )
        allowed_methods = self._model_http_methods(Model)
        if "GET" in allowed_methods:
            self._add_route_with_slash_parity(
                router,
                collection_path,
                self._get_collection(Model),
                ["GET"],
                f"List {tag}",
                route_dependencies,
                f"get_{tag}_collection",
                response_model=collection_response_model,
                responses=error_responses,
                openapi_extra=collection_query_openapi,
            )
        if "POST" in allowed_methods:
            create_body_openapi = self._openapi_request_body(
                self.schemas.document_create(Model),
                example=create_document_example(Model),
            )
            self._add_route_with_slash_parity(
                router,
                collection_path,
                self._post_collection(Model),
                ["POST"],
                f"Create {tag}",
                route_dependencies,
                f"post_{tag}_collection",
                status_code=201,
                response_model=instance_response_model,
                responses=collection_post_responses,
                openapi_extra=self._merge_openapi_extra(
                    instance_query_openapi,
                    create_body_openapi,
                ),
            )
        if "GET" in allowed_methods:
            self._add_route_with_slash_parity(
                router,
                instance_path,
                self._get_instance(Model),
                ["GET"],
                f"Get {tag} by id",
                route_dependencies,
                f"get_{tag}_instance",
                response_model=instance_response_model,
                responses=error_responses,
                openapi_extra=instance_query_openapi,
            )
        if "PATCH" in allowed_methods:
            patch_body_openapi = self._openapi_request_body(
                self.schemas.document_patch(Model),
                example=patch_document_example(Model),
            )
            self._add_route_with_slash_parity(
                router,
                instance_path,
                self._patch_instance(Model),
                ["PATCH"],
                f"Update {tag}",
                route_dependencies,
                f"patch_{tag}_instance",
                response_model=instance_response_model,
                responses=instance_patch_responses,
                openapi_extra=self._merge_openapi_extra(
                    instance_query_openapi,
                    patch_body_openapi,
                ),
            )
        if "DELETE" in allowed_methods:
            self._add_route_with_slash_parity(
                router,
                instance_path,
                self._delete_instance(Model),
                ["DELETE"],
                f"Delete {tag}",
                route_dependencies,
                f"delete_{tag}_instance",
                status_code=204,
                responses=instance_delete_responses,
            )

    def _register_rpc_routes(
        self,
        router: APIRouter,
        Model: Type[Any],
        tag: str,
        collection_path: str,
        instance_path: str,
        rpc_methods: List[Tuple[str, bool, List[str]]],
        route_dependencies: List[DependsParam],
    ) -> None:
        error_responses = self._jsonapi_error_responses()
        # Register class-level RPC before instance routes so /collection/method
        # doesn't get swallowed by /collection/{object_id}.
        for method_name, class_level, http_methods in rpc_methods:
            if not class_level:
                continue
            for http_method in http_methods:
                rpc_params, rpc_body = self._rpc_doc_spec(Model, method_name, http_method=http_method)
                rpc_openapi = self._merge_openapi_extra(
                    self._openapi_query_parameters(rpc_params) if rpc_params else None,
                    rpc_body,
                )
                self._add_route_with_slash_parity(
                    router,
                    f"{collection_path}/{method_name}",
                    self._rpc_handler(Model, method_name, class_level=True, http_method=str(http_method).upper()),
                    [str(http_method).upper()],
                    f"RPC {tag}.{method_name}",
                    route_dependencies,
                    f"class_{tag}_{method_name}_rpc",
                    responses=error_responses,
                    openapi_extra=rpc_openapi,
                )

        for method_name, class_level, http_methods in rpc_methods:
            if class_level:
                continue
            for http_method in http_methods:
                rpc_params, rpc_body = self._rpc_doc_spec(Model, method_name, http_method=http_method)
                rpc_openapi = self._merge_openapi_extra(
                    self._openapi_query_parameters(rpc_params) if rpc_params else None,
                    rpc_body,
                )
                self._add_route_with_slash_parity(
                    router,
                    f"{instance_path}/{method_name}",
                    self._rpc_handler(Model, method_name, class_level=False, http_method=str(http_method).upper()),
                    [str(http_method).upper()],
                    f"RPC {tag}.{method_name}",
                    route_dependencies,
                    f"instance_{tag}_{method_name}_rpc",
                    responses=error_responses,
                    openapi_extra=rpc_openapi,
                )

    def _register_relationship_routes(
        self,
        router: APIRouter,
        Model: Type[Any],
        tag: str,
        instance_path: str,
        route_dependencies: List[DependsParam],
    ) -> None:
        error_responses = self._jsonapi_error_responses()
        relationships = self._resolve_relationship_properties(Model)
        for rel_name, rel in relationships.items():
            rel_path = f"{instance_path}/{rel_name}"
            rel_item_path = f"{rel_path}/{{target_id}}"
            target_model = rel.mapper.class_
            if not hasattr(target_model, "_s_type"):
                continue
            is_many = self._is_to_many_relationship(rel)
            rel_methods = self._relationship_methods(Model, rel)

            # Relationship fetch returns full resource objects, not linkage.
            rel_get_model = (
                self.schemas.document_collection(target_model)
                if is_many
                else self.schemas.document_single(target_model)
            )

            # Relationship mutation payloads use JSON:API linkage documents.
            rel_doc_model = (
                self.schemas.relationship_document_to_many(target_model)
                if is_many
                else self.schemas.relationship_document_to_one(target_model)
            )
            rel_item_model = self.schemas.document_single(target_model)
            rel_example = (
                relationship_to_many_example(target_model)
                if is_many
                else relationship_to_one_example(target_model)
            )
            rel_openapi = self._openapi_request_body(rel_doc_model, example=rel_example)
            rel_get_openapi = self._openapi_query_parameters(
                self._jsonapi_query_parameters(
                    target_model,
                    include_include=True,
                    include_fields=True,
                    include_pagination=is_many,
                    include_sort=is_many,
                    include_filter=is_many,
                )
            )
            rel_item_get_openapi = self._openapi_query_parameters(
                self._jsonapi_query_parameters(
                    target_model,
                    include_include=True,
                    include_fields=True,
                )
            )
            rel_patch_responses = self._merge_response_docs(
                error_responses,
                self._jsonapi_status_responses([204]),
            )
            rel_post_responses = self._merge_response_docs(
                error_responses,
                self._jsonapi_status_responses([202, 204] if is_many else [202]),
            )
            rel_delete_responses = self._merge_response_docs(
                error_responses,
                self._jsonapi_status_responses([200, 202, 204]),
            )

            route_specs: List[
                Tuple[
                    str,
                    Any,
                    List[str],
                    str,
                    str,
                    Optional[int],
                    Optional[Type[Any]],
                    Optional[Dict[str, Any]],
                    Optional[Dict[Union[int, str], Dict[str, Any]]],
                    bool,
                ]
            ] = []
            if "GET" in rel_methods:
                route_specs.append(
                    (
                        rel_path,
                        self._get_relationship(Model, rel_name),
                        ["GET"],
                        f"Get relationship {tag}.{rel_name}",
                        f"get_{tag}_{rel_name}_relationship",
                        200,
                        rel_get_model,
                        rel_get_openapi,
                        error_responses,
                        True,
                    )
                )
                if self.relationship_item_mode != RelationshipItemMode.DISABLED:
                    route_specs.append(
                        (
                            rel_item_path,
                            self._get_relationship_item(Model, rel_name),
                            ["GET"],
                            f"Get relationship item {tag}.{rel_name}",
                            f"get_{tag}_{rel_name}_relationship_item",
                            200,
                            rel_item_model,
                            rel_item_get_openapi,
                            error_responses,
                            self.relationship_item_mode == RelationshipItemMode.ENABLED,
                        )
                    )
            if "PATCH" in rel_methods:
                route_specs.append(
                    (
                        rel_path,
                        self._patch_relationship(Model, rel_name),
                        ["PATCH"],
                        f"Patch relationship {tag}.{rel_name}",
                        f"patch_{tag}_{rel_name}_relationship",
                        None,
                        None,
                        rel_openapi,
                        rel_patch_responses,
                        True,
                    )
                )
            if "POST" in rel_methods:
                route_specs.append(
                    (
                        rel_path,
                        self._post_relationship(Model, rel_name),
                        ["POST"],
                        f"Post relationship {tag}.{rel_name}",
                        f"post_{tag}_{rel_name}_relationship",
                        None,
                        None,
                        rel_openapi,
                        rel_post_responses,
                        True,
                    )
                )
            if "DELETE" in rel_methods:
                route_specs.append(
                    (
                        rel_path,
                        self._delete_relationship(Model, rel_name),
                        ["DELETE"],
                        f"Delete relationship {tag}.{rel_name}",
                        f"delete_{tag}_{rel_name}_relationship",
                        204,
                        None,
                        rel_openapi,
                        rel_delete_responses,
                        True,
                    )
                )
            for (
                path,
                endpoint,
                methods,
                summary,
                operation_id,
                status_code,
                response_model,
                openapi_extra,
                response_docs,
                include_in_schema,
            ) in route_specs:
                self._add_route_with_slash_parity(
                    router,
                    path,
                    endpoint,
                    methods,
                    summary,
                    route_dependencies,
                    operation_id,
                    status_code=status_code,
                    response_model=response_model,
                    responses=response_docs,
                    openapi_extra=openapi_extra,
                    include_in_schema=include_in_schema,
                )

    @staticmethod
    def _schema_ref(model: Type[Any]) -> Dict[str, str]:
        return {"$ref": f"#/components/schemas/{model.__name__}"}

    @staticmethod
    def _openapi_query_parameters(parameters: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {"parameters": parameters}

    @staticmethod
    def _merge_response_docs(
        *response_maps: Optional[Dict[Union[int, str], Dict[str, Any]]]
    ) -> Optional[Dict[Union[int, str], Dict[str, Any]]]:
        merged: Dict[Union[int, str], Dict[str, Any]] = {}
        for response_map in response_maps:
            if not response_map:
                continue
            for status_code, response_spec in response_map.items():
                existing = merged.get(status_code)
                if existing is None:
                    merged[status_code] = dict(response_spec)
                    continue
                combined = dict(existing)
                combined.update(response_spec)
                existing_content = existing.get("content")
                new_content = response_spec.get("content")
                if isinstance(existing_content, dict) and isinstance(new_content, dict):
                    merged_content = dict(existing_content)
                    merged_content.update(new_content)
                    combined["content"] = merged_content
                merged[status_code] = combined
        return merged or None

    @staticmethod
    def _merge_openapi_extra(*extras: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        merged: Dict[str, Any] = {}
        seen_parameters: Set[Tuple[str, str]] = set()
        merged_parameters: List[Dict[str, Any]] = []
        for extra in extras:
            if not extra:
                continue
            for key, value in extra.items():
                if key == "parameters" and isinstance(value, list):
                    for parameter in value:
                        param_name = str(parameter.get("name", ""))
                        param_in = str(parameter.get("in", ""))
                        param_key = (param_in, param_name)
                        if param_key in seen_parameters:
                            continue
                        seen_parameters.add(param_key)
                        merged_parameters.append(parameter)
                    continue
                merged[key] = value
        if merged_parameters:
            merged["parameters"] = merged_parameters
        return merged or None

    @staticmethod
    def _query_parameter(
        name: str,
        schema_type: str = "string",
        description: str = "",
    ) -> Dict[str, Any]:
        return {
            "name": name,
            "in": "query",
            "required": False,
            "schema": {"type": schema_type},
            "description": description,
        }

    def _model_filter_query_parameters(self, Model: Type[Any]) -> List[Dict[str, Any]]:
        params: List[Dict[str, Any]] = [
            self._query_parameter("filter", description=f"{Model._s_type} filter expression"),
        ]
        attrs = set(getattr(Model, "_s_jsonapi_attrs", {}).keys())
        attrs.add("id")
        for attr_name in sorted(attrs):
            params.append(
                self._query_parameter(
                    f"filter[{attr_name}]",
                    description=f"Filter {Model._s_type} by '{attr_name}'",
                )
            )
        return params

    def _jsonapi_query_parameters(
        self,
        Model: Type[Any],
        *,
        include_include: bool = False,
        include_fields: bool = False,
        include_pagination: bool = False,
        include_sort: bool = False,
        include_filter: bool = False,
    ) -> List[Dict[str, Any]]:
        params: List[Dict[str, Any]] = []
        if include_include:
            class_name = str(getattr(Model, "_s_class_name", getattr(Model, "__name__", "Resource")))
            include_examples = ",".join(sorted(str(name) for name in self._resolve_relationship_properties(Model).keys()))
            include_description = f"{class_name} relationships to include (csv)"
            if include_examples:
                include_description = f"{class_name} relationships to include (csv, ex.: {include_examples})"
            params.append(
                self._query_parameter(
                    "include",
                    description=include_description,
                )
            )
        if include_fields:
            params.append(
                self._query_parameter(
                    f"fields[{Model._s_type}]",
                    description=f"Comma-separated fields for {Model._s_type}",
                )
            )
        if include_pagination:
            params.append(self._query_parameter("page[offset]", "integer", "Pagination offset"))
            params.append(self._query_parameter("page[limit]", "integer", "Pagination limit"))
            params.append(self._query_parameter("page[number]", "integer", "Pagination page number"))
            params.append(self._query_parameter("page[size]", "integer", "Pagination page size"))
        if include_sort:
            params.append(self._query_parameter("sort", description="Sort field (prefix with '-' for descending)"))
        if include_filter:
            params.extend(self._model_filter_query_parameters(Model))
        return params

    @staticmethod
    def _model_http_methods(Model: Type[Any]) -> Set[str]:
        raw_methods = getattr(Model, "http_methods", None)
        if raw_methods is None:
            return set(DEFAULT_HTTP_METHODS)
        candidates: Iterable[Any]
        if isinstance(raw_methods, str):
            candidates = [part for part in re.split(r"[\s,]+", raw_methods) if part]
        elif isinstance(raw_methods, (set, list, tuple, frozenset)):
            candidates = cast(Iterable[Any], raw_methods)
        else:
            try:
                candidates = list(cast(Iterable[Any], raw_methods))
            except TypeError:
                candidates = [raw_methods]

        normalized: Set[str] = set()
        for method in candidates:
            method_name = str(method).upper()
            if method_name in DEFAULT_HTTP_METHODS:
                normalized.add(method_name)
        return normalized

    @staticmethod
    def _rpc_annotation_schema(annotation: Any, default: Any = inspect._empty) -> Dict[str, Any]:
        target = annotation
        origin = get_origin(target)
        if origin is Union:
            non_none = [arg for arg in get_args(target) if arg is not type(None)]
            if len(non_none) == 1:
                target = non_none[0]
                origin = get_origin(target)
        if default is not inspect._empty and default is not None:
            return schema_for_example_value(default)
        if target in (int,):
            return {"type": "integer"}
        if target in (float,):
            return {"type": "number"}
        if target in (bool,):
            return {"type": "boolean"}
        if target in (dict,) or origin is dict:
            return {"type": "object", "additionalProperties": True}
        if target in (list, tuple, set) or origin in (list, tuple, set):
            return {"type": "array", "items": {}}
        if target is dt.date:
            return {"type": "string", "format": "date"}
        if target is dt.datetime:
            return {"type": "string", "format": "date-time"}
        if target is dt.time:
            return {"type": "string"}
        return {"type": "string"}

    @staticmethod
    def _rpc_signature_fields(method: Any) -> Tuple[Dict[str, Dict[str, Any]], List[str], List[Dict[str, Any]]]:
        fields: Dict[str, Dict[str, Any]] = {}
        required: List[str] = []
        parameters: List[Dict[str, Any]] = []
        for param in inspect.signature(method).parameters.values():
            if param.name in {"self", "cls"}:
                continue
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue
            schema = SafrsFastAPI._rpc_annotation_schema(param.annotation, param.default)
            if param.default is not inspect._empty:
                schema["default"] = jsonable_encoder(param.default)
            else:
                required.append(param.name)
            fields[param.name] = schema
            parameters.append(
                {
                    "name": param.name,
                    "in": "query",
                    "required": param.default is inspect._empty,
                    "schema": schema,
                    "description": "",
                }
            )
        return fields, required, parameters

    @staticmethod
    def _rpc_parameter_spec(parameter: Dict[str, Any]) -> Dict[str, Any]:
        schema_type = str(parameter.get("type", "string"))
        schema: Dict[str, Any] = {"type": schema_type}
        for key in ("format", "default", "enum", "minimum", "maximum"):
            if key in parameter:
                schema[key] = parameter[key]
        return {
            "name": str(parameter.get("name", "")),
            "in": str(parameter.get("in", "query")),
            "required": bool(parameter.get("required", False)),
            "schema": schema,
            "description": str(parameter.get("description", "")),
        }

    def _rpc_doc_spec(
        self,
        Model: Type[Any],
        method_name: str,
        *,
        http_method: str,
    ) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        method = resolve_rpc_method(Model, method_name)
        rest_doc = cast(Optional[Dict[str, Any]], get_doc(method)) or {}
        documented_parameters = rest_doc.get("parameters", [])
        signature_fields, signature_required, signature_parameters = self._rpc_signature_fields(method)

        parameters: List[Dict[str, Any]] = []
        if isinstance(documented_parameters, list) and documented_parameters:
            parameters.extend(self._rpc_parameter_spec(parameter) for parameter in documented_parameters)
        if rest_doc.get(PAGEABLE):
            parameters.append(self._query_parameter("page[offset]", "integer", "Pagination offset"))
            parameters.append(self._query_parameter("page[limit]", "integer", "Pagination limit"))
        if rest_doc.get(FILTERABLE):
            parameters.extend(self._model_filter_query_parameters(Model))

        if str(http_method).upper() == "GET":
            if not parameters:
                parameters = signature_parameters
            return parameters, None

        documented_args = rest_doc.get("args", {})
        required_fields: List[str] = []
        if isinstance(documented_args, dict) and documented_args:
            fields = {
                str(arg_name): schema_for_example_value(arg_value)
                for arg_name, arg_value in documented_args.items()
            }
        else:
            fields = signature_fields
            required_fields = signature_required

        valid_jsonapi = bool(getattr(method, "valid_jsonapi", True))
        if valid_jsonapi:
            meta_schema = jsonapi_rpc_meta_schema(
                {
                    str(arg_name): field.get("example", "")
                    for arg_name, field in fields.items()
                }
            )
            for arg_name, field_schema in fields.items():
                args_properties = cast(Dict[str, Any], meta_schema["properties"]["args"].setdefault("properties", {}))
                args_properties[arg_name] = field_schema
            if required_fields:
                meta_schema["properties"]["args"]["required"] = required_fields
            request_schema = {
                "type": "object",
                "required": ["meta"],
                "properties": {"meta": meta_schema},
                "additionalProperties": False,
            }
            return parameters, {
                "requestBody": {
                    "required": True,
                    "content": {
                        JSONAPI_MEDIA_TYPE: {"schema": request_schema},
                    },
                }
            }

        request_schema = {
            "type": "object",
            "properties": fields,
            "additionalProperties": True,
        }
        if required_fields:
            request_schema["required"] = required_fields
        return parameters, {
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {"schema": request_schema},
                },
            }
        }

    @staticmethod
    def _model_tag_description(Model: Type[Any], tag: str) -> str:
        raw_doc = getattr(Model, "__doc__", None)
        if isinstance(raw_doc, str):
            model_doc = inspect.cleandoc(raw_doc).strip()
            if model_doc:
                return model_doc
        return f"{tag} operations"

    def _ensure_tag_metadata(self, Model: Type[Any], tag: str) -> None:
        description = self._model_tag_description(Model, tag)
        existing = list(getattr(self.app, "openapi_tags", None) or [])
        by_name: Dict[str, Dict[str, Any]] = {}
        ordered_names: List[str] = []
        for item in existing:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", ""))
            if not name:
                continue
            if name not in by_name:
                ordered_names.append(name)
                by_name[name] = dict(item)
        if tag in by_name:
            if not by_name[tag].get("description"):
                by_name[tag]["description"] = description
        else:
            ordered_names.append(tag)
            by_name[tag] = {"name": tag, "description": description}
        self.app.openapi_tags = [by_name[name] for name in ordered_names]

    def _openapi_request_body(
        self,
        payload_model: Type[Any],
        required: bool = True,
        example: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if isinstance(payload_model, type) and issubclass(payload_model, BaseModel):
            self._openapi_payload_models.add(payload_model)
        media_spec: Dict[str, Any] = {
            "schema": self._schema_ref(payload_model),
        }
        if self.include_examples_in_openapi and example is not None:
            media_spec["example"] = example
        return {
            "requestBody": {
                "required": required,
                "content": {
                    JSONAPI_MEDIA_TYPE: media_spec
                },
            }
        }

    @staticmethod
    def _jsonapi_status_responses(status_codes: Iterable[int]) -> Dict[Union[int, str], Dict[str, Any]]:
        responses: Dict[Union[int, str], Dict[str, Any]] = {}
        for status_code in status_codes:
            status_code_int = int(status_code)
            try:
                description = HTTPStatus(status_code_int).phrase
            except ValueError:
                description = "Response"
            if status_code_int == int(HTTPStatus.NO_CONTENT):
                responses[status_code_int] = {"description": description}
                continue
            responses[status_code_int] = {
                "description": description,
                "content": {
                    JSONAPI_MEDIA_TYPE: {
                        "schema": {"type": "object"},
                    }
                },
            }
        return responses

    def _jsonapi_error_responses(self) -> Dict[Union[int, str], Dict[str, Any]]:
        error_model = self.schemas.error_document()
        error_content = {
            JSONAPI_MEDIA_TYPE: {
                "schema": self._schema_ref(error_model),
            }
        }
        return {
            400: {"description": HTTPStatus.BAD_REQUEST.phrase, "model": error_model, "content": error_content},
            403: {"description": HTTPStatus.FORBIDDEN.phrase, "model": error_model, "content": error_content},
            404: {"description": HTTPStatus.NOT_FOUND.phrase, "model": error_model, "content": error_content},
            405: {"description": HTTPStatus.METHOD_NOT_ALLOWED.phrase, "model": error_model, "content": error_content},
            415: {"description": HTTPStatus.UNSUPPORTED_MEDIA_TYPE.phrase, "model": error_model, "content": error_content},
            409: {"description": HTTPStatus.CONFLICT.phrase, "model": error_model, "content": error_content},
            422: {"description": HTTPStatus.UNPROCESSABLE_ENTITY.phrase, "model": error_model, "content": error_content},
            500: {"description": HTTPStatus.INTERNAL_SERVER_ERROR.phrase, "model": error_model, "content": error_content},
        }

    def expose_object(
        self,
        Model: Type[Any],
        dependencies: Optional[List[Any]] = None,
        method_decorators: Optional[List[Any]] = None,
        *,
        read_dependencies: Optional[List[Any]] = None,
        create_dependencies: Optional[List[Any]] = None,
        update_dependencies: Optional[List[Any]] = None,
        delete_dependencies: Optional[List[Any]] = None,
        response_authorizer: Optional[Callable[[Type[Any], Any, Request], Any]] = None,
    ) -> None:
        """
        Register CRUD routes for a SAFRS model.
        """
        if not getattr(Model, "_s_expose", True):
            raise SystemValidationError(f"Refusing to expose {Model}: _s_expose is set to False")
        if getattr(Model, "decorators", None):
            raise NotImplementedError(
                "FastAPI does not support Model.decorators. "
                "Use dependencies=[Depends(...)] instead."
            )
        if method_decorators:
            raise NotImplementedError(
                "FastAPI adapter does not support Flask method_decorators; use dependencies=[...]"
            )

        model_dependencies = self._normalize_dependencies(dependencies)
        self._model_dependencies[Model] = model_dependencies
        self._models_by_resource_type[str(Model._s_type)] = Model
        self._operation_dependencies[Model] = {
            action: self._default_operation_dependencies[action] + self._normalize_dependencies(dependencies)
            for action, dependencies in {
                "read": read_dependencies, "create": create_dependencies,
                "update": update_dependencies, "delete": delete_dependencies,
            }.items()
        }
        self._response_authorizers[Model] = self._default_response_authorizers + (
            [response_authorizer] if response_authorizer else []
        )
        has_authorization_policy = bool(
            model_dependencies
            or any(self._operation_dependencies[Model].values())
            or self._response_authorizers[Model]
            or (
                self.authorization is not None
                and self.authorization.is_registered(Model)
            )
        )
        if (
            has_authorization_policy
            and not self._docs_protected
            and not self._public_docs_warning_emitted
        ):
            safrs.log.warning(
                "FastAPI documentation routes are public while SAFRS authorization policies are configured; "
                "set docs_dependencies=[Depends(...)] to protect /docs, /redoc, /openapi.json, and /swagger.json"
            )
            self._public_docs_warning_emitted = True
        route_dependencies = self.default_dependencies + model_dependencies
        tag = str(Model._s_collection_name)
        self._ensure_tag_metadata(Model, tag)

        router = APIRouter(prefix=self.prefix, tags=[tag])
        collection_path = "/" + str(Model._s_collection_name)
        instance_path = collection_path + "/{object_id}"
        rpc_methods = self._discover_rpc_methods(Model)

        self._register_rpc_routes(
            router,
            Model,
            tag,
            collection_path,
            instance_path,
            rpc_methods,
            route_dependencies,
        )
        self._register_base_routes(
            router,
            Model,
            tag,
            collection_path,
            instance_path,
            route_dependencies,
        )
        self._register_relationship_routes(router, Model, tag, instance_path, route_dependencies)

        self.app.include_router(router)

        # If /docs was opened before exposing models, FastAPI may have cached OpenAPI already.
        self.app.openapi_schema = None

    def _jsonapi_doc(
        self,
        data: Any = None,
        errors: Any = None,
        included: Any = None,
        meta: Any = None,
    ) -> Dict[str, Any]:
        doc: Dict[str, Any] = {"jsonapi": {"version": "1.0"}}
        if errors is not None:
            doc["errors"] = errors
        if data is not None:
            doc["data"] = data
        if included is not None:
            doc["included"] = included
        if meta is not None:
            doc["meta"] = meta
        return doc

    def _jsonapi_response(
        self,
        content: Dict[str, Any],
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
    ) -> JSONAPIResponse:
        return JSONAPIResponse(status_code=status_code, headers=headers, content=content)

    def _jsonapi_data_response(
        self,
        *,
        data: Any,
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
        links: Any = None,
        meta: Optional[Dict[str, Any]] = None,
        count: Any = None,
        request: Optional[Request] = None,
    ) -> JSONAPIResponse:
        token = None
        if maybe_jsonapi_context() is None:
            query_params = request.query_params if request is not None else {}
            token = set_jsonapi_context(JsonApiContext(query_params=query_params, prefix=self.prefix))
        try:
            if request is not None:
                for obj in data if isinstance(data, (list, tuple, set)) else [data]:
                    if shared_is_resource_instance(obj):
                        self._authorize_loaded_target(obj.__class__, obj, request, "read")
            primary_items = list(data) if isinstance(data, (list, tuple, set)) else [data]
            primary_by_model: Dict[Type[Any], List[Any]] = {}
            for obj in primary_items:
                if shared_is_resource_instance(obj):
                    primary_by_model.setdefault(obj.__class__, []).append(obj)
            for resource_model, instances in primary_by_model.items():
                prepare_current_readable_fields(resource_model, instances)
            payload = cast(
                Dict[str, Any],
                jsonapi_format_response(
                    data=data,
                    meta=meta or {},
                    links=links,
                    errors=None,
                    count=count,
                ),
            )
            return self._jsonapi_response(payload, status_code=status_code, headers=headers)
        finally:
            if token is not None:
                reset_jsonapi_context(token)

    def _instance_links(self, request: Request, Model: Type[Any], obj: Any) -> Dict[str, str]:
        self_url = self._resource_self_path(Model, obj)
        links = {"self": self_url}
        request_path = str(request.url.path).rstrip("/")
        if request_path and (request_path != self_url.rstrip("/") or bool(request.url.query)):
            query = str(request.url.query)
            related = str(request.url.path)
            if query:
                related = f"{related}?{query}"
            links["related"] = related
        return links

    def _jsonapi_error(self, status_code: int, title: str, detail: str) -> NoReturn:
        payload = self._jsonapi_doc(
            errors=[{"status": str(status_code), "title": title, "detail": detail}]
        )
        raise JSONAPIHTTPError(status_code, payload)

    def _handle_safrs_exception(self, exc: Exception) -> None:
        if isinstance(exc, JSONAPIHTTPError):
            raise exc
        if isinstance(exc, (StarletteHTTPException, RequestValidationError)):
            self._rollback_session_quietly()
            raise exc
        expected_validation_exception = _coerce_expected_validation_exception(
            exc,
            self.expected_validation_exceptions,
        )
        if expected_validation_exception is not None:
            self._rollback_session_quietly()
            self._jsonapi_error(
                HTTPStatus.BAD_REQUEST.value,
                "ValidationError",
                str(getattr(expected_validation_exception, "message", str(expected_validation_exception))),
            )
        if isinstance(exc, IntegrityError):
            log_integrity_error_details(exc)
            self._rollback_session_quietly()
            self._jsonapi_error(
                HTTPStatus.CONFLICT.value,
                HTTPStatus.CONFLICT.phrase,
                "Database constraint violation",
            )
        if isinstance(exc, (DataError, StatementError, OverflowError)):
            self._rollback_session_quietly()
            self._jsonapi_error(
                HTTPStatus.BAD_REQUEST.value,
                HTTPStatus.BAD_REQUEST.phrase,
                "Invalid attribute value",
            )
        if isinstance(exc, CircularDependencyError):
            self._rollback_session_quietly()
            self._jsonapi_error(
                HTTPStatus.CONFLICT.value,
                HTTPStatus.CONFLICT.phrase,
                "Relationship update creates a circular dependency",
            )
        if isinstance(exc, (FlushError, InvalidRequestError)):
            self._rollback_session_quietly()
            self._jsonapi_error(
                HTTPStatus.CONFLICT.value,
                HTTPStatus.CONFLICT.phrase,
                "Relationship update violates DB constraints",
            )
        if isinstance(exc, AssertionError) and "Dependency rule on column" in str(exc):
            self._rollback_session_quietly()
            self._jsonapi_error(
                HTTPStatus.CONFLICT.value,
                HTTPStatus.CONFLICT.phrase,
                "Relationship update violates DB constraints",
            )
        if isinstance(exc, (SystemValidationError, ValidationError, GenericError)):
            self._rollback_session_quietly()
            status = int(getattr(exc, "status_code", 400))
            msg = str(getattr(exc, "message", str(exc)))
            self._jsonapi_error(status, exc.__class__.__name__, msg)
        if isinstance(exc, JsonapiError):
            self._rollback_session_quietly()
            status = int(getattr(exc, "status_code", 400))
            msg = str(getattr(exc, "message", str(exc)))
            self._jsonapi_error(status, exc.__class__.__name__, msg)
        self._rollback_session_quietly()
        safrs.log.error("Unhandled SAFRS FastAPI error (%s)", type(exc).__name__)
        self._jsonapi_error(
            HTTPStatus.INTERNAL_SERVER_ERROR.value,
            HTTPStatus.INTERNAL_SERVER_ERROR.phrase,
            "Internal Server Error",
        )

    def _require_type(self, Model: Type[Any], payload: Dict[str, Any]) -> None:
        data = payload.get("data")
        if not isinstance(data, dict):
            self._jsonapi_error(400, "ValidationError", "Invalid JSON:API payload (missing data object)")
        data = cast(Dict[str, Any], data)
        typ = data.get("type")
        if typ != Model._s_type:
            self._jsonapi_error(400, "ValidationError", "Invalid type: expected " + str(Model._s_type))

    def _parse_sparse_fields(self, Model: Type[Any], request: Request) -> Optional[Set[str]]:
        fields_key = f"fields[{Model._s_type}]"
        fields_csv = request.query_params.get(fields_key)
        if not fields_csv:
            return None
        return {field.strip() for field in fields_csv.split(",") if field.strip()}

    def _parse_sparse_fields_map(self, request: Request) -> Dict[str, Set[str]]:
        result: Dict[str, Set[str]] = {}
        for key, value in request.query_params.items():
            if not key.startswith("fields[") or not key.endswith("]"):
                continue
            model_type = key[len("fields[") : -1]
            wanted = {field.strip() for field in value.split(",") if field.strip()}
            if wanted:
                result[model_type] = wanted
        return result

    def _resolve_relationships(self, Model: Type[Any]) -> Dict[str, Any]:
        return resolve_relationships(Model)

    @staticmethod
    def _relationship_property(rel: Any) -> Optional[Any]:
        return relationship_property(rel)

    @staticmethod
    def _is_to_many_relationship(rel: Any) -> bool:
        if hasattr(rel, "uselist"):
            return bool(getattr(rel, "uselist"))
        direction = getattr(rel, "direction", None)
        return direction in (ONETOMANY, MANYTOMANY)

    def _relationship_mutations_enabled(self, Model: Type[Any], rel: Any) -> bool:
        if bool(getattr(rel, "viewonly", False)):
            return False
        return "PATCH" in self._model_http_methods(Model)

    def _relationship_methods(self, Model: Type[Any], rel: Any) -> Set[str]:
        parent_methods = self._model_http_methods(Model)
        target_model = rel.mapper.class_
        target_methods = self._model_http_methods(target_model)
        methods: Set[str] = {"GET"} if "GET" in parent_methods and "GET" in target_methods else set()
        if not self._relationship_mutations_enabled(Model, rel):
            return methods
        if self._is_to_many_relationship(rel):
            candidate_methods = {"POST", "PATCH", "DELETE"}
        else:
            candidate_methods = {"PATCH", "DELETE"}
        methods.update(candidate_methods & target_methods)
        return methods

    def _resolve_relationship_properties(self, Model: Type[Any]) -> Dict[str, Any]:
        raw_rels = self._resolve_relationships(Model)
        mapper = getattr(Model, "__mapper__", None)
        mapper_rels: Dict[str, Any] = {}
        if mapper is not None:
            mapper_rels = {rel.key: rel for rel in mapper.relationships}

        resolved: Dict[str, Any] = {}
        for rel_name, rel in raw_rels.items():
            rel_prop = self._relationship_property(rel)
            if rel_prop is None:
                rel_prop = self._relationship_property(mapper_rels.get(rel_name))
            if rel_prop is not None and relationship_is_exposed(Model, rel_name, rel_prop):
                resolved[rel_name] = rel_prop
        return resolved

    @staticmethod
    def _parse_rpc_args(
        request: Request,
        payload: Optional[Dict[str, Any]],
        *,
        valid_jsonapi: bool = True,
    ) -> Dict[str, Any]:
        return shared_parse_rpc_args(
            http_method=str(request.method).upper(),
            valid_jsonapi=valid_jsonapi,
            query_items=request.query_params.multi_items(),
            payload=payload,
        )

    @staticmethod
    def _rpc_request_context(request: Request):
        from flask import Flask, current_app, has_app_context

        if has_app_context():
            flask_app = cast(Any, current_app)._get_current_object()
        else:
            flask_app = Flask("safrs-fastapi-rpc")
        try:
            from safrs.request import SAFRSRequest
            flask_app.request_class = SAFRSRequest
        except Exception as exc:
            safrs.log.debug("Unable to import SAFRSRequest for rpc context (%s)", type(exc).__name__)
        try:
            from safrs.json_encoder import SAFRSJSONEncoder
            cast(Any, flask_app).json_encoder = SAFRSJSONEncoder
        except Exception as exc:
            safrs.log.debug("Unable to import SAFRSJSONEncoder for rpc context (%s)", type(exc).__name__)
        query_items = [(str(key), str(value)) for key, value in request.query_params.multi_items()]
        return flask_app.test_request_context(path=request.url.path, query_string=query_items)

    def _encode_rpc_value(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, dict):
            if "type" in value and "id" in value:
                return value
            return {key: self._encode_rpc_value(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._encode_rpc_value(item) for item in value]
        if isinstance(value, type) and value.__name__ == "Included":
            return []
        if hasattr(value, "_s_type") and hasattr(value, "jsonapi_id"):
            return self._encode_resource(
                value.__class__,
                value,
                include_relationships=False,
                include_links=False,
            )
        return jsonable_encoder(value)

    def _normalize_rpc_result(
        self,
        Model: Type[Any],
        result: Any,
        *,
        valid_jsonapi: bool = True,
    ) -> Any:
        return shared_normalize_rpc_result(
            result,
            valid_jsonapi=valid_jsonapi,
            encode_value=self._encode_rpc_value,
            encode_resource=lambda value: self._encode_resource(
                value.__class__,
                value,
                include_relationships=False,
                include_links=False,
            ),
            jsonapi_doc=self._jsonapi_doc,
        )

    def _rpc_result_resources(self, result: Any) -> List[Tuple[Type[Any], Any]]:
        """Find resource representations in an RPC result before it is encoded."""
        payload = shared_unwrap_formatted_response(result)
        resources: List[Tuple[Type[Any], Any]] = []
        seen_containers: Set[int] = set()
        seen_resources: Set[Tuple[Type[Any], str]] = set()

        def append_resource(resource_model: Type[Any], resource_or_id: Any) -> None:
            resource_id = getattr(resource_or_id, "jsonapi_id", resource_or_id)
            key = (resource_model, str(resource_id))
            if key in seen_resources:
                return
            seen_resources.add(key)
            resources.append((resource_model, resource_or_id))

        def visit(value: Any) -> None:
            if shared_is_resource_instance(value):
                append_resource(value.__class__, value)
                return
            if isinstance(value, dict):
                container_id = id(value)
                if container_id in seen_containers:
                    return
                seen_containers.add(container_id)
                if "type" in value and "id" in value:
                    resource_type = str(value["type"])
                    resource_model = self._models_by_resource_type.get(resource_type)
                    if resource_model is None:
                        raise StarletteHTTPException(
                            status_code=HTTPStatus.FORBIDDEN.value,
                            detail=f"Cannot authorize RPC response resource type '{resource_type}'",
                        )
                    append_resource(resource_model, value["id"])
                for key, nested in value.items():
                    visit(nested)
                return
            if isinstance(value, (list, tuple, set)):
                container_id = id(value)
                if container_id in seen_containers:
                    return
                seen_containers.add(container_id)
                for nested in value:
                    visit(nested)

        visit(payload)
        return resources

    def _authorize_rpc_result(self, result: Any, request: Request) -> None:
        for resource_model, resource_or_id in self._rpc_result_resources(result):
            registered_model = self._models_by_resource_type.get(str(resource_model._s_type))
            if registered_model is not resource_model:
                raise StarletteHTTPException(
                    status_code=HTTPStatus.FORBIDDEN.value,
                    detail=f"Cannot authorize RPC response resource type '{resource_model._s_type}'",
                )
            resource = resource_or_id if shared_is_resource_instance(resource_or_id) else resource_model.get_instance(resource_or_id)
            self._authorize_loaded_target(resource_model, resource, request, "read")

    def _call_class_rpc(
        self,
        Model: Type[Any],
        method_name: str,
        request: Request,
        payload: Optional[Dict[str, Any]],
    ) -> JSONAPIResponse:
        method = getattr(Model, method_name)
        valid_jsonapi = bool(getattr(method, "valid_jsonapi", True))
        args = self._parse_rpc_args(request, payload, valid_jsonapi=valid_jsonapi)
        bound_args = shared_bind_rpc_kwargs(method, args)
        with self._rpc_request_context(request):
            result = method(**bound_args)
        self._authorize_rpc_result(result, request)
        return JSONAPIResponse(
            status_code=200,
            content=self._normalize_rpc_result(Model, result, valid_jsonapi=valid_jsonapi),
        )

    def _call_instance_rpc(
        self,
        Model: Type[Any],
        method_name: str,
        object_id: ObjectIdParam,
        request: Request,
        payload: Optional[Dict[str, Any]],
    ) -> JSONAPIResponse:
        instance = Model.get_instance(object_id)
        method = getattr(instance, method_name)
        valid_jsonapi = bool(getattr(method, "valid_jsonapi", True))
        args = self._parse_rpc_args(request, payload, valid_jsonapi=valid_jsonapi)
        bound_args = shared_bind_rpc_kwargs(method, args)
        with self._rpc_request_context(request):
            result = method(**bound_args)
        self._authorize_rpc_result(result, request)
        return JSONAPIResponse(
            status_code=200,
            content=self._normalize_rpc_result(Model, result, valid_jsonapi=valid_jsonapi),
        )

    def _dispatch_rpc_call(
        self,
        Model: Type[Any],
        method_name: str,
        request: Request,
        *,
        class_level: bool,
        payload: Optional[Dict[str, Any]] = None,
        object_id: Optional[ObjectIdParam] = None,
    ) -> JSONAPIResponse:
        try:
            if payload is not None:
                validate_json_payload(payload)
            reject_current_rpc(Model)
            self._authorize_operation(
                Model, "update" if str(request.method).upper() in WRITE_HTTP_METHODS else "read", request
            )
            if str(request.method).upper() in WRITE_HTTP_METHODS:
                self._note_write(Model)
            if class_level:
                return self._call_class_rpc(Model, method_name, request, payload)
            if object_id is None:
                raise RuntimeError("Missing object_id for instance RPC handler")
            return self._call_instance_rpc(Model, method_name, object_id, request, payload)
        except JSONAPIHTTPError:
            raise
        except Exception as exc:
            self._handle_safrs_exception(exc)
            raise AssertionError("unreachable")

    def _class_rpc_get_handler(self, Model: Type[Any], method_name: str) -> Callable[[Request], JSONAPIResponse]:
        def class_get_handler(request: Request) -> JSONAPIResponse:
            return self._dispatch_rpc_call(
                Model,
                method_name,
                request,
                class_level=True,
            )

        return class_get_handler

    def _class_rpc_body_handler(
        self,
        Model: Type[Any],
        method_name: str,
    ) -> Callable[[Request, Optional[Dict[str, Any]]], JSONAPIResponse]:
        def class_body_handler(
            request: Request,
            payload: Optional[Dict[str, Any]] = Body(default=None),
        ) -> JSONAPIResponse:
            return self._dispatch_rpc_call(
                Model,
                method_name,
                request,
                class_level=True,
                payload=payload,
            )

        return class_body_handler

    def _instance_rpc_get_handler(
        self,
        Model: Type[Any],
        method_name: str,
    ) -> Callable[[ObjectIdParam, Request], JSONAPIResponse]:
        def instance_get_handler(
            object_id: ObjectIdParam,
            request: Request,
        ) -> JSONAPIResponse:
            return self._dispatch_rpc_call(
                Model,
                method_name,
                request,
                class_level=False,
                object_id=object_id,
            )

        return instance_get_handler

    def _instance_rpc_body_handler(
        self,
        Model: Type[Any],
        method_name: str,
    ) -> Callable[[ObjectIdParam, Request, Optional[Dict[str, Any]]], JSONAPIResponse]:
        def instance_body_handler(
            object_id: ObjectIdParam,
            request: Request,
            payload: Optional[Dict[str, Any]] = Body(default=None),
        ) -> JSONAPIResponse:
            return self._dispatch_rpc_call(
                Model,
                method_name,
                request,
                class_level=False,
                payload=payload,
                object_id=object_id,
            )

        return instance_body_handler

    def _rpc_handler(self, Model: Type[Any], method_name: str, class_level: bool, http_method: str):
        request_method = str(http_method).upper()

        if class_level:
            if request_method == "GET":
                return self._class_rpc_get_handler(Model, method_name)
            return self._class_rpc_body_handler(Model, method_name)

        if request_method == "GET":
            return self._instance_rpc_get_handler(Model, method_name)

        return self._instance_rpc_body_handler(Model, method_name)

    def _parse_include_paths(self, Model: Type[Any], request: Request) -> List[List[str]]:
        include_csv = request.query_params.get("include")
        if not include_csv:
            return []

        include_values = [item.strip() for item in include_csv.split(",") if item.strip()]
        if not include_values:
            return []

        max_include_paths = int(getattr(safrs.SAFRS, "MAX_INCLUDE_PATHS", 0) or 0)
        if max_include_paths > 0 and len(include_values) > max_include_paths:
            self._jsonapi_error(400, "ValidationError", f"Too many include paths (maximum {max_include_paths})")
        max_include_depth = int(getattr(safrs.SAFRS, "MAX_INCLUDE_DEPTH", 0) or 0)

        root_rels = self._resolve_relationship_properties(Model)
        paths: List[List[str]] = []
        for inc in include_values:
            if inc == safrs.SAFRS.INCLUDE_ALL:
                paths.extend([[name] for name in root_rels.keys()])
                continue
            path = [part for part in inc.split(".") if part]
            if not path:
                continue
            if max_include_depth > 0 and len(path) > max_include_depth:
                self._jsonapi_error(
                    400,
                    "ValidationError",
                    f"Include path exceeds maximum depth {max_include_depth}",
                )
            current_model = Model
            for segment in path:
                rels = self._resolve_relationship_properties(current_model)
                if segment not in rels:
                    self._jsonapi_error(400, "ValidationError", f"Invalid relationship '{segment}' in include")
                current_model = rels[segment].mapper.class_
            paths.append(path)
        if max_include_paths > 0 and len(paths) > max_include_paths:
            self._jsonapi_error(400, "ValidationError", f"Too many include paths (maximum {max_include_paths})")
        return paths

    def _iter_related_items(self, rel_value: Any, *, limit: Optional[int] = None) -> List[Any]:
        if rel_value is None:
            return []
        if hasattr(rel_value, "all") and callable(rel_value.all):
            query = rel_value.limit(limit) if limit is not None and hasattr(rel_value, "limit") else rel_value
            return list(query.all())
        if isinstance(rel_value, (list, tuple, set)):
            items = list(rel_value)
            return items[:limit] if limit is not None else items
        return [rel_value]

    def _validate_collection_size(self, data: Any, label: str) -> None:
        if not isinstance(data, list):
            return
        max_items = int(getattr(safrs.SAFRS, "MAX_BULK_ITEMS", 0) or 0)
        if max_items > 0 and len(data) > max_items:
            self._jsonapi_error(400, "ValidationError", f"{label} exceeds maximum item count {max_items}")

    @staticmethod
    def _parse_sort_terms(raw_sort: Optional[str]) -> List[Tuple[str, bool]]:
        sort_csv = str(raw_sort or "").strip() or "id"
        terms: List[Tuple[str, bool]] = []
        for chunk in sort_csv.split(","):
            token = chunk.strip()
            if not token:
                continue
            reverse = token.startswith("-")
            attr_name = token[1:] if reverse else token
            if not attr_name:
                continue
            terms.append((attr_name, reverse))
        if not terms:
            terms.append(("id", False))
        max_sort_terms = int(get_config("MAX_SORT_TERMS") or 0)
        if max_sort_terms > 0 and len(terms) > max_sort_terms:
            raise ValidationError(f"Too many sort terms (maximum {max_sort_terms})")
        return terms

    @staticmethod
    def _resolve_sort_attr_name(Model: Type[Any], attr_name: str) -> Optional[str]:
        if attr_name == "id":
            if hasattr(Model, "id"):
                return "id"
            id_type = getattr(Model, "id_type", None)
            primary_keys = getattr(id_type, "primary_keys", []) if id_type is not None else []
            if primary_keys:
                return str(primary_keys[0])
            return None

        model_attrs = getattr(Model, "_s_jsonapi_attrs", {})
        if attr_name in model_attrs and get_filterable_attribute(Model, attr_name) is not None:
            if has_custom_instance_permission_check(Model):
                raise ValidationError(
                    f"Sorting by '{attr_name}' is not allowed with row-dependent field permissions"
                )
            return attr_name
        return None

    @staticmethod
    def _apply_sort_to_list(Model: Type[Any], items: List[Any], sort_terms: Sequence[Tuple[str, bool]]) -> List[Any]:
        sorted_items = list(items)
        # Python sort is stable; apply terms in reverse so the first term wins.
        for raw_attr, reverse in reversed(sort_terms):
            resolved_attr = SafrsFastAPI._resolve_sort_attr_name(Model, raw_attr)
            if not resolved_attr:
                continue
            try:
                candidate_items = sorted(
                    sorted_items,
                    key=lambda item: (getattr(item, resolved_attr, None) is None, getattr(item, resolved_attr, None)),
                    reverse=reverse,
                )
            except Exception as exc:
                safrs.log.debug("Unable to sort list by '%s' (%s)", resolved_attr, type(exc).__name__)
            else:
                sorted_items = candidate_items
        return sorted_items

    @staticmethod
    def _is_query_like(value: Any) -> bool:
        return hasattr(value, "all") and callable(value.all)

    def _coerce_items(self, value: Any) -> List[Any]:
        if value is None:
            return []
        if self._is_query_like(value):
            return list(value.all())
        if isinstance(value, (list, tuple, set)):
            return list(value)
        return [value]

    def _collection_path(self, Model: Type[Any]) -> str:
        collection_name = getattr(Model, "_s_collection_name", None) or getattr(Model, "_s_type", Model.__name__)
        collection = str(collection_name).strip("/")
        prefix = (self.prefix or "").strip("/")
        if prefix:
            return f"/{prefix}/{collection}/"
        return f"/{collection}/"

    def _resource_self_path(self, Model: Type[Any], obj: Any) -> str:
        encoded_id = quote(str(obj.jsonapi_id), safe="")
        return f"{self._collection_path(Model)}{encoded_id}/"

    def _relationship_self_path(self, Model: Type[Any], obj: Any, rel_name: str) -> str:
        encoded_id = quote(str(obj.jsonapi_id), safe="")
        return f"{self._collection_path(Model)}{encoded_id}/{rel_name}"

    @staticmethod
    def _build_query_string(params: List[Tuple[str, str]]) -> str:
        if not params:
            return ""
        encoded_parts = [f"{quote(str(key), safe='[]')}={quote(str(value), safe=',')}" for key, value in params]
        return "&".join(encoded_parts)

    def _pagination_args(self, request: Request) -> Tuple[int, int]:
        context = self._build_jsonapi_context(request)
        offset = self._parse_page_param(context.get_page_offset(), 0)
        default_limit = int(getattr(safrs.SAFRS, "DEFAULT_PAGE_LIMIT", 250))
        limit = self._parse_page_param(context.get_page_limit(), default_limit)

        max_page_limit = int(getattr(safrs.SAFRS, "MAX_PAGE_LIMIT", 0) or 0)
        if max_page_limit > 0:
            raw_limits: List[str] = []
            if request.query_params.get("page[limit]") is not None:
                raw_limits.append(str(request.query_params.get("page[limit]")))
            if request.query_params.get("page[number]") is not None and request.query_params.get("page[size]") is not None:
                raw_limits.append(str(request.query_params.get("page[size]")))
            for raw_limit in raw_limits:
                try:
                    if int(raw_limit) <= 0:
                        limit = max_page_limit
                        break
                except (TypeError, ValueError):
                    continue
            if limit <= 0:
                limit = max_page_limit
            elif limit > max_page_limit:
                limit = max_page_limit

        return offset, limit

    @staticmethod
    def _parse_page_param(raw_value: Any, default: int) -> int:
        """
        Backward-compatible pagination parser used by internal tests.
        """
        try:
            parsed = int(raw_value)
        except (TypeError, ValueError):
            return int(default)
        if parsed < 0:
            return 0
        return parsed

    def _page_link(self, request: Request, page_offset: int, limit: int, *, base_path: Optional[str] = None) -> str:
        params = [(str(key), str(value)) for key, value in request.query_params.multi_items() if key not in {"page[offset]", "page[limit]"}]
        params.append(("page[offset]", str(page_offset)))
        params.append(("page[limit]", str(limit)))
        query = self._build_query_string(params)
        path = str(base_path if base_path is not None else request.url.path)
        if not path.endswith("/"):
            path = path + "/"
        return f"{path}?{query}" if query else path

    def _pagination_links(
        self,
        request: Request,
        *,
        count: int,
        page_offset: int,
        limit: int,
        base_path: Optional[str] = None,
    ) -> Dict[str, str]:
        page_base = int(page_offset / limit) * limit
        first_args = (0, limit)
        last_args = (int(int(count / limit) * limit), limit)
        self_args = (page_base if page_base <= last_args[0] else last_args[0], limit)
        next_args = (page_offset + limit, limit) if page_offset + limit <= last_args[0] else last_args
        prev_args = (page_offset - limit, limit) if page_offset > limit else first_args
        links: Dict[str, str] = {
            "first": self._page_link(request, *first_args, base_path=base_path),
            "self": self._page_link(request, page_offset, limit, base_path=base_path),
            "last": self._page_link(request, *last_args, base_path=base_path),
            "prev": self._page_link(request, *prev_args, base_path=base_path),
            "next": self._page_link(request, *next_args, base_path=base_path),
        }
        if last_args == self_args:
            links.pop("last", None)
        if first_args == self_args:
            links.pop("first", None)
        if next_args == last_args:
            links.pop("next", None)
        if prev_args == first_args:
            links.pop("prev", None)
        return links

    @staticmethod
    def _query_or_items_count(value: Any) -> int:
        if value is None:
            return 0
        if hasattr(value, "count") and callable(value.count):
            try:
                return int(value.count())
            except Exception as exc:
                safrs.log.debug("Unable to evaluate count() for %s (%s)", type(value).__name__, type(exc).__name__)
        if isinstance(value, (list, tuple, set)):
            return len(value)
        return 1

    def _apply_pagination(self, value: Any, request: Request) -> Any:
        offset, limit = self._pagination_args(request)
        raw_limit = request.query_params.get("page[limit]")
        if raw_limit is not None:
            try:
                if int(str(raw_limit)) <= 0:
                    max_page_limit = int(getattr(safrs.SAFRS, "MAX_PAGE_LIMIT", limit) or limit)
                    if max_page_limit > 0:
                        limit = max_page_limit
            except (TypeError, ValueError):
                pass

        if self._is_query_like(value):
            query = value.offset(offset)
            return query.limit(limit)

        items = self._coerce_items(value)
        return items[offset : offset + limit]

    def _apply_sort_query_or_items(self, Model: Type[Any], value: Any, request: Request) -> Any:
        sort_terms = self._parse_sort_terms(request.query_params.get("sort"))

        if self._is_query_like(value):
            sorted_query = value
            for raw_attr, reverse in sort_terms:
                resolved_attr = self._resolve_sort_attr_name(Model, raw_attr)
                if not resolved_attr:
                    continue
                model_attr = getattr(Model, resolved_attr, None)
                if model_attr is None:
                    continue
                try:
                    ordered_query = sorted_query.order_by(model_attr.desc() if reverse else model_attr.asc())
                except Exception as exc:
                    safrs.log.debug("Unable to apply query sort for '%s' (%s)", resolved_attr, type(exc).__name__)
                else:
                    sorted_query = ordered_query
            return sorted_query

        return self._apply_sort_to_list(Model, self._coerce_items(value), sort_terms)

    def _apply_sort(self, items: Any, request: Request) -> List[Any]:
        """
        Backward-compatible list sorting helper used by internal tests.
        """
        sort_terms = self._parse_sort_terms(request.query_params.get("sort"))
        sorted_items = self._coerce_items(items)
        for raw_attr, reverse in reversed(sort_terms):
            attr_name = "id" if raw_attr == "id" else raw_attr
            try:
                candidate_items = sorted(
                    sorted_items,
                    key=lambda item: (getattr(item, attr_name, None) is None, getattr(item, attr_name, None)),
                    reverse=reverse,
                )
            except Exception as exc:
                safrs.log.debug("Unable to apply list sort for '%s' (%s)", attr_name, type(exc).__name__)
            else:
                sorted_items = candidate_items
        return sorted_items

    def _apply_filter(self, Model: Type[Any], request: Request, base_query: Any) -> Any:
        raw_filter = request.query_params.get("filter")
        bracket_filters: Dict[str, str] = {}
        for key, value in request.query_params.items():
            attr_name = parse_bracket_filter_name(key)
            if attr_name is not None:
                bracket_filters[attr_name] = value
        validate_bracket_filter_count(bracket_filters)

        if raw_filter is None:
            if bracket_filters:
                filtered_query = base_query
                for attr_name, attr_value in bracket_filters.items():
                    model_attr = require_filterable_attribute(Model, attr_name)
                    filter_values = coerce_filter_values(model_attr, attr_value, attr_name)
                    if self._is_query_like(filtered_query):
                        expression = bracket_filter_expression(model_attr, filter_values, attr_name)
                        filtered_query = filtered_query.filter(expression)
                    else:
                        items = self._coerce_items(filtered_query)
                        accepted = {str(value) for value in filter_values}
                        filtered_query = [item for item in items if str(getattr(item, attr_name, None)) in accepted]
                return apply_filter_read_permissions(Model, filtered_query, bracket_filters.keys())
            return base_query

        try:
            if "filter" in Model.__dict__ and callable(getattr(Model, "filter")):
                custom_filter = getattr(Model, "filter")
                declared_fields = custom_filter_read_fields(Model, custom_filter)
                filtered = custom_filter(raw_filter)
                filtered = apply_filter_read_permissions(Model, filtered, declared_fields)
            else:
                custom_filter = Model._s_filter
                declared_fields = (
                    () if uses_builtin_json_filter(Model) else custom_filter_read_fields(Model, custom_filter)
                )
                filtered = custom_filter(raw_filter)
                if uses_builtin_json_filter(Model):
                    filtered = apply_filter_read_permissions(Model, filtered, filter_attribute_names(raw_filter))
                else:
                    filtered = apply_filter_read_permissions(Model, filtered, declared_fields)
        except ValidationError as exc:
            self._jsonapi_error(400, "ValidationError", str(exc.message))
        except JsonapiError as exc:
            self._handle_safrs_exception(exc)
        except Exception as exc:
            self._handle_safrs_exception(exc)
        return validate_filter_result(filtered)

    def _normalize_jsonapi_id(self, Model: Type[Any], raw_id: Any) -> Any:
        id_type = getattr(Model, "id_type", None)
        validate = getattr(id_type, "validate_id", None) if id_type is not None else None
        if not callable(validate):
            return raw_id
        try:
            return validate(raw_id)
        except ValidationError as exc:
            self._jsonapi_error(400, "ValidationError", str(exc))
        except Exception:
            self._jsonapi_error(400, "ValidationError", "Invalid id")
        return raw_id

    def _lookup_related_instance(
        self,
        target_model: Type[Any],
        payload: Dict[str, Any],
        strict: bool = True,
        request: Optional[Request] = None,
        action: str = "link",
    ) -> Any:
        if not isinstance(payload, dict):
            self._jsonapi_error(400, "ValidationError", "Invalid data payload")
        rel_id = payload.get("id")
        rel_type = payload.get("type")
        if rel_id is None or rel_type is None:
            if strict:
                self._jsonapi_error(403, "ValidationError", "Invalid relationship payload")
            self._jsonapi_error(400, "ValidationError", "Invalid data payload")
        if rel_type != target_model._s_type:
            self._jsonapi_error(403, "ValidationError", "Invalid relationship type")
        normalized_rel_id = self._normalize_jsonapi_id(target_model, rel_id)
        try:
            target = target_model.get_instance(normalized_rel_id)
        except Exception:
            self._jsonapi_error(404, "NotFound", f"Related object {rel_id} not found")
        if target is None:
            self._jsonapi_error(404, "NotFound", f"Related object {rel_id} not found")
        # SEC-02: object-level authorization for the loaded target row.
        self._authorize_loaded_target(target_model, target, request, action)
        return target

    def _authorize_loaded_target(
        self,
        target_model: Type[Any],
        target: Any,
        request: Optional[Request],
        action: str,
    ) -> None:
        """SEC-02: authorize a target row loaded from a relationship payload.

        Runs the explicitly configured target operation policy and the
        model's object-level ``_s_check_instance_access`` hook. A denial
        raises before the unit of work commits, so the mutation rolls back.
        """
        if target is None:
            return
        if action == "read" and request is not None:
            self._authorize_instance_response(target_model, target, request)
        elif request is not None:
            self._authorize_operation(target_model, "delete" if action == "cascade_delete" else "update", request)
        try:
            run_instance_access_check(target_model, target, action)
        except (JSONAPIHTTPError, StarletteHTTPException):
            raise
        except Exception as exc:
            safrs.log.debug(
                "Target row authorization denied for %s (%s)",
                getattr(target_model, "__name__", target_model),
                type(exc).__name__,
            )
            self._jsonapi_error(
                int(getattr(exc, "status_code", None) or HTTPStatus.FORBIDDEN.value),
                "Forbidden",
                "The related resource is not authorized",
            )

    def _clear_relationship(self, rel_value: Any) -> None:
        current_items = self._iter_related_items(rel_value)
        for item in current_items:
            try:
                rel_value.remove(item)
            except Exception as exc:
                safrs.log.debug(
                    "Ignoring relationship remove error for %s (%s)",
                    type(item).__name__,
                    type(exc).__name__,
                )

    def _append_relationship_item(self, rel_value: Any, item: Any) -> None:
        if hasattr(rel_value, "append"):
            rel_value.append(item)
            return
        self._jsonapi_error(400, "ValidationError", "Relationship is not appendable")

    def _remove_relationship_item(self, rel_value: Any, item: Any) -> None:
        if hasattr(rel_value, "remove"):
            try:
                rel_value.remove(item)
            except ValueError:
                # DELETE relationship operations are idempotent; removing a non-member is a no-op.
                return
            return
        self._jsonapi_error(400, "ValidationError", "Relationship is not removable")

    def _collect_included(
        self,
        current_model: Type[Any],
        obj: Any,
        include_paths: List[List[str]],
        fields_map: Dict[str, Set[str]],
        seen: Set[Tuple[str, str]],
        included: List[Dict[str, Any]],
    ) -> None:
        for path in include_paths:
            if not path:
                continue
            rel_name = path[0]
            rels = self._resolve_relationship_properties(current_model)
            rel = rels.get(rel_name)
            if rel is None:
                continue
            target_model = rel.mapper.class_
            if not hasattr(target_model, "_s_type"):
                continue
            rel_value = getattr(obj, rel_name, None)
            context = maybe_jsonapi_context()
            rel_limit = context.get_relationship_page_limit(rel_name) if context is not None else None
            rel_items = self._iter_related_items(rel_value, limit=rel_limit)
            for rel_obj in rel_items:
                if rel_obj is None:
                    continue
                key = (str(target_model._s_type), str(rel_obj.jsonapi_id))
                next_include_names: Set[str] = set()
                if len(path) > 1:
                    next_include_names.add(str(path[1]))
                if key not in seen:
                    max_included = int(getattr(safrs.SAFRS, "MAX_INCLUDED_RESOURCES", 0) or 0)
                    if max_included > 0 and len(included) >= max_included:
                        self._jsonapi_error(
                            400,
                            "ValidationError",
                            f"Included resources exceed maximum item count {max_included}",
                        )
                    seen.add(key)
                    included.append(
                        self._encode_resource(
                            target_model,
                            rel_obj,
                            wanted_fields=fields_map.get(str(target_model._s_type)),
                            include_relationships=True,
                            include_links=True,
                            include_relationship_names=next_include_names,
                        )
                    )
                if len(path) > 1:
                    self._collect_included(
                        target_model,
                        rel_obj,
                        [path[1:]],
                        fields_map,
                        seen,
                        included,
                    )

    def _relationship_data(
        self,
        rel_prop: Any,
        rel_name: str,
        rel_value: Any,
        *,
        include_data: bool,
    ) -> Any:
        if self._is_to_many_relationship(rel_prop):
            # Match Flask SAFRS responses: avoid embedding full linkage arrays by default.
            return []
        if not include_data:
            return None
        if rel_value is None:
            return None
        target_model = rel_prop.mapper.class_
        target_type = str(getattr(target_model, "_s_type", target_model.__name__))
        try:
            return {"type": target_type, "id": str(rel_value.jsonapi_id)}
        except Exception:
            safrs.log.debug(f"Unable to build relationship linkage for {rel_name}")
            return None

    def _encode_relationships(
        self,
        Model: Type[Any],
        obj: Any,
        *,
        include_relationship_names: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        relationships: Dict[str, Any] = {}
        include_all_relationships = include_relationship_names is None
        for rel_name, rel_prop in self._resolve_relationship_properties(Model).items():
            rel_value = getattr(obj, rel_name, None)
            include_data = include_all_relationships or (
                include_relationship_names is not None and str(rel_name) in include_relationship_names
            )
            relationships[str(rel_name)] = {
                "links": {"self": self._relationship_self_path(Model, obj, str(rel_name))},
                "data": self._relationship_data(
                    rel_prop,
                    str(rel_name),
                    rel_value,
                    include_data=bool(include_data),
                ),
            }
        return relationships

    @staticmethod
    def _normalize_attr_value_for_jsonapi(attr_val: Any) -> Any:
        if isinstance(attr_val, dt.datetime):
            if attr_val.tzinfo is None:
                attr_val = attr_val.replace(tzinfo=dt.timezone.utc)
            return attr_val.isoformat()
        if isinstance(attr_val, dt.date):
            return attr_val.isoformat()
        if isinstance(attr_val, dt.time):
            if attr_val.tzinfo is None:
                attr_val = attr_val.replace(tzinfo=dt.timezone.utc)
            return attr_val.isoformat()
        return attr_val

    @staticmethod
    def _fallback_encoded_attributes(Model: Type[Any], obj: Any, wanted_fields: Optional[Set[str]]) -> Dict[str, Any]:
        attrs: Dict[str, Any] = {}
        model_attrs = getattr(Model, "_s_jsonapi_attrs", {})
        for attr_name in model_attrs.keys():
            if wanted_fields is not None and attr_name not in wanted_fields:
                continue
            try:
                raw_value = getattr(obj, attr_name)
            except Exception:
                raw_value = None
            attrs[attr_name] = SafrsFastAPI._normalize_attr_value_for_jsonapi(raw_value)
        return attrs

    def _fallback_encode_resource(self, Model: Type[Any], obj: Any, wanted_fields: Optional[Set[str]]) -> Dict[str, Any]:
        attrs = self._fallback_encoded_attributes(Model, obj, wanted_fields)
        return {
            "type": str(getattr(Model, "_s_type", Model.__name__)),
            "id": str(getattr(obj, "jsonapi_id", "")),
            "attributes": jsonable_encoder(attrs),
        }

    def _model_encode_resource(self, obj: Any) -> Dict[str, Any]:
        token = None
        if maybe_jsonapi_context() is None:
            token = set_jsonapi_context(JsonApiContext(query_params={}, prefix=self.prefix))
        try:
            return cast(Dict[str, Any], obj._s_jsonapi_encode())
        finally:
            if token is not None:
                reset_jsonapi_context(token)

    @staticmethod
    def _prune_encoded_resource(
        result: Dict[str, Any], wanted_fields: Optional[Set[str]], *, include_links: bool, include_relationships: bool
    ) -> Dict[str, Any]:
        if wanted_fields is not None:
            attrs = cast(Dict[str, Any], result.get("attributes", {}))
            result["attributes"] = {name: value for name, value in attrs.items() if name in wanted_fields}
        if not include_links:
            result.pop("links", None)
        if not include_relationships:
            result.pop("relationships", None)
        return result

    def _encode_resource(
        self,
        Model: Type[Any],
        obj: Any,
        wanted_fields: Optional[Set[str]] = None,
        *,
        include_relationships: bool = True,
        include_links: bool = True,
        include_relationship_names: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        # Delegate resource serialization to the shared SAFRS/Flask pipeline.
        # This keeps FastAPI output in lockstep with Flask behavior.
        _ = include_relationship_names
        if not hasattr(obj, "_s_jsonapi_encode"):
            return self._fallback_encode_resource(Model, obj, wanted_fields)

        encoded = self._model_encode_resource(obj)
        return self._prune_encoded_resource(
            encoded,
            wanted_fields,
            include_links=include_links,
            include_relationships=include_relationships,
        )

    def _get_collection(self, Model: Type[Any]):
        def handler(request: Request):
            context_token = None
            try:
                self._authorize_operation(Model, "read", request)
                # Validate include paths early so invalid relationships fail with 400.
                self._parse_include_paths(Model, request)
                if maybe_jsonapi_context() is None:
                    context_token = set_jsonapi_context(self._build_jsonapi_context(request))
                query_or_items = Model._s_get()
                query_or_items = self._authorize_collection_before_metadata(Model, query_or_items, request)
                query_or_items = self._apply_sort_query_or_items(Model, query_or_items, request)
                total_count = self._query_or_items_count(query_or_items)
                page_offset, page_limit = self._pagination_args(request)
                paged = self._apply_pagination(query_or_items, request)
                objs = self._coerce_items(paged)
                links = self._pagination_links(
                    request,
                    count=total_count,
                    page_offset=page_offset,
                    limit=page_limit,
                )
                return self._jsonapi_data_response(
                    data=objs,
                    links=links,
                    meta={"count": total_count, "total": total_count, "limit": page_limit},
                    count=total_count,
                    request=request,
                )
            except Exception as exc:
                self._handle_safrs_exception(exc)
            finally:
                if context_token is not None:
                    reset_jsonapi_context(context_token)

        return handler

    def _get_instance(self, Model: Type[Any]):
        def handler(object_id: ObjectIdParam, request: Request):
            try:
                self._authorize_operation(Model, "read", request)
                obj = Model.get_instance(object_id)
                # Validate include paths early so invalid relationships fail with 400.
                self._parse_include_paths(Model, request)
                # SEC-02: object-level policies apply to direct reads too.
                self._authorize_loaded_target(Model, obj, request, "read")
                links = self._instance_links(request, Model, obj)
                return self._jsonapi_data_response(
                    data=obj,
                    links=links,
                    meta={"instance_meta": obj._s_meta()},
                    count=1,
                    request=request,
                )
            except Exception as exc:
                self._handle_safrs_exception(exc)

        return handler

    def _coerce_post_items(self, Model: Type[Any], payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        validate_json_payload(payload)
        raw_data = payload.get("data")
        if isinstance(raw_data, list):
            self._validate_collection_size(raw_data, "Bulk POST")
            return raw_data
        self._require_type(Model, payload)
        return [payload.get("data") or {}]

    def _create_post_object(
        self, Model: Type[Any], data: Dict[str, Any], request: Optional[Request] = None
    ) -> Tuple[Any, bool]:
        if not isinstance(data, dict):
            self._jsonapi_error(400, "ValidationError", "Invalid JSON:API payload (data item must be object)")
        if data.get("type") != Model._s_type:
            self._jsonapi_error(400, "ValidationError", "Invalid type: expected " + str(Model._s_type))
        attrs = cast(Dict[str, Any], data.get("attributes") or {})
        rels = data.get("relationships") or {}
        jsonapi_id = data.get("id")
        get_upsert_target = getattr(Model, "_s_get_upsert_target", None)
        upsert_target = get_upsert_target(jsonapi_id, **attrs) if callable(get_upsert_target) else None
        if upsert_target is not None:
            # POST transport does not grant update permission. The existing-row
            # branch shares PATCH's explicit policy, even on POST-only models.
            self._authorize_operation(Model, "update", request)
            # SEC-02: upsert rewrites an existing row; enforce its policy.
            run_instance_access_check(Model, upsert_target, "link")
            return upsert_target._s_update_from_post(**attrs, **rels), False
        self._authorize_operation(Model, "create", request)
        create_method = getattr(Model, "_s_post_prechecked", Model._s_post)
        return create_method(jsonapi_id=jsonapi_id, **attrs, **rels), True

    @staticmethod
    def _append_auto_include_paths(include_paths: List[List[str]], obj: Any) -> None:
        auto_include = getattr(obj, "included_list", None) or []
        for include_item in auto_include:
            if not isinstance(include_item, str) or not include_item:
                continue
            path = [segment for segment in include_item.split(".") if segment]
            if path:
                include_paths.append(path)

    @staticmethod
    def _dedupe_include_paths(include_paths: List[List[str]]) -> List[List[str]]:
        deduped_include_paths: List[List[str]] = []
        seen_paths: Set[Tuple[str, ...]] = set()
        for include_path in include_paths:
            include_tuple = tuple(include_path)
            if not include_tuple or include_tuple in seen_paths:
                continue
            seen_paths.add(include_tuple)
            deduped_include_paths.append(include_path)
        return deduped_include_paths

    def _collect_included_for_created(
        self,
        Model: Type[Any],
        created: List[Any],
        include_paths: List[List[str]],
        fields_map: Dict[str, Set[str]],
    ) -> List[Dict[str, Any]]:
        included: List[Dict[str, Any]] = []
        seen_included: Set[Tuple[str, str]] = set()
        for item in created:
            self._collect_included(Model, item, include_paths, fields_map, seen_included, included)
        return included

    def _build_post_response(
        self,
        Model: Type[Any],
        created: List[Any],
        wanted_fields: Optional[Set[str]],
        include_paths: List[List[str]],
        included: List[Dict[str, Any]],
        request: Optional[Request] = None,
        all_created: bool = True,
    ) -> JSONAPIResponse:
        _ = wanted_fields
        _ = include_paths
        _ = included
        data_doc: Any
        headers: Optional[Dict[str, str]] = None
        if len(created) == 1:
            data_doc = created[0]
            collection_name = getattr(Model, "_s_collection_name", None)
            if collection_name and all_created:
                prefix = (self.prefix or "").rstrip("/")
                if prefix and not prefix.startswith("/"):
                    prefix = "/" + prefix
                encoded_id = quote(str(created[0].jsonapi_id), safe="")
                collection = str(collection_name).strip("/")
                location = f"{prefix}/{collection}/{encoded_id}" if prefix else f"/{collection}/{encoded_id}"
                headers = {"Location": location}
        else:
            data_doc = created
        return self._jsonapi_data_response(
            data=data_doc,
            status_code=201 if all_created else 200,
            headers=headers,
            count=len(created),
            request=request,
        )

    def _post_collection(self, Model: Type[Any]):
        def handler(
            request: Request,
            payload: Dict[str, Any] = Body(..., media_type=JSONAPI_MEDIA_TYPE)
        ):
            try:
                items = self._coerce_post_items(Model, payload)
                fields_map = self._parse_sparse_fields_map(request)
                wanted_fields = fields_map.get(str(Model._s_type)) or self._parse_sparse_fields(Model, request)
                include_paths = self._parse_include_paths(Model, request)
                created: List[Any] = []
                created_flags: List[bool] = []
                for data in items:
                    self._note_write(Model)
                    obj, was_created = self._create_post_object(Model, data, request)
                    created.append(obj)
                    created_flags.append(was_created)
                    self._append_auto_include_paths(include_paths, obj)
                for obj in created:
                    self._authorize_instance_response(Model, obj, request)
                deduped_include_paths = self._dedupe_include_paths(include_paths)
                # The shared formatter serializes includes under the same
                # authorization context. Pre-encoding here marks related rows
                # as primary data and causes Included.encode() to omit them.
                return self._build_post_response(
                    Model,
                    created,
                    wanted_fields,
                    deduped_include_paths,
                    [],
                    request=request,
                    all_created=all(created_flags),
                )
            except JSONAPIHTTPError:
                raise
            except Exception as exc:
                self._handle_safrs_exception(exc)

        return handler

    def _patch_instance(self, Model: Type[Any]):
        def handler(
            object_id: ObjectIdParam,
            request: Request,
            payload: Dict[str, Any] = Body(..., media_type=JSONAPI_MEDIA_TYPE),
        ):
            try:
                validate_json_payload(payload)
                self._authorize_operation(Model, "update", request)
                self._require_type(Model, payload)
                data = payload.get("data") or {}

                # Enforce JSON:API resource id parity with URL id
                normalized_path_id = self._normalize_jsonapi_id(Model, object_id)
                body_id = data.get("id")
                enforce_body_id = hasattr(Model, "_s_collection_name")
                if enforce_body_id and body_id is None:
                    self._jsonapi_error(400, "ValidationError", "Missing id in request body")
                if body_id is not None:
                    normalized_body_id = self._normalize_jsonapi_id(Model, body_id)
                    if normalized_body_id != normalized_path_id:
                        self._jsonapi_error(400, "ValidationError", "Body id does not match path id")

                attrs = cast(Dict[str, Any], data.get("attributes") or {})

                obj = Model.get_instance(object_id)
                self._note_write(Model)
                obj = obj._s_patch(**attrs)
                self._authorize_instance_response(Model, obj, request)
                self._parse_include_paths(Model, request)
                links = self._instance_links(request, Model, obj)
                return self._jsonapi_data_response(
                    data=obj,
                    links=links,
                    meta={"instance_meta": obj._s_meta()},
                    count=1,
                    request=request,
                )
            except JSONAPIHTTPError:
                raise
            except Exception as exc:
                self._handle_safrs_exception(exc)

        return handler

    def _delete_instance(self, Model: Type[Any]):
        def handler(object_id: ObjectIdParam):
            try:
                self._authorize_operation(Model, "delete")
                begin_current_protected_write(Model)
                obj = Model.get_instance(object_id)
                self._note_write(Model)
                obj._s_delete()
                return Response(status_code=204)
            except JSONAPIHTTPError:
                raise
            except Exception as exc:
                self._handle_safrs_exception(exc)

        return handler

    def _get_relationship(self, Model: Type[Any], rel_name: str):
        def handler(object_id: ObjectIdParam, request: Request):
            try:
                self._authorize_relationship_response(Model, object_id, rel_name, request)
                parent = Model.get_instance(object_id)
                rel = self._resolve_relationship_properties(Model).get(rel_name)
                if rel is None:
                    self._jsonapi_error(404, "NotFound", f"Unknown relationship '{rel_name}'")
                target_model = rel.mapper.class_
                require_current_instance(parent, "read", [rel_name])
                self._parse_include_paths(target_model, request)
                rel_value = getattr(parent, rel_name, None)

                if self._is_to_many_relationship(rel):
                    if current_model_is_registered(target_model):
                        rel_value = get_db().session.query(target_model).with_parent(
                            parent, property=rel
                        )
                    query_or_items = self._apply_filter(target_model, request, rel_value)
                    query_or_items = target_model._s_query_scope(query_or_items)
                    query_or_items = self._authorize_collection_before_metadata(
                        target_model, query_or_items, request
                    )
                    query_or_items = self._apply_sort_query_or_items(target_model, query_or_items, request)
                    total_count = self._query_or_items_count(query_or_items)
                    page_offset, page_limit = self._pagination_args(request)
                    paged = self._apply_pagination(query_or_items, request)
                    items = self._coerce_items(paged)
                    links = self._pagination_links(
                        request,
                        count=total_count,
                        page_offset=page_offset,
                        limit=page_limit,
                        base_path=self._collection_path(target_model),
                    )
                    return self._jsonapi_data_response(
                        data=items,
                        links=links,
                        meta={"count": len(items), "total": total_count, "limit": page_limit},
                        count=len(items),
                        request=request,
                    )

                if rel_value is None:
                    self._jsonapi_error(404, "NotFound", f"Relationship '{rel_name}' is empty")
                return self._jsonapi_data_response(
                    data=rel_value,
                    count=1,
                    request=request,
                )
            except Exception as exc:
                self._handle_safrs_exception(exc)

        return handler

    def _get_relationship_item(self, Model: Type[Any], rel_name: str):
        def handler(object_id: ObjectIdParam, target_id: TargetIdParam, request: Request):
            try:
                self._authorize_relationship_response(Model, object_id, rel_name, request)
                parent = Model.get_instance(object_id)
                rel = self._resolve_relationship_properties(Model).get(rel_name)
                if rel is None:
                    self._jsonapi_error(404, "NotFound", f"Unknown relationship '{rel_name}'")
                target_model = rel.mapper.class_
                require_current_instance(parent, "read", [rel_name])
                normalized_target_id = self._normalize_jsonapi_id(target_model, target_id)
                self._parse_include_paths(target_model, request)
                rel_value = getattr(parent, rel_name, None)
                if current_model_is_registered(target_model) and self._is_to_many_relationship(rel):
                    rel_value = get_db().session.query(target_model).with_parent(
                        parent, property=rel
                    )
                    rel_value = target_model._s_query_scope(rel_value)
                    rel_value = apply_authorization_scope(target_model, rel_value)
                for item in self._iter_related_items(rel_value):
                    item_id = self._normalize_jsonapi_id(target_model, item.jsonapi_id)
                    if item_id == normalized_target_id:
                        return self._jsonapi_data_response(
                            data=item,
                            count=1,
                            request=request,
                        )
                self._jsonapi_error(404, "NotFound", f"Relationship item '{target_id}' not found")
            except Exception as exc:
                self._handle_safrs_exception(exc)

        return handler

    def _patch_relationship(self, Model: Type[Any], rel_name: str):
        def handler(
            object_id: ObjectIdParam,
            request: Request,
            payload: Dict[str, Any] = Body(..., media_type=JSONAPI_MEDIA_TYPE),
        ):
            try:
                request_obj: Optional[Request] = request if isinstance(request, Request) else None
                payload_obj: Any = payload
                if not isinstance(request, Request):
                    payload_obj = request
                if not isinstance(payload_obj, dict):
                    self._jsonapi_error(400, "ValidationError", "Invalid JSON:API payload (expected object)")
                validate_json_payload(payload_obj)
                self._authorize_operation(Model, "update", request_obj)
                parent = Model.get_instance(object_id)
                rel = self._resolve_relationship_properties(Model).get(rel_name)
                if rel is None:
                    self._jsonapi_error(404, "NotFound", f"Unknown relationship '{rel_name}'")
                check_relationship_write_permission(parent, rel_name)
                target_model = rel.mapper.class_
                if "data" not in payload_obj:
                    self._jsonapi_error(400, "ValidationError", "Missing 'data' member in request body")
                data = payload_obj.get("data")
                rel_value = getattr(parent, rel_name, None)
                self._note_write(Model)

                if self._is_to_many_relationship(rel):
                    if not isinstance(data, list):
                        self._jsonapi_error(400, "ValidationError", "PATCH a TOMANY relationship with a list")
                    self._validate_collection_size(data, "Relationship PATCH")
                    for removed in self._iter_related_items(rel_value):
                        self._authorize_loaded_target(target_model, removed, request_obj, "unlink")
                    self._clear_relationship(rel_value)
                    for item in data:
                        target = self._lookup_related_instance(target_model, item, request=request_obj, action="link")
                        self._append_relationship_item(rel_value, target)
                    if tx.in_request():
                        get_db().session.flush()
                    items = self._iter_related_items(rel_value)
                    if request_obj is not None:
                        self._authorize_relationship_response(Model, object_id, rel_name, request_obj)
                    return self._jsonapi_data_response(
                        data=items,
                        meta={"count": len(items)},
                        count=len(items),
                        request=request_obj,
                    )

                if data is None:
                    self._authorize_loaded_target(target_model, rel_value, request_obj, "unlink")
                    setattr(parent, rel_name, None)
                    if tx.in_request():
                        get_db().session.flush()
                    return Response(status_code=204)
                if not isinstance(data, dict):
                    self._jsonapi_error(400, "ValidationError", "Invalid data payload")
                target = self._lookup_related_instance(target_model, data, request=request_obj, action="link")
                if rel_value is not None and rel_value is not target:
                    self._authorize_loaded_target(target_model, rel_value, request_obj, "unlink")
                setattr(parent, rel_name, target)
                if tx.in_request():
                    get_db().session.flush()
                if rel_name == "thing":
                    if request_obj is not None:
                        self._authorize_relationship_response(Model, object_id, rel_name, request_obj)
                    return self._jsonapi_data_response(data=target, count=1, request=request_obj)
                return Response(status_code=204)
            except Exception as exc:
                self._handle_safrs_exception(exc)

        return handler

    def _post_relationship(self, Model: Type[Any], rel_name: str):
        def handler(
            object_id: ObjectIdParam,
            request: Request,
            payload: Dict[str, Any] = Body(..., media_type=JSONAPI_MEDIA_TYPE),
        ):
            try:
                request_obj: Optional[Request] = request if isinstance(request, Request) else None
                payload_obj: Any = payload
                if not isinstance(request, Request):
                    payload_obj = request
                if not isinstance(payload_obj, dict):
                    self._jsonapi_error(400, "ValidationError", "Invalid JSON:API payload (expected object)")
                validate_json_payload(payload_obj)
                self._authorize_operation(Model, "update", request_obj)
                parent = Model.get_instance(object_id)
                rel = self._resolve_relationship_properties(Model).get(rel_name)
                if rel is None:
                    self._jsonapi_error(404, "NotFound", f"Unknown relationship '{rel_name}'")
                check_relationship_write_permission(parent, rel_name)
                target_model = rel.mapper.class_
                data = payload_obj.get("data")
                rel_value = getattr(parent, rel_name, None)
                self._note_write(Model)

                if self._is_to_many_relationship(rel):
                    if not isinstance(data, list):
                        self._jsonapi_error(400, "ValidationError", "Invalid data payload")
                    self._validate_collection_size(data, "Relationship POST")
                    for item in data:
                        target = self._lookup_related_instance(target_model, item, request=request_obj, action="link")
                        self._append_relationship_item(rel_value, target)
                    if tx.in_request():
                        get_db().session.flush()
                    return Response(status_code=204)

                if not isinstance(data, dict):
                    self._jsonapi_error(400, "ValidationError", "Invalid data payload")
                target = self._lookup_related_instance(target_model, data, request=request_obj, action="link")
                setattr(parent, rel_name, target)
                if tx.in_request():
                    get_db().session.flush()
                if request_obj is not None:
                    self._authorize_relationship_response(Model, object_id, rel_name, request_obj)
                return self._jsonapi_response(self._jsonapi_doc(data=self._encode_resource(target_model, target)))
            except Exception as exc:
                self._handle_safrs_exception(exc)

        return handler

    def _delete_relationship(self, Model: Type[Any], rel_name: str):
        def handler(
            object_id: ObjectIdParam,
            payload: Dict[str, Any] = Body(..., media_type=JSONAPI_MEDIA_TYPE),
            request: Annotated[Request, "safrs-sec02"] = None,  # type: ignore[assignment]
        ):
            try:
                request_obj: Optional[Request] = request if isinstance(request, Request) else None
                validate_json_payload(payload)
                self._authorize_operation(Model, "update", request_obj)
                parent = Model.get_instance(object_id)
                rel = self._resolve_relationship_properties(Model).get(rel_name)
                if rel is None:
                    self._jsonapi_error(404, "NotFound", f"Unknown relationship '{rel_name}'")
                check_relationship_write_permission(parent, rel_name)
                target_model = rel.mapper.class_
                data = payload.get("data")
                rel_value = getattr(parent, rel_name, None)
                self._note_write(Model)

                if self._is_to_many_relationship(rel):
                    if not isinstance(data, list):
                        self._jsonapi_error(400, "ValidationError", "Invalid data payload")
                    self._validate_collection_size(data, "Relationship DELETE")
                    for item in data:
                        target = self._lookup_related_instance(target_model, item, request=request_obj, action="unlink")
                        self._remove_relationship_item(rel_value, target)
                    if tx.in_request():
                        get_db().session.flush()
                    return Response(status_code=204)

                if isinstance(data, list):
                    if data and isinstance(data[0], dict):
                        safrs.log.warning("Invalid Payload to delete from MANYTOONE relationship")
                        data = data[0]
                    else:
                        self._jsonapi_error(400, "ValidationError", "Invalid data payload")
                if not isinstance(data, dict):
                    self._jsonapi_error(400, "ValidationError", "Invalid data payload")
                target = self._lookup_related_instance(target_model, data, strict=True, request=request_obj, action="unlink")
                current = getattr(parent, rel_name, None)
                if current is not None and str(current.jsonapi_id) == str(target.jsonapi_id):
                    setattr(parent, rel_name, None)
                else:
                    safrs.log.warning("child not in relation")
                if tx.in_request():
                    get_db().session.flush()
                return Response(status_code=204)
            except Exception as exc:
                self._handle_safrs_exception(exc)

        return handler
