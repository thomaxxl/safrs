from __future__ import annotations

import asyncio
from contextvars import copy_context
import json
from types import SimpleNamespace
from typing import Any

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI, Request

import safrs
from safrs.errors import GenericError, reset_fastapi_request_url, set_fastapi_request_url
from safrs.fastapi.api import JSONAPIHTTPError, JSONAPI_MEDIA_TYPE, SafrsFastAPI, install_jsonapi_exception_handlers
from safrs.fastapi.schemas.registry import SchemaRegistry


def _request(query: str = "") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "query_string": query.encode(),
        }
    )


def test_generic_error_debug_mode_without_flask_request_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("safrs.errors.is_debug", lambda: True)
    err = GenericError("boom")
    assert "boom" in err.message


def test_fastapi_request_url_reset_handles_different_contexts() -> None:
    token = set_fastapi_request_url("http://example.invalid")

    def _reset_in_other_context() -> None:
        reset_fastapi_request_url(token)

    copy_context().run(_reset_in_other_context)


def test_fastapi_exception_handler_returns_jsonapi_error_document() -> None:
    app = FastAPI()
    install_jsonapi_exception_handlers(app)
    handler = app.exception_handlers[Exception]
    request = _request()
    response = asyncio.run(handler(request, RuntimeError("boom")))

    assert response.status_code == 500
    assert JSONAPI_MEDIA_TYPE in response.headers.get("content-type", "")
    payload = json.loads(response.body.decode("utf-8"))
    assert payload["errors"][0]["status"] == "500"
    assert payload["errors"][0]["detail"] == "Internal Server Error"


def test_fastapi_error_document_schema_includes_error_source_links_and_meta() -> None:
    schema = SchemaRegistry().error_document().model_json_schema()
    error_items = schema["properties"]["errors"]["items"]
    error_ref = error_items["$ref"]
    error_schema = schema["$defs"]["JsonApiErrorObject"]
    error_props = error_schema["properties"]
    source_ref = error_props["source"]["anyOf"][0]["$ref"]
    links_ref = error_props["links"]["anyOf"][0]["$ref"]
    meta_ref = error_props["meta"]["anyOf"][0]["$ref"]

    assert error_ref.endswith("/JsonApiErrorObject")
    assert source_ref.endswith("/JsonApiErrorSource")
    assert links_ref.endswith("/JsonApiErrorLinks")
    assert meta_ref.endswith("/JsonApiMeta")


def test_handle_safrs_exception_maps_runtime_errors_to_jsonapi_and_rolls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    api = SafrsFastAPI(app)
    rollback_calls = {"count": 0}

    class Session:
        info: dict[str, Any] = {}

        def rollback(self) -> None:
            rollback_calls["count"] += 1

    monkeypatch.setattr(safrs, "DB", SimpleNamespace(session=Session()))

    with pytest.raises(JSONAPIHTTPError) as exc_info:
        api._handle_safrs_exception(RuntimeError("boom"))

    assert exc_info.value.status_code == 500
    assert exc_info.value.payload["errors"][0]["detail"] == "Internal Server Error"
    assert rollback_calls["count"] == 1


def test_handle_safrs_exception_maps_dependency_rule_assertion_to_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    api = SafrsFastAPI(app)
    rollback_calls = {"count": 0}

    class Session:
        info: dict[str, Any] = {}

        def rollback(self) -> None:
            rollback_calls["count"] += 1

    monkeypatch.setattr(safrs, "DB", SimpleNamespace(session=Session()))
    message = "Dependency rule on column 'Books.id' tried to blank-out primary key column 'Reviews.book_id'"
    with pytest.raises(JSONAPIHTTPError) as exc_info:
        api._handle_safrs_exception(AssertionError(message))

    assert exc_info.value.status_code == 409
    assert exc_info.value.payload["errors"][0]["detail"] == "Relationship update violates DB constraints"
    assert rollback_calls["count"] == 1


def test_handle_safrs_exception_logs_traceback_in_debug(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    api = SafrsFastAPI(app)
    rollback_calls = {"count": 0}
    log_calls = {"error": 0, "exception": 0}

    class Session:
        info: dict[str, Any] = {}

        def rollback(self) -> None:
            rollback_calls["count"] += 1

    monkeypatch.setattr(safrs, "DB", SimpleNamespace(session=Session()))
    monkeypatch.setattr("safrs.fastapi.api.is_debug", lambda: True)
    monkeypatch.setattr(safrs.log, "error", lambda *args, **kwargs: log_calls.__setitem__("error", log_calls["error"] + 1))
    monkeypatch.setattr(
        safrs.log,
        "exception",
        lambda *args, **kwargs: log_calls.__setitem__("exception", log_calls["exception"] + 1),
    )

    with pytest.raises(JSONAPIHTTPError) as exc_info:
        api._handle_safrs_exception(RuntimeError("boom"))

    assert exc_info.value.status_code == 500
    assert log_calls["exception"] == 1
    assert log_calls["error"] == 0
    assert rollback_calls["count"] == 1


def test_rpc_request_context_handles_multi_value_query_params() -> None:
    request = _request("x=1&x=2&page[offset]=3")
    with SafrsFastAPI._rpc_request_context(request):
        from flask import request as flask_request

        assert flask_request.args.getlist("x") == ["1", "2"]
        assert flask_request.args.get("page[offset]") == "3"
