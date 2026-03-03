from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI, Request

from safrs.fastapi.api import SafrsFastAPI


class _TargetModel:
    _s_type = "Customer"


class _SourceModel:
    _s_type = "Order"
    _s_collection_name = "Order"
    _s_jsonapi_attrs = {"Id": object(), "ShipName": object()}


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


def test_encode_resource_includes_links_and_relationships(monkeypatch: Any) -> None:
    api = SafrsFastAPI(FastAPI(), prefix="/api")

    rel_to_one = SimpleNamespace(uselist=False, mapper=SimpleNamespace(class_=_TargetModel))
    rel_to_one_other = SimpleNamespace(uselist=False, mapper=SimpleNamespace(class_=_TargetModel))
    rel_to_many = SimpleNamespace(uselist=True, mapper=SimpleNamespace(class_=_TargetModel))
    monkeypatch.setattr(
        api,
        "_resolve_relationship_properties",
        lambda _model: {"Customer": rel_to_one, "Location": rel_to_one_other, "OrderList": rel_to_many},
    )

    obj = SimpleNamespace(
        jsonapi_id="10248",
        Id=10248,
        ShipName="Ship Name",
        Customer=SimpleNamespace(jsonapi_id="VINET"),
        Location=SimpleNamespace(jsonapi_id="USA_San Francisco"),
        OrderList=[SimpleNamespace(jsonapi_id="1")],
    )

    payload = api._encode_resource(
        _SourceModel,
        obj,
        include_relationships=True,
        include_links=True,
        include_relationship_names={"Customer"},
    )

    assert payload["links"]["self"] == "/api/Order/10248/"
    assert "relationships" in payload
    assert payload["relationships"]["Customer"]["links"]["self"] == "/api/Order/10248/Customer"
    assert payload["relationships"]["Customer"]["data"] == {"type": "Customer", "id": "VINET"}
    assert payload["relationships"]["Location"]["data"] is None
    assert payload["relationships"]["OrderList"]["data"] == []


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
