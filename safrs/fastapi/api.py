# -*- coding: utf-8 -*-

from typing import Any, Dict, Optional, Set, Type

import safrs
from safrs.attr_parse import parse_attr
from safrs.errors import JsonapiError, ValidationError

from fastapi import APIRouter, Body, FastAPI, Request, Response
from fastapi.encoders import jsonable_encoder

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
    def __init__(self, app: FastAPI, prefix: str = "") -> None:
        self.app = app
        self.prefix = prefix
        install_jsonapi_exception_handlers(app)

    @staticmethod
    def _with_slash_parity(path: str) -> list[str]:
        if path.endswith("/"):
            path = path.rstrip("/")
        return [path, path + "/"]

    def expose_object(self, Model: Type[Any]) -> None:
        """
        Register CRUD routes for a SAFRS model.
        """
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
                operation_id=f"delete_{tag}_instance" if idx == 0 else None,
                include_in_schema=(idx == 0),
            )

        self.app.include_router(router)

        # If /docs was opened before exposing models, FastAPI may have cached OpenAPI already.
        self.app.openapi_schema = None

    def _jsonapi_doc(self, data: Any = None, errors: Any = None) -> Dict[str, Any]:
        doc: Dict[str, Any] = {"jsonapi": {"version": "1.0"}}
        if errors is not None:
            doc["errors"] = errors
        if data is not None:
            doc["data"] = data
        return doc

    def _jsonapi_error(self, status_code: int, title: str, detail: str) -> None:
        payload = self._jsonapi_doc(
            errors=[{"status": str(status_code), "title": title, "detail": detail}]
        )
        raise JSONAPIHTTPError(status_code, payload)

    def _handle_safrs_exception(self, exc: Exception) -> None:
        if isinstance(exc, JSONAPIHTTPError):
            raise exc
        if isinstance(exc, JsonapiError):
            status = int(getattr(exc, "status_code", 400))
            msg = str(getattr(exc, "message", str(exc)))
            self._jsonapi_error(status, exc.__class__.__name__, msg)
        if isinstance(exc, ValidationError):
            self._jsonapi_error(400, "ValidationError", str(exc))
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
                wanted_fields = self._parse_sparse_fields(Model, request)
                objs = Model._s_query.all()
                data = [self._encode_resource(Model, o, wanted_fields=wanted_fields) for o in objs]
                return self._jsonapi_doc(data=data)
            except Exception as exc:
                self._handle_safrs_exception(exc)

        return handler

    def _get_instance(self, Model: Type[Any]):
        def handler(object_id: str, request: Request):
            try:
                obj = Model.get_instance(object_id)
                wanted_fields = self._parse_sparse_fields(Model, request)
                return self._jsonapi_doc(data=self._encode_resource(Model, obj, wanted_fields=wanted_fields))
            except Exception as exc:
                self._handle_safrs_exception(exc)

        return handler

    def _post_collection(self, Model: Type[Any]):
        def handler(
            payload: Dict[str, Any] = Body(..., media_type=JSONAPI_MEDIA_TYPE)
        ):
            try:
                self._require_type(Model, payload)
                data = payload.get("data") or {}
                attrs = data.get("attributes") or {}
                attrs = self._parse_attributes_for_model(Model, attrs)

                obj = Model._s_post(jsonapi_id=data.get("id"), **attrs)
                # SAFRS _s_post commits internally
                return JSONAPIResponse(
                    status_code=201,
                    content=self._jsonapi_doc(data=self._encode_resource(Model, obj)),
                )
            except JSONAPIHTTPError:
                raise
            except Exception as exc:
                self._handle_safrs_exception(exc)

        return handler

    def _patch_instance(self, Model: Type[Any]):
        def handler(
            object_id: str,
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
                return self._jsonapi_doc(data=self._encode_resource(Model, obj))
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
