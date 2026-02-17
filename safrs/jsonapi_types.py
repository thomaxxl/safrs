from typing import Any, Union

try:
    from typing import TypedDict
except ImportError:  # pragma: no cover
    from typing_extensions import TypedDict


class JSONAPIResourceIdentifier(TypedDict):
    id: str
    type: str


class JSONAPIResourceObject(JSONAPIResourceIdentifier, total=False):
    attributes: dict[str, Any]
    relationships: dict[str, Any]
    meta: dict[str, Any]
    links: dict[str, Any]


JSONAPIData = Union[JSONAPIResourceObject, list[JSONAPIResourceObject], None]


class JSONAPIDocument(TypedDict, total=False):
    data: JSONAPIData
    meta: dict[str, Any]
    errors: list[dict[str, Any]]
    included: list[JSONAPIResourceObject]
    links: dict[str, Any]


class JSONAPIResponseDocument(TypedDict, total=False):
    data: Any
    meta: dict[str, Any]
    errors: Any
    included: Any
    links: dict[str, Any]
    jsonapi: dict[str, str]
