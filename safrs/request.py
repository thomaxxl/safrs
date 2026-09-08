"""
http://jsonapi.org/format/#content-negotiation-servers

Server Responsibilities
Servers MUST send all JSON API data in response documents with the header
"Content-Type: application/vnd.api+json" without any media type parameters.

Servers MUST respond with a 415 Unsupported Media Type status code if a request specifies the header
"Content-Type: application/vnd.api+json" with any media type parameters.
This should be implemented by the app, for example using @app.before_request  and @app.after_request
"""
from typing import Any

import re
from flask import Request, abort
from werkzeug.datastructures import TypeConversionDict
import safrs
from .config import get_config
from .errors import ValidationError
from .filtering import parse_bracket_filter_name

HTTP_METHODS = {"GET", "POST", "PATCH", "DELETE", "PUT"}


def validate_json_payload(payload: Any) -> None:
    """Bound nesting and total JSON:API resource objects in one request."""
    max_depth = int(get_config("MAX_JSON_DEPTH") or 0)
    max_resources = int(get_config("MAX_REQUEST_RESOURCES") or 0)
    resources = 0
    stack: list[tuple[Any, int]] = [(payload, 1)]
    while stack:
        value, depth = stack.pop()
        if max_depth > 0 and depth > max_depth:
            raise ValidationError(f"JSON payload exceeds maximum depth {max_depth}")
        if isinstance(value, dict):
            if "type" in value and any(key in value for key in ("id", "attributes", "relationships")):
                resources += 1
                if max_resources > 0 and resources > max_resources:
                    raise ValidationError(
                        f"JSON payload exceeds maximum resource count {max_resources}"
                    )
            stack.extend((nested, depth + 1) for nested in value.values())
        elif isinstance(value, list):
            stack.extend((nested, depth + 1) for nested in value)


# pylint: disable=too-many-ancestors, logging-format-interpolation
class SAFRSRequest(Request):
    """
    Parse jsonapi-related the request arguments:
    - header: Content-Type should be "application/vnd.api+json"
    - query args: page[limit], page[offset], fields
    - body: valid json
    """

    jsonapi_content_types: list[str] = ["application/json", "application/vnd.api+json"]
    is_jsonapi: bool = False  # indicates whether this is a jsonapi request
    _extensions: set[str] = set()
    filters: dict[str, str] = {}
    filter: str = ""  # filter is the custom filter, used as an argument by _s_filter
    filter_validation_error: str = ""
    includes: list[str] = []
    secure: bool = True

    def __init__(self: Any, *args: Any, **kwargs: Any) -> None:
        """
        constructor
        """
        super().__init__(*args, **kwargs)
        self.parse_content_type()
        self.parse_jsonapi_args()

    def parse_content_type(self: Any) -> Any:
        """
        Check if the request content type is jsonapi and any requested extensions
        """
        if not isinstance(self.content_type, str):  # pragma: no cover
            return

        content_type = self.content_type.split(";")[0]
        if content_type not in self.jsonapi_content_types:  # pragma: no cover
            return

        self.is_jsonapi = True
        self.parameter_storage_class = TypeConversionDict

        extensions = self.content_type.split(";")[1:]
        for ext in extensions:
            parsed_ext = ext.strip().split("=")
            if parsed_ext[0] == "ext" and parsed_ext[1:]:
                ext_name = parsed_ext[1]
                self._extensions.add(ext_name)

    @property
    def page_offset(self: Any) -> Any:
        """
        :return: page offset requested by the client when fetching lists

        Json:API supports multiple paging strategies.
        (https://jsonapi.org/format/#fetching-pagination)
        Here we extract the paging parameters to be used by sqla from the url query string.
        If the client uses page[number] instead of page[offset], then we transform the
        number parameter to an offset
        """
        page_offset = self.args.get("page[offset]", 0, type=int)
        if page_offset == 0 and "page[number]" in self.args and "page[size]" in self.args:
            page_size = self.args.get("page[size]", type=int)
            page_number = self.args.get("page[number]", type=int) - 1
            page_offset = page_number * page_size
        return page_offset

    def get_page_offset(self: Any, rel_name: Any) -> Any:
        """
        get the page offset for the included relationship resource
        :param rel_name: name of the relationship
        :return: page offset for included resources
        """
        page_offset = self.args.get(f"page[{rel_name}][offset]", 0, type=int)
        if page_offset == 0 and "page[{rel_name}][number]" in self.args and "page[{rel_name}][size]" in self.args:
            page_size = self.args.get("page[{rel_name}][size]", type=int)
            page_number = self.args.get("page[{rel_name}][number]", type=int) - 1
            page_offset = page_number * page_size
        return page_offset

    @property
    def page_limit(self: Any) -> Any:
        """
        get the page limit for the included relationship resource
        :param rel_name: name of the relationship
        :return: page limit for included resources
        """
        page_limit = self.args.get("page[limit]", get_config("DEFAULT_PAGE_LIMIT"), type=int)
        if "page[number]" in self.args and "page[size]" in self.args:
            return self.args.get("page[size]", type=int)
        return page_limit

    def get_page_limit(self: Any, rel_name: Any) -> Any:
        page_limit = self.args.get(f"page[{rel_name}][limit]", self.page_limit, type=int)
        if "page[{rel_name}][number]" in self.args and "page[{rel_name}][size]" in self.args:
            return self.args.get("page[{rel_name}][size]", type=int)
        return page_limit

    @property
    def is_bulk(self: Any) -> Any:
        """
        jsonapi bulk extension, http://springbot.github.io/json-api/extensions/bulk/
        """
        return "bulk" in self._extensions

    def get_jsonapi_payload(self: Any) -> Any:
        """
        :return: jsonapi request payload
        """
        if not self.is_jsonapi:  # pragma: no cover
            safrs.log.warning(f'Invalid Media Type! "{self.content_type}"')
            # raise GenericError('Unsupported Media Type', 415)
        if self.method == "OPTIONS":
            return None
        if self.method not in HTTP_METHODS:
            abort(500)
        result = self.get_json()
        if not isinstance(result, dict):
            raise ValidationError("Invalid JSON payload (expected object)")
        validate_json_payload(result)
        return result

    def parse_jsonapi_args(self: Any) -> Any:
        """
        parse the jsonapi request arguments:
        - page[offset]
        - page[limit]
        - filter[]
        - fields[]
        """

        self.filters = {}
        self.fields = {}
        self.filter_validation_error = ""

        # Parse the jsonapi filter[] and fields[] args
        for arg, val in self.args.items():
            if arg == "filter":
                self.filter = val

            try:
                attr_name = parse_bracket_filter_name(arg)
            except ValidationError as exc:
                # Request construction happens outside SAFRS' JSON:API error
                # wrapper. Defer the error so clients receive a normal 400
                # document rather than an uncaught exception.
                self.filter_validation_error = exc.message
                attr_name = None
            if attr_name is not None:
                self.filters[attr_name] = val

            # https://jsonapi.org/format/#fetching-sparse-fieldsets
            fields_attr = re.search(r"fields\[(\w+)\]", arg)
            if fields_attr:
                field_type = fields_attr.group(1)
                self.fields[field_type] = val.split(",")

            if arg == "include":
                self.includes = val.split(",")
