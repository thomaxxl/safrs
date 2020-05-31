# -*- coding: utf-8 -*-
# flake8: noqa: F401
#
# The code implements some seemingly awkward constructs and redundant functionality
# This is however required for backwards compatibility, we'll get rid of it eventually
#
from .safrs_api import DB, log, SAFRSAPI, SAFRS, dict_merge, test_decorator, SAFRSRequest
from .errors import ValidationError, GenericError
from .json_encoder import SAFRSJSONEncoder
from ._api import Api, SAFRSRestAPI
from .base import SAFRSBase, jsonapi_attr
from .jsonapi import jsonapi_format_response, SAFRSFormattedResponse, paginate
from .api_methods import search, startswith
from .swagger_doc import jsonapi_rpc
from .__about__ import __version__, __description__

__all__ = (
    "__version__",
    "__description__",
    #
    "SAFRSAPI",
    "SAFRSRestAPI",
    # db:
    "SAFRSBase",
    "jsonapi_attr",
    "jsonapi_rpc",
    # jsonapi:
    "SAFRSJSONEncoder",
    "paginate",
    "jsonapi_format_response",
    "SAFRSFormattedResponse",
    # api_methods:
    "search",
    "startswith",
    # Errors:
    "ValidationError",
    "GenericError",
    # request
    "SAFRSRequest",
)
