from __future__ import annotations

import datetime as dt
import json

from safrs.base import Included
from safrs.fastapi.responses import JSONAPIResponse
from safrs.jsonapi_context import JsonApiContext, reset_jsonapi_context, set_jsonapi_context


def test_jsonapi_response_uses_safrs_json_encoder_for_datetime() -> None:
    response = JSONAPIResponse(status_code=200, content={"at": dt.datetime(2024, 1, 2, 3, 4, 5)})
    payload = json.loads(response.body.decode("utf-8"))
    assert payload["at"] == "2024-01-02 03:04:05"


def test_jsonapi_response_renders_included_sentinel_without_flask_globals() -> None:
    token = set_jsonapi_context(JsonApiContext(query_params={}))
    try:
        response = JSONAPIResponse(status_code=200, content={"included": Included})
        payload = json.loads(response.body.decode("utf-8"))
    finally:
        reset_jsonapi_context(token)

    assert payload["included"] == []
