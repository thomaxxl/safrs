"""
http://jsonapi.org/format/#content-negotiation-servers

Server Responsibilities
Servers MUST send all JSON API data in response documents with the header
"Content-Type: application/vnd.api+json" without any media type parameters.

Servers MUST respond with a 415 Unsupported Media Type status code if a request specifies the header
"Content-Type: application/vnd.api+json" with any media type parameters.
This should be implemented by the app, for example using @app.before_request  and @app.after_request
"""

import re
from flask import Request, abort
from werkzeug.datastructures import TypeConversionDict
import safrs
from .config import get_config
from .errors import ValidationError
from .safrs_api import HTTP_METHODS


# pylint: disable=too-many-ancestors, logging-format-interpolation
class SAFRSRequest(Request):
    """
    Parse jsonapi-related the request arguments:
    - header: Content-Type should be "application/vnd.api+json"
    - query args: page[limit], page[offset], fields
    - body: valid json
    """

    jsonapi_content_types = ["application/json", "application/vnd.api+json"]
    is_jsonapi = False  # indicates whether this is a jsonapi request
    _extensions = set()
    filters = {}
    filter = ""  # filter is the custom filter, used as an argument by _s_filter
    includes = []
    secure = True

    def __init__(self, *args, **kwargs):
        """
        constructor
        """
        super().__init__(*args, **kwargs)
        self.parse_content_type()
        self.parse_jsonapi_args()

    def parse_content_type(self):
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
            ext = ext.strip().split("=")
            if ext[0] == "ext" and ext[1:]:
                ext_name = ext[1]
                self._extensions.add(ext_name)

    @property
    def page_offset(self):
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

    def get_page_offset(self, rel_name):
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
    def page_limit(self):
        """
        get the page limit for the included relationship resource
        :param rel_name: name of the relationship
        :return: page limit for included resources
        """
        page_limit = self.args.get("page[limit]", get_config("DEFAULT_PAGE_LIMIT"), type=int)
        if "page[number]" in self.args and "page[size]" in self.args:
            return self.args.get("page[size]", type=int)
        return page_limit

    def get_page_limit(self, rel_name):
        page_limit = self.args.get(f"page[{rel_name}][limit]", self.page_limit, type=int)
        if "page[{rel_name}][number]" in self.args and "page[{rel_name}][size]" in self.args:
            return self.args.get("page[{rel_name}][size]", type=int)
        return page_limit

    @property
    def is_bulk(self):
        """
        jsonapi bulk extension, http://springbot.github.io/json-api/extensions/bulk/
        """
        return "bulk" in self._extensions

    def get_jsonapi_payload(self):
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
            raise ValidationError(f"Invalid JSON Payload : {result}")
        return result

    def parse_jsonapi_args(self):
        """
        parse the jsonapi request arguments:
        - page[offset]
        - page[limit]
        - filter[]
        - fields[]
        """

        self.filters = {}
        self.fields = {}

        # Parse the jsonapi filter[] and fields[] args
        for arg, val in self.args.items():
            if arg == "filter":
                self.filter = val

            filter_attr = re.search(r"filter\[(\w+)\]", arg)
            if filter_attr:
                attr_name = filter_attr.group(1)
                self.filters[attr_name] = val

            # https://jsonapi.org/format/#fetching-sparse-fieldsets
            fields_attr = re.search(r"fields\[(\w+)\]", arg)
            if fields_attr:
                field_type = fields_attr.group(1)
                self.fields[field_type] = val.split(",")

            if arg == "include":
                self.includes = val.split(",")
