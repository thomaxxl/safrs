# -*- coding: utf-8 -*-

from typing import Any, Dict, List, Optional, Set, Tuple, Type

import safrs
from safrs.attr_parse import parse_attr
from safrs.errors import GenericError, JsonapiError, SystemValidationError, ValidationError
from safrs.json_encoder import SAFRSFormattedResponse
from safrs.swagger_doc import get_doc, get_http_methods

from fastapi import APIRouter, Body, Depends as FastAPIDepends, FastAPI, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.params import Depends as DependsParam

from .responses import JSONAPIResponse

JSONAPI_MEDIA_TYPE = "application/vnd.api+json"


class JSONAPIHTTPError(Exception):
    def __init__(self, status_code: int, payload: Dict[str, Any]) -> None:
        self.status_code = status_code
        self.payload = payload


def install_jsonapi_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(JSONAPIHTTPError)
    async def _jsonapi_http_error_handler(_request: Request, exc: JSONAPIHTTPError):
        return JSONAPIResponse(status_code=exc.status_code, content=exc.payload)


class SafrsFastAPI:
    def __init__(self, app: FastAPI, prefix: str = "", dependencies: Optional[List[Any]] = None) -> None:
        self.app = app
        self.prefix = prefix
        self.default_dependencies = self._normalize_dependencies(dependencies)
        install_jsonapi_exception_handlers(app)
        self._install_swagger_alias()

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
                model_method = Model.__dict__.get(method_name, None)
                class_level = isinstance(model_method, (classmethod, staticmethod)) or getattr(api_method, "__self__", None) is Model
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
        tag = str(Model._s_collection_name)

        # IMPORTANT: build router with routes first, then include_router()
        router = APIRouter(prefix=self.prefix, tags=[tag])

        collection_path = "/" + str(Model._s_collection_name)
        instance_path = collection_path + "/{object_id}"

        for idx, path in enumerate(self._with_slash_parity(collection_path)):
            router.add_api_route(
                path,
                self._get_collection(Model),
                methods=["GET"],
                response_class=JSONAPIResponse,
                summary=f"List {tag}",
                dependencies=route_dependencies,
                operation_id=f"get_{tag}_collection" if idx == 0 else None,
                include_in_schema=(idx == 0),
            )
        for idx, path in enumerate(self._with_slash_parity(instance_path)):
            router.add_api_route(
                path,
                self._get_instance(Model),
                methods=["GET"],
                response_class=JSONAPIResponse,
                summary=f"Get {tag} by id",
                dependencies=route_dependencies,
                operation_id=f"get_{tag}_instance" if idx == 0 else None,
                include_in_schema=(idx == 0),
            )
        for idx, path in enumerate(self._with_slash_parity(collection_path)):
            router.add_api_route(
                path,
                self._post_collection(Model),
                methods=["POST"],
                response_class=JSONAPIResponse,
                summary=f"Create {tag}",
                dependencies=route_dependencies,
                operation_id=f"post_{tag}_collection" if idx == 0 else None,
                include_in_schema=(idx == 0),
            )
        for idx, path in enumerate(self._with_slash_parity(instance_path)):
            router.add_api_route(
                path,
                self._patch_instance(Model),
                methods=["PATCH"],
                response_class=JSONAPIResponse,
                summary=f"Update {tag}",
                dependencies=route_dependencies,
                operation_id=f"patch_{tag}_instance" if idx == 0 else None,
                include_in_schema=(idx == 0),
            )
        for idx, path in enumerate(self._with_slash_parity(instance_path)):
            router.add_api_route(
                path,
                self._delete_instance(Model),
                methods=["DELETE"],
                response_class=JSONAPIResponse,
                summary=f"Delete {tag}",
                dependencies=route_dependencies,
                operation_id=f"delete_{tag}_instance" if idx == 0 else None,
                include_in_schema=(idx == 0),
            )

        for method_name, class_level, rpc_methods in self._discover_rpc_methods(Model):
            rpc_path = f"{collection_path}/{method_name}" if class_level else f"{instance_path}/{method_name}"
            rpc_operation = f"{'class' if class_level else 'instance'}_{tag}_{method_name}_rpc"
            for idx, path in enumerate(self._with_slash_parity(rpc_path)):
                router.add_api_route(
                    path,
                    self._rpc_handler(Model, method_name, class_level),
                    methods=rpc_methods,
                    response_class=JSONAPIResponse,
                    summary=f"RPC {tag}.{method_name}",
                    dependencies=route_dependencies,
                    operation_id=rpc_operation if idx == 0 else None,
                    include_in_schema=(idx == 0),
                )

        relationships = self._resolve_relationships(Model)
        if relationships:
            for rel_name in relationships.keys():
                rel_path = f"{instance_path}/{rel_name}"
                rel_item_path = f"{rel_path}/{{target_id}}"

                for idx, path in enumerate(self._with_slash_parity(rel_path)):
                    router.add_api_route(
                        path,
                        self._get_relationship(Model, rel_name),
                        methods=["GET"],
                        response_class=JSONAPIResponse,
                        summary=f"Get relationship {tag}.{rel_name}",
                        dependencies=route_dependencies,
                        operation_id=f"get_{tag}_{rel_name}_relationship" if idx == 0 else None,
                        include_in_schema=(idx == 0),
                    )
                for idx, path in enumerate(self._with_slash_parity(rel_item_path)):
                    router.add_api_route(
                        path,
                        self._get_relationship_item(Model, rel_name),
                        methods=["GET"],
                        response_class=JSONAPIResponse,
                        summary=f"Get relationship item {tag}.{rel_name}",
                        dependencies=route_dependencies,
                        operation_id=f"get_{tag}_{rel_name}_relationship_item" if idx == 0 else None,
                        include_in_schema=(idx == 0),
                    )
                for idx, path in enumerate(self._with_slash_parity(rel_path)):
                    router.add_api_route(
                        path,
                        self._patch_relationship(Model, rel_name),
                        methods=["PATCH"],
                        response_class=JSONAPIResponse,
                        summary=f"Patch relationship {tag}.{rel_name}",
                        dependencies=route_dependencies,
                        operation_id=f"patch_{tag}_{rel_name}_relationship" if idx == 0 else None,
                        include_in_schema=(idx == 0),
                    )
                for idx, path in enumerate(self._with_slash_parity(rel_path)):
                    router.add_api_route(
                        path,
                        self._post_relationship(Model, rel_name),
                        methods=["POST"],
                        response_class=JSONAPIResponse,
                        summary=f"Post relationship {tag}.{rel_name}",
                        dependencies=route_dependencies,
                        operation_id=f"post_{tag}_{rel_name}_relationship" if idx == 0 else None,
                        include_in_schema=(idx == 0),
                    )
                for idx, path in enumerate(self._with_slash_parity(rel_path)):
                    router.add_api_route(
                        path,
                        self._delete_relationship(Model, rel_name),
                        methods=["DELETE"],
                        response_class=JSONAPIResponse,
                        summary=f"Delete relationship {tag}.{rel_name}",
                        dependencies=route_dependencies,
                        operation_id=f"delete_{tag}_{rel_name}_relationship" if idx == 0 else None,
                        include_in_schema=(idx == 0),
                    )

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
        if included:
            doc["included"] = included
        if meta is not None:
            doc["meta"] = meta
        return doc

    def _jsonapi_error(self, status_code: int, title: str, detail: str) -> None:
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
        typ = data.get("type")
        if typ != Model._s_type:
            self._jsonapi_error(400, "ValidationError", "Invalid type: expected " + str(Model._s_type))

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
        rels = getattr(Model, "_s_relationships", None)
        if isinstance(rels, dict):
            return rels
        mapper = getattr(Model, "__mapper__", None)
        if mapper is None:
            return {}
        return {rel.key: rel for rel in mapper.relationships}

    @staticmethod
    def _parse_rpc_args(request: Request, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        args: Dict[str, Any] = {}
        if isinstance(payload, dict):
            meta = payload.get("meta")
            if isinstance(meta, dict):
                meta_args = meta.get("args")
                if isinstance(meta_args, dict):
                    args.update(meta_args)
        for key, value in request.query_params.items():
            args.setdefault(key, value)
        return args

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

    def _rpc_handler(self, Model: Type[Any], method_name: str, class_level: bool):
        if class_level:
            def handler(
                request: Request,
                payload: Optional[Dict[str, Any]] = Body(default=None, media_type=JSONAPI_MEDIA_TYPE),
            ):
                try:
                    args = self._parse_rpc_args(request, payload)
                    method = getattr(Model, method_name)
                    result = method(**args)
                    return JSONAPIResponse(status_code=200, content=self._normalize_rpc_result(Model, result))
                except JSONAPIHTTPError:
                    raise
                except Exception as exc:
                    self._handle_safrs_exception(exc)

            return handler

        def handler(
            object_id: str,
            request: Request,
            payload: Optional[Dict[str, Any]] = Body(default=None, media_type=JSONAPI_MEDIA_TYPE),
        ):
            try:
                args = self._parse_rpc_args(request, payload)
                instance = Model.get_instance(object_id)
                method = getattr(instance, method_name)
                result = method(**args)
                return JSONAPIResponse(status_code=200, content=self._normalize_rpc_result(Model, result))
            except JSONAPIHTTPError:
                raise
            except Exception as exc:
                self._handle_safrs_exception(exc)

        return handler

    def _parse_include_paths(self, Model: Type[Any], request: Request) -> List[List[str]]:
        include_csv = request.query_params.get("include")
        if not include_csv:
            return []

        include_values = [item.strip() for item in include_csv.split(",") if item.strip()]
        if not include_values:
            return []

        root_rels = self._resolve_relationships(Model)
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
                rels = self._resolve_relationships(current_model)
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
            return sorted(items, key=lambda item: getattr(item, attr_name, None), reverse=reverse)
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
        if raw_filter is None:
            # Keep SAFRS-style permissive behavior for query args like filter[invalid]=...
            if any(key.startswith("filter[") for key in request.query_params.keys()):
                return []
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
            except Exception:
                pass

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
            rels = self._resolve_relationships(current_model)
            rel = rels.get(rel_name)
            if rel is None:
                continue
            target_model = rel.mapper.class_
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
                return self._jsonapi_doc(data=data, included=included if included else None)
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
                return self._jsonapi_doc(
                    data=self._encode_resource(Model, obj, wanted_fields=wanted_fields),
                    included=included if included else None,
                )
            except Exception as exc:
                self._handle_safrs_exception(exc)

        return handler

    def _post_collection(self, Model: Type[Any]):
        def handler(
            request: Request,
            payload: Dict[str, Any] = Body(..., media_type=JSONAPI_MEDIA_TYPE)
        ):
            try:
                self._require_type(Model, payload)
                data = payload.get("data") or {}
                attrs = data.get("attributes") or {}
                attrs = self._parse_attributes_for_model(Model, attrs)
                rels = data.get("relationships") or {}

                obj = Model._s_post(jsonapi_id=data.get("id"), **attrs, **rels)
                fields_map = self._parse_sparse_fields_map(request)
                wanted_fields = fields_map.get(str(Model._s_type)) or self._parse_sparse_fields(Model, request)
                include_paths = self._parse_include_paths(Model, request)
                auto_include = getattr(obj, "included_list", None) or []
                for include_item in auto_include:
                    if not isinstance(include_item, str) or not include_item:
                        continue
                    path = [segment for segment in include_item.split(".") if segment]
                    if path:
                        include_paths.append(path)
                deduped_include_paths: List[List[str]] = []
                seen_paths: Set[Tuple[str, ...]] = set()
                for include_path in include_paths:
                    include_tuple = tuple(include_path)
                    if not include_tuple or include_tuple in seen_paths:
                        continue
                    seen_paths.add(include_tuple)
                    deduped_include_paths.append(include_path)
                included: List[Dict[str, Any]] = []
                seen_included: Set[Tuple[str, str]] = set()
                for item in [obj]:
                    self._collect_included(Model, item, deduped_include_paths, fields_map, seen_included, included)
                # SAFRS _s_post commits internally
                return JSONAPIResponse(
                    status_code=201,
                    content=self._jsonapi_doc(
                        data=self._encode_resource(Model, obj, wanted_fields=wanted_fields),
                        included=included if included else None,
                    ),
                )
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

                # Optional strict check: data.id should match path id if present
                body_id = data.get("id")
                if body_id is not None and str(body_id) != str(object_id):
                    self._jsonapi_error(400, "ValidationError", "Body id does not match path id")

                attrs = data.get("attributes") or {}
                attrs = self._parse_attributes_for_model(Model, attrs)

                obj = Model.get_instance(object_id)
                obj = obj._s_patch(**attrs)
                fields_map = self._parse_sparse_fields_map(request)
                wanted_fields = fields_map.get(str(Model._s_type)) or self._parse_sparse_fields(Model, request)
                include_paths = self._parse_include_paths(Model, request)
                included: List[Dict[str, Any]] = []
                seen: Set[Tuple[str, str]] = set()
                if include_paths:
                    self._collect_included(Model, obj, include_paths, fields_map, seen, included)
                return self._jsonapi_doc(
                    data=self._encode_resource(Model, obj, wanted_fields=wanted_fields),
                    included=included if included else None,
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
                obj._s_delete()
                safrs.DB.session.commit()
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
                rel = self._resolve_relationships(Model).get(rel_name)
                if rel is None:
                    self._jsonapi_error(404, "NotFound", f"Unknown relationship '{rel_name}'")
                target_model = rel.mapper.class_
                fields_map = self._parse_sparse_fields_map(request)
                wanted_fields = fields_map.get(str(target_model._s_type))
                rel_value = getattr(parent, rel_name, None)

                if rel.uselist:
                    items = self._iter_related_items(rel_value)
                    items = self._apply_sort_query_or_items(target_model, items, request)
                    items = self._apply_pagination(items, request)
                    items = self._coerce_items(items)
                    data = [self._encode_resource(target_model, item, wanted_fields=wanted_fields) for item in items]
                    return self._jsonapi_doc(data=data, meta={"count": len(data)})

                if rel_value is None:
                    self._jsonapi_error(404, "NotFound", f"Relationship '{rel_name}' is empty")
                return self._jsonapi_doc(data=self._encode_resource(target_model, rel_value, wanted_fields=wanted_fields))
            except Exception as exc:
                self._handle_safrs_exception(exc)

        return handler

    def _get_relationship_item(self, Model: Type[Any], rel_name: str):
        def handler(object_id: str, target_id: str, request: Request):
            try:
                parent = Model.get_instance(object_id)
                rel = self._resolve_relationships(Model).get(rel_name)
                if rel is None:
                    self._jsonapi_error(404, "NotFound", f"Unknown relationship '{rel_name}'")
                target_model = rel.mapper.class_
                fields_map = self._parse_sparse_fields_map(request)
                wanted_fields = fields_map.get(str(target_model._s_type))
                rel_value = getattr(parent, rel_name, None)
                for item in self._iter_related_items(rel_value):
                    if str(item.jsonapi_id) == str(target_id):
                        return self._jsonapi_doc(data=self._encode_resource(target_model, item, wanted_fields=wanted_fields))
                self._jsonapi_error(404, "NotFound", f"Relationship item '{target_id}' not found")
            except Exception as exc:
                self._handle_safrs_exception(exc)

        return handler

    def _patch_relationship(self, Model: Type[Any], rel_name: str):
        def handler(object_id: str, payload: Dict[str, Any] = Body(..., media_type=JSONAPI_MEDIA_TYPE)):
            try:
                parent = Model.get_instance(object_id)
                rel = self._resolve_relationships(Model).get(rel_name)
                if rel is None:
                    self._jsonapi_error(404, "NotFound", f"Unknown relationship '{rel_name}'")
                target_model = rel.mapper.class_
                data = payload.get("data")
                rel_value = getattr(parent, rel_name, None)

                if rel.uselist:
                    if not isinstance(data, list):
                        self._jsonapi_error(400, "ValidationError", "PATCH a TOMANY relationship with a list")
                    self._clear_relationship(rel_value)
                    for item in data:
                        target = self._lookup_related_instance(target_model, item)
                        self._append_relationship_item(rel_value, target)
                    safrs.DB.session.commit()
                    items = self._iter_related_items(rel_value)
                    return self._jsonapi_doc(
                        data=[self._encode_resource(target_model, item) for item in items],
                        meta={"count": len(items)},
                    )

                if data is None:
                    setattr(parent, rel_name, None)
                    safrs.DB.session.commit()
                    return Response(status_code=204)
                if not isinstance(data, dict):
                    self._jsonapi_error(400, "ValidationError", "Invalid data payload")
                target = self._lookup_related_instance(target_model, data)
                setattr(parent, rel_name, target)
                safrs.DB.session.commit()
                return Response(status_code=204)
            except Exception as exc:
                self._handle_safrs_exception(exc)

        return handler

    def _post_relationship(self, Model: Type[Any], rel_name: str):
        def handler(object_id: str, payload: Dict[str, Any] = Body(..., media_type=JSONAPI_MEDIA_TYPE)):
            try:
                parent = Model.get_instance(object_id)
                rel = self._resolve_relationships(Model).get(rel_name)
                if rel is None:
                    self._jsonapi_error(404, "NotFound", f"Unknown relationship '{rel_name}'")
                target_model = rel.mapper.class_
                data = payload.get("data")
                rel_value = getattr(parent, rel_name, None)

                if rel.uselist:
                    if not isinstance(data, list):
                        self._jsonapi_error(400, "ValidationError", "Invalid data payload")
                    for item in data:
                        target = self._lookup_related_instance(target_model, item)
                        self._append_relationship_item(rel_value, target)
                    safrs.DB.session.commit()
                    return Response(status_code=204)

                if not isinstance(data, dict):
                    self._jsonapi_error(400, "ValidationError", "Invalid data payload")
                target = self._lookup_related_instance(target_model, data)
                setattr(parent, rel_name, target)
                safrs.DB.session.commit()
                return self._jsonapi_doc(data=self._encode_resource(target_model, target))
            except Exception as exc:
                self._handle_safrs_exception(exc)

        return handler

    def _delete_relationship(self, Model: Type[Any], rel_name: str):
        def handler(object_id: str, payload: Dict[str, Any] = Body(..., media_type=JSONAPI_MEDIA_TYPE)):
            try:
                parent = Model.get_instance(object_id)
                rel = self._resolve_relationships(Model).get(rel_name)
                if rel is None:
                    self._jsonapi_error(404, "NotFound", f"Unknown relationship '{rel_name}'")
                target_model = rel.mapper.class_
                data = payload.get("data")
                rel_value = getattr(parent, rel_name, None)

                if rel.uselist:
                    if not isinstance(data, list):
                        self._jsonapi_error(400, "ValidationError", "Invalid data payload")
                    for item in data:
                        target = self._lookup_related_instance(target_model, item)
                        self._remove_relationship_item(rel_value, target)
                    safrs.DB.session.commit()
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
                safrs.DB.session.commit()
                return Response(status_code=204)
            except Exception as exc:
                self._handle_safrs_exception(exc)

        return handler
