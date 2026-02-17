from http import HTTPStatus
from types import SimpleNamespace
from typing import Optional

import pytest
from sqlalchemy.orm.interfaces import MANYTOONE, ONETOMANY
import safrs

from safrs.errors import ValidationError
from safrs.jsonapi import SAFRSRestRelationshipAPI
import safrs.jsonapi as jsonapi_mod


class _FakeTarget:
    _s_type = "children"
    _s_object_id = "ChildId"

    def __init__(self, instances: dict[str, object]) -> None:
        self._instances = instances

    def get_instance(self, object_id: str) -> Optional[object]:
        return self._instances.get(object_id)


class _FakeParent:
    def __init__(self, children: Optional[list[object]]=None, child: Optional[object]=None) -> None:
        self.jsonapi_id = "parent-1"
        self.children = children if children is not None else []
        self.child = child


def _build_api(direction: object, rel_name: str, parent: _FakeParent, relation: object, payload: dict, target_instances: dict[str, object]) -> SAFRSRestRelationshipAPI:
    api = object.__new__(SAFRSRestRelationshipAPI)
    api.SAFRSObject = SimpleNamespace(relationship=SimpleNamespace(direction=direction, key=rel_name))
    api.rel_name = rel_name
    api.parent_object_id = "ParentId"
    api.child_object_id = "ChildId"
    api.target = _FakeTarget(target_instances)
    api.parse_args = lambda **kwargs: (parent, relation)
    api._parse_target_data = lambda data: api.target.get_instance(data["id"])
    return api


@pytest.fixture(autouse=True)
def _patch_jsonapi_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        safrs,
        "log",
        SimpleNamespace(debug=lambda *a, **k: None, info=lambda *a, **k: None, warning=lambda *a, **k: None, error=lambda *a, **k: None),
        raising=False,
    )
    monkeypatch.setattr(jsonapi_mod, "jsonify", lambda data: data)
    monkeypatch.setattr(jsonapi_mod, "make_response", lambda data, status=None: (data, status))
    monkeypatch.setattr(jsonapi_mod, "request", SimpleNamespace(get_jsonapi_payload=lambda: {"data": None}))


def test_patch_tomany_rejects_dict_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    parent = _FakeParent(children=[])
    child = SimpleNamespace(jsonapi_id="child-1")
    payload = {"data": {"id": "child-1", "type": "children"}}
    monkeypatch.setattr(jsonapi_mod, "request", SimpleNamespace(get_jsonapi_payload=lambda: payload))
    api = _build_api(ONETOMANY, "children", parent, parent.children, payload, {"child-1": child})

    with pytest.raises(ValidationError) as exc_info:
        api.patch(ParentId="parent-1")
    assert "Provide a list to PATCH a TOMANY relationship" in exc_info.value.message


def test_post_manytoone_rejects_list_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    parent = _FakeParent(child=None)
    payload = {"data": [{"id": "child-1", "type": "children"}]}
    monkeypatch.setattr(jsonapi_mod, "request", SimpleNamespace(get_jsonapi_payload=lambda: payload))
    api = _build_api(MANYTOONE, "child", parent, parent.child, payload, {})

    with pytest.raises(ValidationError) as exc_info:
        api.post(ParentId="parent-1")
    assert "MANYTOONE relationship can only hold a single item" in exc_info.value.message


def test_post_tomany_appends_new_children(monkeypatch: pytest.MonkeyPatch) -> None:
    child1 = SimpleNamespace(jsonapi_id="child-1")
    child2 = SimpleNamespace(jsonapi_id="child-2")
    parent = _FakeParent(children=[child1])
    payload = {"data": [{"id": "child-1", "type": "children"}, {"id": "child-2", "type": "children"}]}
    monkeypatch.setattr(jsonapi_mod, "request", SimpleNamespace(get_jsonapi_payload=lambda: payload))
    api = _build_api(ONETOMANY, "children", parent, parent.children, payload, {"child-1": child1, "child-2": child2})

    body, status = api.post(ParentId="parent-1")

    assert status == HTTPStatus.NO_CONTENT
    assert body == {}
    assert parent.children == [child1, child2]


def test_delete_tomany_rejects_non_list_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    parent = _FakeParent(children=[])
    payload = {"data": {"id": "child-1", "type": "children"}}
    monkeypatch.setattr(jsonapi_mod, "request", SimpleNamespace(get_jsonapi_payload=lambda: payload))
    api = _build_api(ONETOMANY, "children", parent, parent.children, payload, {})

    with pytest.raises(ValidationError) as exc_info:
        api.delete(ParentId="parent-1")
    assert "Invalid data payload" in exc_info.value.message


def test_delete_tomany_removes_existing_child(monkeypatch: pytest.MonkeyPatch) -> None:
    child1 = SimpleNamespace(jsonapi_id="child-1")
    child2 = SimpleNamespace(jsonapi_id="child-2")
    parent = _FakeParent(children=[child1, child2])
    payload = {"data": [{"id": "child-1", "type": "children"}]}
    monkeypatch.setattr(jsonapi_mod, "request", SimpleNamespace(get_jsonapi_payload=lambda: payload))
    api = _build_api(ONETOMANY, "children", parent, parent.children, payload, {"child-1": child1, "child-2": child2})

    body, status = api.delete(ParentId="parent-1")

    assert status == HTTPStatus.NO_CONTENT
    assert body == {}
    assert parent.children == [child2]
