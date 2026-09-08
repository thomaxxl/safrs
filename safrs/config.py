# Configuration settings should be set in app.config
# Most of the configuration in this file is deprecated, it is kept for backwards compatibility
# The get_config function handles the current config while remaining backwards compatible
import os
import logging
from flask import current_app, request
import safrs
from typing import Any


def get_config(option: str) -> Any:
    """Retrieve a configuration parameter from the app
    :param option: configuration parameter
    :return: configuration value
    :rtype: string
    """

    try:
        result = current_app.config[option]
    except (KeyError, RuntimeError):
        try:
            app_config = current_app.extensions.get("safrs_config", {})
            result = app_config.get(option)
        except RuntimeError:
            result = None
        if result is None:
            result = getattr(safrs.SAFRS, option, os.environ.get(option, None))
    if result is not None:
        return result
    # pylint: disable=invalid-name, unused-variable, pointless-string-statement
    # The suffix of the url path parameter shown in the swagger UI, eg Id => /Users/{UserId}
    OBJECT_ID_SUFFIX = os.environ.get("OBJECT_ID_SUFFIX", safrs.SAFRS.OBJECT_ID_SUFFIX)
    if not OBJECT_ID_SUFFIX:
        OBJECT_ID_SUFFIX = "Id"

    # The following URL fromatters determine the urls of the API resource objects
    #
    # first argument will be is the url prefix (eg. /api/v1/ )
    # second argument will be object tablename (ie resource, eg. Users)
    # Third parameter will be the "Object id" (eg. UserId)
    # => /api/v1/Users/{UserId}
    RESOURCE_URL_FMT = "{}/{}/"
    INSTANCE_URL_FMT = RESOURCE_URL_FMT + "<string:{}" + OBJECT_ID_SUFFIX + ">/"
    # last parameter for the "method" urls below will be the method name
    INSTANCEMETHOD_URL_FMT = os.environ.get("INSTANCEMETHOD_URL_FMT", None)
    if not INSTANCEMETHOD_URL_FMT:
        INSTANCEMETHOD_URL_FMT = RESOURCE_URL_FMT + "<string:{}>/{}"
    # (eg. /Users/get_list)
    CLASSMETHOD_URL_FMT = RESOURCE_URL_FMT + "{}"

    # Parent-> Child relationship, (eg. /Users/{UserId}/books)
    RELATIONSHIP_URL_FMT = "{}{}"

    """
    # Alternative configuration with more explicit urls:
    INSTANCE_URL_FMT = '{}{}/instances/<string:{}' + OBJECT_ID_SUFFIX + '>/'
    RELATIONSHIP_URL_FMT = '{}relationships/{}'
    # last parameter for the "method" urls below will be the method name
    INSTANCEMETHOD_URL_FMT = '{}{}/instances/<string:{}>/methods/{}'
    CLASSMETHOD_URL_FMT = '{}{}/methods/{}'
    """

    # endpoint naming
    INSTANCE_ENDPOINT_FMT = "{}api.{}Id"
    ENDPOINT_FMT = "{}api.{}"

    # UNLIMITED = int(os.environ.get('safrs.SAFRS_UNLIMITED', 1<<32))
    UNLIMITED = int(os.environ.get("SAFRS_UNLIMITED", safrs.SAFRS.MAX_PAGE_LIMIT))
    MAX_PAGE_LIMIT = int(os.environ.get("MAX_PAGE_LIMIT", safrs.SAFRS.MAX_PAGE_LIMIT))
    MAX_PAGE_OFFSET = int(os.environ.get("MAX_PAGE_OFFSET", safrs.SAFRS.MAX_PAGE_OFFSET))
    MAX_BULK_ITEMS = int(os.environ.get("MAX_BULK_ITEMS", safrs.SAFRS.MAX_BULK_ITEMS))
    MAX_INCLUDE_DEPTH = int(os.environ.get("MAX_INCLUDE_DEPTH", safrs.SAFRS.MAX_INCLUDE_DEPTH))
    MAX_INCLUDE_PATHS = int(os.environ.get("MAX_INCLUDE_PATHS", safrs.SAFRS.MAX_INCLUDE_PATHS))
    MAX_INCLUDED_RESOURCES = int(
        os.environ.get("MAX_INCLUDED_RESOURCES", safrs.SAFRS.MAX_INCLUDED_RESOURCES)
    )
    MAX_FILTER_LENGTH = int(os.environ.get("MAX_FILTER_LENGTH", safrs.SAFRS.MAX_FILTER_LENGTH))
    MAX_FILTER_DEPTH = int(os.environ.get("MAX_FILTER_DEPTH", safrs.SAFRS.MAX_FILTER_DEPTH))
    MAX_FILTER_CLAUSES = int(os.environ.get("MAX_FILTER_CLAUSES", safrs.SAFRS.MAX_FILTER_CLAUSES))
    MAX_FILTER_VALUES = int(os.environ.get("MAX_FILTER_VALUES", safrs.SAFRS.MAX_FILTER_VALUES))
    MAX_BRACKET_FILTERS = int(
        os.environ.get("MAX_BRACKET_FILTERS", safrs.SAFRS.MAX_BRACKET_FILTERS)
    )
    MAX_SORT_TERMS = int(os.environ.get("MAX_SORT_TERMS", safrs.SAFRS.MAX_SORT_TERMS))
    MAX_AUTHORIZATION_SCAN = int(
        os.environ.get("MAX_AUTHORIZATION_SCAN", safrs.SAFRS.MAX_AUTHORIZATION_SCAN)
    )
    MAX_REQUEST_BODY_BYTES = int(
        os.environ.get("MAX_REQUEST_BODY_BYTES", safrs.SAFRS.MAX_REQUEST_BODY_BYTES)
    )
    MAX_JSON_DEPTH = int(os.environ.get("MAX_JSON_DEPTH", safrs.SAFRS.MAX_JSON_DEPTH))
    MAX_REQUEST_RESOURCES = int(
        os.environ.get("MAX_REQUEST_RESOURCES", safrs.SAFRS.MAX_REQUEST_RESOURCES)
    )
    # This is the default query limit
    # used as default sqla "limit" parameter. -1 works for sqlite but not for mysql
    BIG_QUERY_THRESHOLD = 1000  # Warning level
    MAX_QUERY_THRESHOLD = BIG_QUERY_THRESHOLD
    USE_API_METHODS = True

    # ENABLE_RELATIONSHIPS enables relationships to be included.
    # This may slow down certain queries if the relationships are not properly configured!
    ENABLE_RELATIONSHIPS = bool(os.environ.get("ENABLE_RELATIONSHIPS", safrs.SAFRS.ENABLE_RELATIONSHIPS))

    MAX_TABLE_COUNT = int(os.environ.get("MAX_TABLE_COUNT", safrs.SAFRS.MAX_TABLE_COUNT))

    result = locals().get(option)

    return result


def get_request_param(param: Any, default: Any=0) -> Any:
    """Retrieve request parameters
    Used for backwards compatibility (with safrs < 2.x)
    :param param: parameter to retrieve
    :param default:
    :return: prequest parameter or None
    :rtype: Boolean
    """
    result = getattr(request, param, None)
    return result


def is_debug() -> bool:
    """
    We use the loglevel to check whether we're running in debug mode
    :return: whether the app is in debug mode
    :rtype: Boolean
    """
    return safrs.log.getEffectiveLevel() < logging.INFO
