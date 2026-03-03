from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

from fastapi import FastAPI, Request

from safrs.fastapi.api import SafrsFastAPI


class _SourceModel:
    _s_type = "Order"
    _s_collection_name = "Order"
    _s_jsonapi_attrs = {"Id": object(), "ShipName": object()}


class _EncodedResource:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def _s_jsonapi_encode(self) -> dict[str, Any]:
        return deepcopy(self._payload)


def _request(path: str, query: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": [],
            "query_string": query.encode(),
        }
    )


def test_encode_resource_includes_links_and_relationships() -> None:
    api = SafrsFastAPI(FastAPI(), prefix="/api")

    encoded = {
        "type": "Order",
        "id": "10248",
        "attributes": {"Id": 10248, "ShipName": "Ship Name"},
        "links": {"self": "/api/Order/10248/"},
        "relationships": {
            "Customer": {"links": {"self": "/api/Order/10248/Customer"}, "data": {"type": "Customer", "id": "VINET"}},
            "Location": {"links": {"self": "/api/Order/10248/Location"}, "data": None},
            "OrderList": {"links": {"self": "/api/Order/10248/OrderList"}, "data": []},
        },
    }
    obj = _EncodedResource(encoded)

    payload = api._encode_resource(_SourceModel, obj, include_relationships=True, include_links=True)

    assert payload["links"]["self"] == "/api/Order/10248/"
    assert payload["relationships"]["Customer"]["links"]["self"] == "/api/Order/10248/Customer"
    assert payload["relationships"]["Customer"]["data"] == {"type": "Customer", "id": "VINET"}
    assert payload["relationships"]["Location"]["data"] is None
    assert payload["relationships"]["OrderList"]["data"] == []

    payload_no_links = api._encode_resource(_SourceModel, obj, include_relationships=True, include_links=False)
    assert "links" not in payload_no_links
    assert "relationships" in payload_no_links

    payload_no_rels = api._encode_resource(_SourceModel, obj, include_relationships=False, include_links=True)
    assert "links" in payload_no_rels
    assert "relationships" not in payload_no_rels

    payload_sparse = api._encode_resource(
        _SourceModel,
        _EncodedResource(
            {
                "type": "Order",
                "id": "10248",
                "attributes": {"Id": 10248, "ShipName": "Ship Name"},
                "links": {"self": "/api/Order/10248/"},
                "relationships": {},
            }
        ),
        wanted_fields={"Id"},
    )
    assert payload_sparse["attributes"] == {"Id": 10248}


def test_pagination_links_match_flask_style() -> None:
    api = SafrsFastAPI(FastAPI(), prefix="/api")
    request = _request(
        "/api/Order/",
        "include=Customer,Employee&page[offset]=0&page[limit]=1",
    )

    links = api._pagination_links(request, count=830, page_offset=0, limit=1)

    assert links["self"] == "/api/Order/?include=Customer,Employee&page[offset]=0&page[limit]=1"
    assert links["next"] == "/api/Order/?include=Customer,Employee&page[offset]=1&page[limit]=1"
    assert links["last"] == "/api/Order/?include=Customer,Employee&page[offset]=830&page[limit]=1"
    assert "first" not in links
    assert "prev" not in links


def test_jsonapi_data_response_uses_shared_formatter() -> None:
    api = SafrsFastAPI(FastAPI(), prefix="/api")
    response = api._jsonapi_data_response(data=[], count=0)
    payload = json.loads(response.body.decode("utf-8"))

    assert payload["jsonapi"] == {"version": "1.0"}
    assert payload["data"] == []
    assert payload["included"] == []
    assert payload["meta"]["count"] == 0
