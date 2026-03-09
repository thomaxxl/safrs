from __future__ import annotations

from pathlib import Path

from safrs.request import HTTP_METHODS


def test_request_module_defines_http_methods_without_flask_adapter_import() -> None:
    source = Path("safrs/request.py").read_text(encoding="utf-8")
    assert "from .safrs_api import HTTP_METHODS" not in source
    assert HTTP_METHODS == {"GET", "POST", "PATCH", "DELETE", "PUT"}
