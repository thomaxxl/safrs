# flake8: noqa: F401
#
# The code implements some seemingly awkward constructs and redundant functionality
# This is however required for backwards compatibility, we'll get rid of it eventually
#
from typing import Any

from .safrs_init import DB, log, SAFRS, dict_merge, test_decorator, SAFRSRequest
from .errors import ValidationError, GenericError, IntegerOverflowError, UnAuthorizedError, NotFoundError
from .json_encoder import DefaultJSONProvider, SAFRSFormattedResponse
from .base import SAFRSBase
from .jabase import JABase
from .jsonapi_attr import jsonapi_attr
from .jsonapi_formatting import jsonapi_format_response, paginate
from .api_methods import search, startswith
from .api_doc import jsonapi_rpc
from . import tx
from .__about__ import __version__, __description__

_MISSING_FLASK_ADAPTER_DEPS = {"flask_restful", "flask_restful_swagger_2", "flask_swagger_ui"}


def _raise_missing_flask_adapter_error(exc: ModuleNotFoundError) -> None:
    raise ModuleNotFoundError(
        "Flask adapter dependencies are not installed. Install them with "
        "`pip install \"safrs[flask]\"`."
    ) from exc


try:
    from .safrs_api import SAFRSAPI
except ModuleNotFoundError as exc:
    if exc.name not in _MISSING_FLASK_ADAPTER_DEPS:
        raise
    _missing_flask_adapter_exc = exc

    class SAFRSAPI:  # type: ignore[no-redef]
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            _raise_missing_flask_adapter_error(_missing_flask_adapter_exc)


SafrsApi = SAFRSAPI

__all__ = (
    "__version__",
    "__description__",
    #
    "SAFRSAPI",
    "SafrsApi",
    # db:
    "SAFRSBase",
    "jsonapi_attr",
    "jsonapi_rpc",
    # jsonapi:
    "DefaultJSONProvider",
    "paginate",
    "jsonapi_format_response",
    "SAFRSFormattedResponse",
    "JABase",
    # api_methods:
    "search",
    "startswith",
    # Errors:
    "ValidationError",
    "IntegerOverflowError",
    "GenericError",
    "UnAuthorizedError",
    "NotFoundError",
    # request
    "SAFRSRequest",
    # tx helper
    "tx",
)
