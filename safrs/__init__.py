# flake8: noqa: F401
#
# The code implements some seemingly awkward constructs and redundant functionality
# This is however required for backwards compatibility, we'll get rid of it eventually
#
from .safrs_init import DB, log, SAFRS, dict_merge, test_decorator, SAFRSRequest
from .errors import ValidationError, GenericError, UnAuthorizedError, NotFoundError
from .json_encoder import DefaultJSONProvider, SAFRSFormattedResponse
from .safrs_api import SAFRSAPI
from .base import SAFRSBase
from .jabase import JABase
from .jsonapi_attr import jsonapi_attr
from .jsonapi import jsonapi_format_response, paginate
from .api_methods import search, startswith
from .swagger_doc import jsonapi_rpc
from .__about__ import __version__, __description__

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
    "GenericError",
    "UnAuthorizedError",
    "NotFoundError",
    # request
    "SAFRSRequest",
)
