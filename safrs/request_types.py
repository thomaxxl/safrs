from typing import Any, Optional, cast

try:
    from typing import Protocol
except ImportError:  # pragma: no cover
    from typing_extensions import Protocol

from .jsonapi_types import JSONAPIDocument


class JSONAPIRequest(Protocol):
    is_jsonapi: bool
    is_bulk: bool
    fields: dict[str, list[str]]

    def get_jsonapi_payload(self) -> Optional[JSONAPIDocument]:
        ...

    def get_page_limit(self, rel_name: Any) -> int:
        ...


def get_jsonapi_request(req: Any) -> JSONAPIRequest:
    return cast(JSONAPIRequest, req)
