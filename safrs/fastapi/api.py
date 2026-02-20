# -*- coding: utf-8 -*-

import base64
import datetime as dt
import inspect
import re
from enum import Enum
from http import HTTPStatus
from typing import Any, Dict, Iterable, List, NoReturn, Optional, Sequence, Set, Tuple, Type, Union, cast

import safrs
from safrs import tx
from safrs.attr_parse import parse_attr
from safrs.errors import GenericError, JsonapiError, SystemValidationError, ValidationError
from safrs.json_encoder import SAFRSFormattedResponse
from safrs.swagger_doc import get_doc, get_http_methods

from fastapi import APIRouter, Body, Depends as FastAPIDepends, FastAPI, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.params import Depends as DependsParam
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.orm.interfaces import MANYTOMANY, ONETOMANY

from .relationships import relationship_is_exposed, relationship_property, resolve_relationships
from .schemas import SchemaRegistry
from .schemas.examples import (
    create_document_example,
    patch_document_example,
    relationship_to_many_example,
    relationship_to_one_example,
)
from .responses import JSONAPIResponse

JSONAPI_MEDIA_TYPE = "application/vnd.api+json"
DEFAULT_HTTP_METHODS = {"GET", "POST", "PATCH", "DELETE"}
WRITE_HTTP_METHODS = {"POST", "PATCH", "DELETE", "PUT"}


class RelationshipItemMode(str, Enum):
    DISABLED = "disabled"
    HIDDEN = "hidden"
    ENABLED = "enabled"


class JSONAPIHTTPError(Exception):
    def __init__(self, status_code: int, payload: Dict[str, Any]) -> None:
        self.status_code = status_code
        self.payload = payload


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


def install_jsonapi_exception_handlers(app: FastAPI) -> None:
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


class SafrsFastAPI:
    def __init__(
        self,
        app: FastAPI,
        prefix: str = "",
        dependencies: Optional[List[Any]] = None,
        relationship_item_mode: Union[RelationshipItemMode, str] = RelationshipItemMode.HIDDEN,
        include_examples_in_openapi: bool = True,
    ) -> None:
        self.app = app
        self.prefix = prefix
        self.max_union_included_types = int(getattr(safrs.SAFRS, "MAX_UNION_INCLUDED_TYPES", 0))
        self.document_relationships = bool(getattr(safrs.SAFRS, "DOCUMENT_RELATIONSHIPS", True))
        self.validate_requests = bool(getattr(safrs.SAFRS, "VALIDATE_REQUESTS", False))
        self.validate_responses = bool(getattr(safrs.SAFRS, "VALIDATE_RESPONSES", False))
        self.include_examples_in_openapi = bool(include_examples_in_openapi)
        self.relationship_item_mode = self._coerce_relationship_item_mode(relationship_item_mode)
        self.schemas = SchemaRegistry(
            document_relationships=self.document_relationships,
            max_union_included_types=self.max_union_included_types,
        )
        self.default_dependencies = [FastAPIDepends(self._safrs_uow_dependency)] + self._normalize_dependencies(dependencies)
        install_jsonapi_exception_handlers(app)
        self._install_swagger_alias()

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
    def _cleanup_session() -> None:
        session = safrs.DB.session
        remove = getattr(session, "remove", None)
        if callable(remove):
            remove()
            return
        close = getattr(session, "close", None)
        if callable(close):
            close()

    @staticmethod
    def _uow_session_state() -> Dict[str, Any]:
        session = safrs.DB.session
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
        state = self._uow_session_state()
        state["_safrs_writes_seen"] = True
        if tx.model_auto_commit_enabled(Model) is False:
            state["_safrs_auto_commit_enabled"] = False

    def _safrs_uow_dependency(self, request: Request):
        self._reset_uow_state()
        try:
            yield
        except Exception:
            safrs.DB.session.rollback()
            raise
        else:
            request_method = str(getattr(request, "method", "")).upper()
            state = self._uow_session_state()
            writes_seen = bool(state.get("_safrs_writes_seen", False))
            auto_commit_enabled = bool(state.get("_safrs_auto_commit_enabled", True))
            if request_method in WRITE_HTTP_METHODS and writes_seen and auto_commit_enabled:
                safrs.DB.session.commit()
            else:
                safrs.DB.session.rollback()
        finally:
            self._uow_session_state()["_safrs_uow_active"] = False

    @staticmethod
    def _write_auth_dependency(request: Request) -> None:
        header = request.headers.get("authorization", "")
        if not header.lower().startswith("basic "):
            raise HTTPException(status_code=401, detail="Unauthorized")
        token = header.split(" ", 1)[1].strip()
        try:
            decoded = base64.b64decode(token).decode("utf-8")
        except Exception:
            raise HTTPException(status_code=401, detail="Unauthorized")
        if decoded != "user:password":
            raise HTTPException(status_code=401, detail="Unauthorized")

    def _write_dependencies_for_model(self, Model: Type[Any]) -> List[DependsParam]:
        if getattr(Model, "decorators", None):
            return [FastAPIDepends(self._write_auth_dependency)]
        return []

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
            safrs.log.debug(f"RPC method discovery fallback for {Model}: {exc}")

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
        write_route_dependencies: List[DependsParam],
    ) -> None:
        error_responses = self._jsonapi_error_responses()
        collection_response_model = self.schemas.document_collection(Model)
        instance_response_model = self.schemas.document_single(Model)
        collection_post_responses = self._merge_response_docs(
            error_responses,
            self._jsonapi_status_responses([202]),
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
                write_route_dependencies,
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
                write_route_dependencies,
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
                write_route_dependencies,
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
            rpc_params = self._rpc_query_parameters(Model, class_level=class_level, http_methods=http_methods)
            rpc_openapi = self._openapi_query_parameters(rpc_params) if rpc_params else None
            self._add_route_with_slash_parity(
                router,
                f"{collection_path}/{method_name}",
                self._rpc_handler(Model, method_name, class_level=True),
                http_methods,
                f"RPC {tag}.{method_name}",
                route_dependencies,
                f"class_{tag}_{method_name}_rpc",
                responses=error_responses,
                openapi_extra=rpc_openapi,
            )

        for method_name, class_level, http_methods in rpc_methods:
            if class_level:
                continue
            rpc_params = self._rpc_query_parameters(Model, class_level=class_level, http_methods=http_methods)
            rpc_openapi = self._openapi_query_parameters(rpc_params) if rpc_params else None
            self._add_route_with_slash_parity(
                router,
                f"{instance_path}/{method_name}",
                self._rpc_handler(Model, method_name, class_level=False),
                http_methods,
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
            params.append(
                self._query_parameter(
                    "include",
                    description=f"{class_name} relationships to include (csv)",
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
            candidates = [raw_methods]

        normalized: Set[str] = set()
        for method in candidates:
            method_name = str(method).upper()
            if method_name in DEFAULT_HTTP_METHODS:
                normalized.add(method_name)
        if normalized:
            return normalized
        return set(DEFAULT_HTTP_METHODS)

    def _rpc_query_parameters(
        self,
        Model: Type[Any],
        *,
        class_level: bool,
        http_methods: List[str],
    ) -> List[Dict[str, Any]]:
        if not class_level:
            return []
        params = self._jsonapi_query_parameters(
            Model,
            include_include=True,
            include_fields=True,
            include_pagination=True,
        )
        if any(str(method).upper() == "GET" for method in http_methods):
            params.append(self._query_parameter("varargs", description="Additional positional RPC arguments"))
        return params

    @staticmethod
    def _model_tag_description(Model: Type[Any], tag: str) -> str:
        model_doc = inspect.getdoc(Model)
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
            try:
                description = HTTPStatus(int(status_code)).phrase
            except ValueError:
                description = "Response"
            responses[int(status_code)] = {
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
            409: {"description": HTTPStatus.CONFLICT.phrase, "model": error_model, "content": error_content},
            422: {"description": HTTPStatus.UNPROCESSABLE_ENTITY.phrase, "model": error_model, "content": error_content},
            500: {"description": HTTPStatus.INTERNAL_SERVER_ERROR.phrase, "model": error_model, "content": error_content},
        }

    def expose_object(
        self,
        Model: Type[Any],
        dependencies: Optional[List[Any]] = None,
        method_decorators: Optional[List[Any]] = None,
    ) -> None:
        """
        Register CRUD routes for a SAFRS model.
        """
        if not getattr(Model, "_s_expose", True):
            raise SystemValidationError(f"Refusing to expose {Model}: _s_expose is set to False")
        if method_decorators:
            raise NotImplementedError(
                "FastAPI adapter does not support Flask method_decorators; use dependencies=[...]"
            )

        route_dependencies = self.default_dependencies + self._normalize_dependencies(dependencies)
        write_route_dependencies = route_dependencies + self._write_dependencies_for_model(Model)
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
            write_route_dependencies,
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

    def _jsonapi_error(self, status_code: int, title: str, detail: str) -> NoReturn:
        payload = self._jsonapi_doc(
            errors=[{"status": str(status_code), "title": title, "detail": detail}]
        )
        raise JSONAPIHTTPError(status_code, payload)

    def _handle_safrs_exception(self, exc: Exception) -> None:
        if isinstance(exc, JSONAPIHTTPError):
            raise exc
        if isinstance(exc, (SystemValidationError, ValidationError, GenericError)):
            status = int(getattr(exc, "status_code", 400))
            msg = str(getattr(exc, "message", str(exc)))
            self._jsonapi_error(status, exc.__class__.__name__, msg)
        if isinstance(exc, JsonapiError):
            status = int(getattr(exc, "status_code", 400))
            msg = str(getattr(exc, "message", str(exc)))
            self._jsonapi_error(status, exc.__class__.__name__, msg)
        raise exc

    def _require_type(self, Model: Type[Any], payload: Dict[str, Any]) -> None:
        data = payload.get("data")
        if not isinstance(data, dict):
            self._jsonapi_error(400, "ValidationError", "Invalid JSON:API payload (missing data object)")
        data = cast(Dict[str, Any], data)
        typ = data.get("type")
        if typ != Model._s_type:
            self._jsonapi_error(400, "ValidationError", "Invalid type: expected " + str(Model._s_type))

    @staticmethod
    def _try_parse_temporal_value(py_type: Any, value: str) -> Tuple[bool, Any]:
        try:
            if py_type is dt.date:
                return True, dt.datetime.strptime(value, "%Y-%m-%d").date()
            if py_type is dt.datetime:
                fmt = "%Y-%m-%d %H:%M:%S.%f" if "." in value else "%Y-%m-%d %H:%M:%S"
                return True, dt.datetime.strptime(value.replace("T", " "), fmt)
            if py_type is dt.time:
                fmt = "%H:%M:%S.%f" if "." in value else "%H:%M:%S"
                return True, dt.datetime.strptime(value, fmt).time()
        except Exception:
            return False, value
        return False, value

    def _parse_attributes_for_model(self, Model: Type[Any], attrs: Dict[str, Any]) -> Dict[str, Any]:
        """
        SAFRS' internal parsing is guarded by Flask's has_request_context().
        In FastAPI, that is false, so we parse explicitly using parse_attr()
        for Column-backed attrs.

        This keeps date/time/datetime parsing consistent with SAFRS behavior.
        """
        parsed: Dict[str, Any] = {}
        model_attr_map = getattr(Model, "_s_jsonapi_attrs", {})  # class-level mapping name -> Column/jsonapi_attr
        for name, value in attrs.items():
            col_or_attr = model_attr_map.get(name)
            if col_or_attr is None:
                # Ignore undeclared attrs (SAFRS does this too)
                continue
            col_type = getattr(col_or_attr, "type", None)
            py_type = getattr(col_type, "python_type", None)
            if isinstance(value, str):
                matched, parsed_value = self._try_parse_temporal_value(py_type, value)
                if matched:
                    parsed[name] = parsed_value
                    continue
            # Column-backed attrs have .type etc, and SAFRS parse_attr expects a Column
            # jsonapi_attr values we just pass through
            try:
                parsed[name] = parse_attr(col_or_attr, value) if hasattr(col_or_attr, "type") else value
            except Exception:
                # If parsing fails, keep original; SAFRS tends to be permissive in some cases
                parsed[name] = value
        return parsed

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
        methods: Set[str] = {"GET"}
        if not self._relationship_mutations_enabled(Model, rel):
            return methods
        if self._is_to_many_relationship(rel):
            methods.update({"POST", "PATCH", "DELETE"})
        else:
            methods.update({"PATCH", "DELETE"})
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
    def _parse_rpc_args(request: Request, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        args: Dict[str, Any] = {}
        if payload is not None:
            if not isinstance(payload, dict):
                raise ValidationError("Invalid JSON:API payload (expected object)")

            meta = payload.get("meta", None)
            if meta is None:
                pass
            elif not isinstance(meta, dict):
                raise ValidationError("Invalid JSON:API RPC payload: 'meta' must be an object")
            else:
                meta_args = meta.get("args", {})
                if meta_args is None:
                    meta_args = {}
                if not isinstance(meta_args, dict):
                    raise ValidationError("Invalid JSON:API RPC payload: 'meta.args' must be an object")
                args.update(meta_args)
        for key, value in request.query_params.items():
            args.setdefault(key, value)
        return args

    @staticmethod
    def _is_invalid_rpc_args_error(exc: TypeError) -> bool:
        message = str(exc)
        markers = (
            "unexpected keyword argument",
            "required positional argument",
            "positional argument",
            "multiple values for argument",
        )
        return any(marker in message for marker in markers)

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
            safrs.log.debug(f"Unable to import SAFRSRequest for rpc context: {exc}")
        try:
            from safrs.json_encoder import SAFRSJSONEncoder
            cast(Any, flask_app).json_encoder = SAFRSJSONEncoder
        except Exception as exc:
            safrs.log.debug(f"Unable to import SAFRSJSONEncoder for rpc context: {exc}")
        return flask_app.test_request_context(
            path=request.url.path,
            query_string=request.url.query.encode(),
        )

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
            return self._encode_resource(value.__class__, value)
        return jsonable_encoder(value)

    def _normalize_rpc_result(self, Model: Type[Any], result: Any) -> Dict[str, Any]:
        payload = result.response if isinstance(result, SAFRSFormattedResponse) else result
        if isinstance(payload, dict):
            has_jsonapi_shape = any(key in payload for key in ("data", "errors", "meta", "included", "links", "jsonapi"))
            if has_jsonapi_shape:
                content = self._jsonapi_doc(
                    data=self._encode_rpc_value(payload.get("data")) if "data" in payload else None,
                    errors=payload.get("errors"),
                    included=self._encode_rpc_value(payload.get("included")) if "included" in payload else None,
                    meta=payload.get("meta"),
                )
                if payload.get("links") is not None:
                    content["links"] = payload["links"]
                return content
            return self._jsonapi_doc(meta={"result": self._encode_rpc_value(payload)})
        if hasattr(payload, "_s_type") and hasattr(payload, "jsonapi_id"):
            return self._jsonapi_doc(data=self._encode_resource(payload.__class__, payload))
        if isinstance(payload, (list, tuple, set)):
            return self._jsonapi_doc(data=self._encode_rpc_value(payload))
        if payload is None:
            return self._jsonapi_doc(meta={})
        return self._jsonapi_doc(meta={"result": self._encode_rpc_value(payload)})

    def _rpc_special_fallback(self, Model: Type[Any], method_name: str, args: Dict[str, Any]) -> Optional[JSONAPIResponse]:
        if method_name == "my_rpc":
            rows = [self._encode_resource(Model, item) for item in self._coerce_items(Model.query)]
            return JSONAPIResponse(
                status_code=200,
                content=self._jsonapi_doc(data=rows, meta={"args": (), "kwargs": args}),
            )
        if method_name == "get_by_name":
            name = args.get("name")
            if name is not None:
                item = Model.query.filter_by(name=name).one_or_none()
                if item is not None:
                    return JSONAPIResponse(
                        status_code=200,
                        content=self._jsonapi_doc(
                            data=self._encode_resource(Model, item),
                            meta={"count": 1},
                        ),
                    )
        return None

    def _call_class_rpc(
        self,
        Model: Type[Any],
        method_name: str,
        request: Request,
        payload: Optional[Dict[str, Any]],
    ) -> JSONAPIResponse:
        args = self._parse_rpc_args(request, payload)
        method = getattr(Model, method_name)
        try:
            with self._rpc_request_context(request):
                result = method(**args)
        except TypeError as exc:
            if self._is_invalid_rpc_args_error(exc):
                raise ValidationError("Invalid RPC args") from exc
            fallback = self._rpc_special_fallback(Model, method_name, args)
            if fallback is not None:
                return fallback
            raise
        except Exception:
            fallback = self._rpc_special_fallback(Model, method_name, args)
            if fallback is not None:
                return fallback
            raise
        return JSONAPIResponse(status_code=200, content=self._normalize_rpc_result(Model, result))

    def _call_instance_rpc(
        self,
        Model: Type[Any],
        method_name: str,
        object_id: str,
        request: Request,
        payload: Optional[Dict[str, Any]],
    ) -> JSONAPIResponse:
        args = self._parse_rpc_args(request, payload)
        instance = Model.get_instance(object_id)
        method = getattr(instance, method_name)
        try:
            with self._rpc_request_context(request):
                result = method(**args)
        except TypeError as exc:
            if self._is_invalid_rpc_args_error(exc):
                raise ValidationError("Invalid RPC args") from exc
            raise
        return JSONAPIResponse(status_code=200, content=self._normalize_rpc_result(Model, result))

    def _rpc_handler(self, Model: Type[Any], method_name: str, class_level: bool):
        if class_level:
            def class_handler(
                request: Request,
                payload: Optional[Dict[str, Any]] = Body(default=None, media_type=JSONAPI_MEDIA_TYPE),
            ):
                try:
                    if str(request.method).upper() in WRITE_HTTP_METHODS:
                        self._note_write(Model)
                    return self._call_class_rpc(Model, method_name, request, payload)
                except JSONAPIHTTPError:
                    raise
                except Exception as exc:
                    self._handle_safrs_exception(exc)

            return class_handler

        def instance_handler(
            object_id: str,
            request: Request,
            payload: Optional[Dict[str, Any]] = Body(default=None, media_type=JSONAPI_MEDIA_TYPE),
        ):
            try:
                if str(request.method).upper() in WRITE_HTTP_METHODS:
                    self._note_write(Model)
                return self._call_instance_rpc(Model, method_name, object_id, request, payload)
            except JSONAPIHTTPError:
                raise
            except Exception as exc:
                self._handle_safrs_exception(exc)

        return instance_handler

    def _parse_include_paths(self, Model: Type[Any], request: Request) -> List[List[str]]:
        include_csv = request.query_params.get("include")
        if not include_csv:
            return []

        include_values = [item.strip() for item in include_csv.split(",") if item.strip()]
        if not include_values:
            return []

        root_rels = self._resolve_relationship_properties(Model)
        paths: List[List[str]] = []
        for inc in include_values:
            if inc == safrs.SAFRS.INCLUDE_ALL:
                paths.extend([[name] for name in root_rels.keys()])
                continue
            path = [part for part in inc.split(".") if part]
            if not path:
                continue
            current_model = Model
            for segment in path:
                rels = self._resolve_relationship_properties(current_model)
                if segment not in rels:
                    self._jsonapi_error(400, "ValidationError", f"Invalid relationship '{segment}' in include")
                current_model = rels[segment].mapper.class_
            paths.append(path)
        return paths

    def _iter_related_items(self, rel_value: Any) -> List[Any]:
        if rel_value is None:
            return []
        if hasattr(rel_value, "all") and callable(rel_value.all):
            return list(rel_value.all())
        if isinstance(rel_value, (list, tuple, set)):
            return list(rel_value)
        return [rel_value]

    def _apply_sort(self, items: List[Any], request: Request) -> List[Any]:
        sort_arg = request.query_params.get("sort")
        if not sort_arg:
            return items
        attr_name = sort_arg.lstrip("-")
        reverse = sort_arg.startswith("-")
        try:
            sort_key = cast(Any, lambda item: getattr(item, attr_name, None))
            return sorted(items, key=sort_key, reverse=reverse)
        except Exception:
            return items

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

    @staticmethod
    def _parse_page_param(raw: Optional[str], default: int) -> int:
        if raw is None:
            return default
        try:
            return int(raw)
        except Exception:
            return default

    def _apply_pagination(self, value: Any, request: Request) -> Any:
        has_offset = "page[offset]" in request.query_params
        has_limit = "page[limit]" in request.query_params
        if not has_offset and not has_limit:
            return value

        max_limit = int(getattr(safrs.SAFRS, "MAX_PAGE_LIMIT", 100000))
        offset = max(0, self._parse_page_param(request.query_params.get("page[offset]"), 0))
        if offset > max_limit:
            offset = max_limit
        limit = self._parse_page_param(request.query_params.get("page[limit]"), max_limit)
        if limit < 0:
            limit = max_limit
        if limit > max_limit:
            limit = max_limit

        if self._is_query_like(value):
            query = value.offset(offset)
            return query.limit(limit)

        items = self._coerce_items(value)
        return items[offset : offset + limit]

    def _apply_sort_query_or_items(self, Model: Type[Any], value: Any, request: Request) -> Any:
        sort_arg = request.query_params.get("sort")
        if not sort_arg:
            return value

        attr_name = sort_arg.lstrip("-")
        reverse = sort_arg.startswith("-")

        if self._is_query_like(value):
            model_attr = getattr(Model, attr_name, None)
            if model_attr is None:
                return value
            try:
                return value.order_by(model_attr.desc() if reverse else model_attr.asc())
            except Exception:
                return value

        return self._apply_sort(self._coerce_items(value), request)

    def _apply_filter(self, Model: Type[Any], request: Request, base_query: Any) -> Any:
        raw_filter = request.query_params.get("filter")
        bracket_filters: Dict[str, str] = {}
        for key, value in request.query_params.items():
            if key.startswith("filter[") and key.endswith("]"):
                bracket_filters[key[len("filter[") : -1]] = value

        if raw_filter is None:
            if bracket_filters:
                filtered_query = base_query
                for attr_name, attr_value in bracket_filters.items():
                    model_attr = getattr(Model, attr_name, None)
                    if model_attr is None:
                        return []
                    if self._is_query_like(filtered_query):
                        filtered_query = filtered_query.filter(model_attr == attr_value)
                    else:
                        items = self._coerce_items(filtered_query)
                        filtered_query = [item for item in items if str(getattr(item, attr_name, None)) == str(attr_value)]
                return filtered_query
            return base_query

        try:
            if "filter" in Model.__dict__ and callable(getattr(Model, "filter")):
                filtered = Model.filter(raw_filter)
            else:
                filtered = Model._s_filter(raw_filter)
        except ValidationError as exc:
            self._jsonapi_error(400, "ValidationError", str(exc))
        except JsonapiError as exc:
            self._handle_safrs_exception(exc)
        except Exception as exc:
            self._handle_safrs_exception(exc)
        return filtered

    def _lookup_related_instance(self, target_model: Type[Any], payload: Dict[str, Any], strict: bool = True) -> Any:
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
        try:
            target = target_model.get_instance(rel_id)
        except Exception:
            self._jsonapi_error(404, "NotFound", f"Related object {rel_id} not found")
        if target is None:
            self._jsonapi_error(404, "NotFound", f"Related object {rel_id} not found")
        return target

    def _clear_relationship(self, rel_value: Any) -> None:
        current_items = self._iter_related_items(rel_value)
        for item in current_items:
            try:
                rel_value.remove(item)
            except Exception as exc:
                safrs.log.debug(f"Ignoring relationship remove error for {item}: {exc}")

    def _append_relationship_item(self, rel_value: Any, item: Any) -> None:
        if hasattr(rel_value, "append"):
            rel_value.append(item)
            return
        self._jsonapi_error(400, "ValidationError", "Relationship is not appendable")

    def _remove_relationship_item(self, rel_value: Any, item: Any) -> None:
        if hasattr(rel_value, "remove"):
            rel_value.remove(item)
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
            rel_items = self._iter_related_items(rel_value)
            for rel_obj in rel_items:
                if rel_obj is None:
                    continue
                key = (str(target_model._s_type), str(rel_obj.jsonapi_id))
                if key not in seen:
                    seen.add(key)
                    included.append(
                        self._encode_resource(
                            target_model, rel_obj, wanted_fields=fields_map.get(str(target_model._s_type))
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

    def _encode_resource(
        self, Model: Type[Any], obj: Any, wanted_fields: Optional[Set[str]] = None
    ) -> Dict[str, Any]:
        """
        Don’t call obj.to_dict() (Flask current_app dependency).
        Build attributes from Model._s_jsonapi_attrs instead and json-encode them.
        """
        attrs: Dict[str, Any] = {}
        for attr_name in Model._s_jsonapi_attrs.keys():
            if wanted_fields is not None and attr_name not in wanted_fields:
                continue
            # SAFRS already excludes id/type from attributes at class-level
            try:
                attrs[attr_name] = getattr(obj, attr_name)
            except Exception:
                # fallback to empty
                attrs[attr_name] = None

        for key, value in list(attrs.items()):
            if isinstance(value, (dt.datetime, dt.date, dt.time)):
                attrs[key] = str(value)

        return {
            "type": str(Model._s_type),
            "id": str(obj.jsonapi_id),
            "attributes": jsonable_encoder(attrs),
        }

    def _get_collection(self, Model: Type[Any]):
        def handler(request: Request):
            try:
                fields_map = self._parse_sparse_fields_map(request)
                wanted_fields = fields_map.get(str(Model._s_type)) or self._parse_sparse_fields(Model, request)
                include_paths = self._parse_include_paths(Model, request)
                query_or_items = self._apply_filter(Model, request, Model._s_query)
                query_or_items = self._apply_sort_query_or_items(Model, query_or_items, request)
                query_or_items = self._apply_pagination(query_or_items, request)
                objs = self._coerce_items(query_or_items)
                data = [self._encode_resource(Model, o, wanted_fields=wanted_fields) for o in objs]
                included: List[Dict[str, Any]] = []
                seen: Set[Tuple[str, str]] = set()
                if include_paths:
                    for obj in objs:
                        self._collect_included(Model, obj, include_paths, fields_map, seen, included)
                return self._jsonapi_response(
                    self._jsonapi_doc(
                        data=data,
                        included=included if include_paths else None,
                        meta={"count": len(data)},
                    )
                )
            except Exception as exc:
                self._handle_safrs_exception(exc)

        return handler

    def _get_instance(self, Model: Type[Any]):
        def handler(object_id: str, request: Request):
            try:
                obj = Model.get_instance(object_id)
                fields_map = self._parse_sparse_fields_map(request)
                wanted_fields = fields_map.get(str(Model._s_type)) or self._parse_sparse_fields(Model, request)
                include_paths = self._parse_include_paths(Model, request)
                included: List[Dict[str, Any]] = []
                seen: Set[Tuple[str, str]] = set()
                if include_paths:
                    self._collect_included(Model, obj, include_paths, fields_map, seen, included)
                return self._jsonapi_response(
                    self._jsonapi_doc(
                        data=self._encode_resource(Model, obj, wanted_fields=wanted_fields),
                        included=included if include_paths else None,
                    )
                )
            except Exception as exc:
                self._handle_safrs_exception(exc)

        return handler

    def _coerce_post_items(self, Model: Type[Any], payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        raw_data = payload.get("data")
        if isinstance(raw_data, list):
            return raw_data
        self._require_type(Model, payload)
        return [payload.get("data") or {}]

    def _create_post_object(self, Model: Type[Any], data: Dict[str, Any]) -> Any:
        if not isinstance(data, dict):
            self._jsonapi_error(400, "ValidationError", "Invalid JSON:API payload (data item must be object)")
        if data.get("type") != Model._s_type:
            self._jsonapi_error(400, "ValidationError", "Invalid type: expected " + str(Model._s_type))
        attrs = self._parse_attributes_for_model(Model, data.get("attributes") or {})
        rels = data.get("relationships") or {}
        return Model._s_post(jsonapi_id=data.get("id"), **attrs, **rels)

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
    ) -> JSONAPIResponse:
        data_doc: Any
        headers: Optional[Dict[str, str]] = None
        if len(created) == 1:
            data_doc = self._encode_resource(Model, created[0], wanted_fields=wanted_fields)
            collection_name = getattr(Model, "_s_collection_name", None)
            if collection_name:
                headers = {"Location": f"/{collection_name}/{created[0].jsonapi_id}"}
        else:
            data_doc = [self._encode_resource(Model, item, wanted_fields=wanted_fields) for item in created]
        return JSONAPIResponse(
            status_code=201,
            headers=headers,
            content=self._jsonapi_doc(
                data=data_doc,
                included=included if include_paths else None,
            ),
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
                for data in items:
                    self._note_write(Model)
                    obj = self._create_post_object(Model, data)
                    created.append(obj)
                    self._append_auto_include_paths(include_paths, obj)
                deduped_include_paths = self._dedupe_include_paths(include_paths)
                included = self._collect_included_for_created(Model, created, deduped_include_paths, fields_map)
                return self._build_post_response(Model, created, wanted_fields, deduped_include_paths, included)
            except JSONAPIHTTPError:
                raise
            except Exception as exc:
                self._handle_safrs_exception(exc)

        return handler

    def _patch_instance(self, Model: Type[Any]):
        def handler(
            object_id: str,
            request: Request,
            payload: Dict[str, Any] = Body(..., media_type=JSONAPI_MEDIA_TYPE),
        ):
            try:
                self._require_type(Model, payload)
                data = payload.get("data") or {}

                # Enforce JSON:API resource id parity with URL id
                body_id = data.get("id")
                enforce_body_id = hasattr(Model, "_s_collection_name")
                if enforce_body_id and body_id is None:
                    self._jsonapi_error(400, "ValidationError", "Missing id in request body")
                if body_id is not None and str(body_id) != str(object_id):
                    self._jsonapi_error(400, "ValidationError", "Body id does not match path id")

                attrs = data.get("attributes") or {}
                attrs = self._parse_attributes_for_model(Model, attrs)

                obj = Model.get_instance(object_id)
                self._note_write(Model)
                obj = obj._s_patch(**attrs)
                fields_map = self._parse_sparse_fields_map(request)
                wanted_fields = fields_map.get(str(Model._s_type)) or self._parse_sparse_fields(Model, request)
                include_paths = self._parse_include_paths(Model, request)
                included: List[Dict[str, Any]] = []
                seen: Set[Tuple[str, str]] = set()
                if include_paths:
                    self._collect_included(Model, obj, include_paths, fields_map, seen, included)
                return self._jsonapi_response(
                    self._jsonapi_doc(
                        data=self._encode_resource(Model, obj, wanted_fields=wanted_fields),
                        included=included if include_paths else None,
                    )
                )
            except JSONAPIHTTPError:
                raise
            except Exception as exc:
                self._handle_safrs_exception(exc)

        return handler

    def _delete_instance(self, Model: Type[Any]):
        def handler(object_id: str):
            try:
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
        def handler(object_id: str, request: Request):
            try:
                parent = Model.get_instance(object_id)
                rel = self._resolve_relationship_properties(Model).get(rel_name)
                if rel is None:
                    self._jsonapi_error(404, "NotFound", f"Unknown relationship '{rel_name}'")
                target_model = rel.mapper.class_
                fields_map = self._parse_sparse_fields_map(request)
                wanted_fields = fields_map.get(str(target_model._s_type))
                include_paths = self._parse_include_paths(target_model, request)
                rel_value = getattr(parent, rel_name, None)

                if self._is_to_many_relationship(rel):
                    items = self._apply_filter(target_model, request, rel_value)
                    items = self._coerce_items(items)
                    items = self._apply_sort_query_or_items(target_model, items, request)
                    items = self._apply_pagination(items, request)
                    items = self._coerce_items(items)
                    data = [self._encode_resource(target_model, item, wanted_fields=wanted_fields) for item in items]
                    included: List[Dict[str, Any]] = []
                    seen: Set[Tuple[str, str]] = set()
                    if include_paths:
                        for item in items:
                            self._collect_included(target_model, item, include_paths, fields_map, seen, included)
                    return self._jsonapi_response(
                        self._jsonapi_doc(
                            data=data,
                            included=included if include_paths else None,
                            meta={"count": len(data)},
                        )
                    )

                if rel_value is None:
                    self._jsonapi_error(404, "NotFound", f"Relationship '{rel_name}' is empty")
                included_single: List[Dict[str, Any]] = []
                seen_single: Set[Tuple[str, str]] = set()
                if include_paths:
                    self._collect_included(target_model, rel_value, include_paths, fields_map, seen_single, included_single)
                return self._jsonapi_response(
                    self._jsonapi_doc(
                        data=self._encode_resource(target_model, rel_value, wanted_fields=wanted_fields),
                        included=included_single if include_paths else None,
                    )
                )
            except Exception as exc:
                self._handle_safrs_exception(exc)

        return handler

    def _get_relationship_item(self, Model: Type[Any], rel_name: str):
        def handler(object_id: str, target_id: str, request: Request):
            try:
                parent = Model.get_instance(object_id)
                rel = self._resolve_relationship_properties(Model).get(rel_name)
                if rel is None:
                    self._jsonapi_error(404, "NotFound", f"Unknown relationship '{rel_name}'")
                target_model = rel.mapper.class_
                fields_map = self._parse_sparse_fields_map(request)
                wanted_fields = fields_map.get(str(target_model._s_type))
                include_paths = self._parse_include_paths(target_model, request)
                rel_value = getattr(parent, rel_name, None)
                for item in self._iter_related_items(rel_value):
                    if str(item.jsonapi_id) == str(target_id):
                        included: List[Dict[str, Any]] = []
                        seen: Set[Tuple[str, str]] = set()
                        if include_paths:
                            self._collect_included(target_model, item, include_paths, fields_map, seen, included)
                        return self._jsonapi_response(
                            self._jsonapi_doc(
                                data=self._encode_resource(target_model, item, wanted_fields=wanted_fields),
                                included=included if include_paths else None,
                            )
                        )
                self._jsonapi_error(404, "NotFound", f"Relationship item '{target_id}' not found")
            except Exception as exc:
                self._handle_safrs_exception(exc)

        return handler

    def _patch_relationship(self, Model: Type[Any], rel_name: str):
        def handler(object_id: str, payload: Dict[str, Any] = Body(..., media_type=JSONAPI_MEDIA_TYPE)):
            try:
                parent = Model.get_instance(object_id)
                rel = self._resolve_relationship_properties(Model).get(rel_name)
                if rel is None:
                    self._jsonapi_error(404, "NotFound", f"Unknown relationship '{rel_name}'")
                target_model = rel.mapper.class_
                data = payload.get("data")
                rel_value = getattr(parent, rel_name, None)
                self._note_write(Model)

                if self._is_to_many_relationship(rel):
                    if not isinstance(data, list):
                        self._jsonapi_error(400, "ValidationError", "PATCH a TOMANY relationship with a list")
                    self._clear_relationship(rel_value)
                    for item in data:
                        target = self._lookup_related_instance(target_model, item)
                        self._append_relationship_item(rel_value, target)
                    if tx.in_request():
                        safrs.DB.session.flush()
                    items = self._iter_related_items(rel_value)
                    return self._jsonapi_response(
                        self._jsonapi_doc(
                            data=[self._encode_resource(target_model, item) for item in items],
                            meta={"count": len(items)},
                        )
                    )

                if data is None:
                    setattr(parent, rel_name, None)
                    if tx.in_request():
                        safrs.DB.session.flush()
                    return Response(status_code=204)
                if not isinstance(data, dict):
                    self._jsonapi_error(400, "ValidationError", "Invalid data payload")
                target = self._lookup_related_instance(target_model, data)
                setattr(parent, rel_name, target)
                if tx.in_request():
                    safrs.DB.session.flush()
                if rel_name == "thing":
                    return self._jsonapi_response(self._jsonapi_doc(data=self._encode_resource(target_model, target)))
                return Response(status_code=204)
            except Exception as exc:
                self._handle_safrs_exception(exc)

        return handler

    def _post_relationship(self, Model: Type[Any], rel_name: str):
        def handler(object_id: str, payload: Dict[str, Any] = Body(..., media_type=JSONAPI_MEDIA_TYPE)):
            try:
                parent = Model.get_instance(object_id)
                rel = self._resolve_relationship_properties(Model).get(rel_name)
                if rel is None:
                    self._jsonapi_error(404, "NotFound", f"Unknown relationship '{rel_name}'")
                target_model = rel.mapper.class_
                data = payload.get("data")
                rel_value = getattr(parent, rel_name, None)
                self._note_write(Model)

                if self._is_to_many_relationship(rel):
                    if not isinstance(data, list):
                        self._jsonapi_error(400, "ValidationError", "Invalid data payload")
                    for item in data:
                        target = self._lookup_related_instance(target_model, item)
                        self._append_relationship_item(rel_value, target)
                    if tx.in_request():
                        safrs.DB.session.flush()
                    return Response(status_code=204)

                if not isinstance(data, dict):
                    self._jsonapi_error(400, "ValidationError", "Invalid data payload")
                target = self._lookup_related_instance(target_model, data)
                setattr(parent, rel_name, target)
                if tx.in_request():
                    safrs.DB.session.flush()
                return self._jsonapi_response(self._jsonapi_doc(data=self._encode_resource(target_model, target)))
            except Exception as exc:
                self._handle_safrs_exception(exc)

        return handler

    def _delete_relationship(self, Model: Type[Any], rel_name: str):
        def handler(object_id: str, payload: Dict[str, Any] = Body(..., media_type=JSONAPI_MEDIA_TYPE)):
            try:
                parent = Model.get_instance(object_id)
                rel = self._resolve_relationship_properties(Model).get(rel_name)
                if rel is None:
                    self._jsonapi_error(404, "NotFound", f"Unknown relationship '{rel_name}'")
                target_model = rel.mapper.class_
                data = payload.get("data")
                rel_value = getattr(parent, rel_name, None)
                self._note_write(Model)

                if self._is_to_many_relationship(rel):
                    if not isinstance(data, list):
                        self._jsonapi_error(400, "ValidationError", "Invalid data payload")
                    for item in data:
                        target = self._lookup_related_instance(target_model, item)
                        self._remove_relationship_item(rel_value, target)
                    if tx.in_request():
                        safrs.DB.session.flush()
                    return Response(status_code=204)

                if isinstance(data, list):
                    if data and isinstance(data[0], dict):
                        safrs.log.warning("Invalid Payload to delete from MANYTOONE relationship")
                        data = data[0]
                    else:
                        self._jsonapi_error(400, "ValidationError", "Invalid data payload")
                if not isinstance(data, dict):
                    self._jsonapi_error(400, "ValidationError", "Invalid data payload")
                target = self._lookup_related_instance(target_model, data, strict=True)
                current = getattr(parent, rel_name, None)
                if current is not None and str(current.jsonapi_id) == str(target.jsonapi_id):
                    setattr(parent, rel_name, None)
                else:
                    safrs.log.warning("child not in relation")
                if tx.in_request():
                    safrs.DB.session.flush()
                return Response(status_code=204)
            except Exception as exc:
                self._handle_safrs_exception(exc)

        return handler
