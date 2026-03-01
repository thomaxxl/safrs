from __future__ import annotations

from typing import Any

from flask import Flask

from safrs.jsonapi import SAFRSRestAPI, SAFRSRestRelationshipAPI, _build_location_header


class _FakeInstance:
    _s_object_id = "CustomerId"

    def __init__(self, jsonapi_id: str) -> None:
        self.jsonapi_id = jsonapi_id


def test_build_location_header_percent_encodes_control_chars() -> None:
    app = Flask(__name__)

    @app.route("/api/Customer/<CustomerId>", endpoint="customer_detail")
    def _customer_detail(**_kwargs: Any) -> str:
        return "ok"

    with app.test_request_context("/"):
        location = _build_location_header("customer_detail", _FakeInstance("\nX"))

    assert "\n" not in location
    assert "\r" not in location
    assert "%0A" in location
    assert location.endswith("%0AX")


def test_collection_delete_docstring_documents_conflict_status() -> None:
    doc = SAFRSRestAPI.delete.__doc__ or ""
    assert "409" in doc
    assert "description: Conflict" in doc


def test_relationship_delete_docstring_documents_conflict_status() -> None:
    doc = SAFRSRestRelationshipAPI.delete.__doc__ or ""
    assert "409" in doc
    assert "description: Conflict" in doc
