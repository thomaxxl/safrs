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
from ._api import HTTP_METHODS


# pylint: disable=too-many-ancestors, logging-format-interpolation
class SAFRSRequest(Request):
    """
        Parse jsonapi-related the request arguments:
        - header: Content-Type should be "application/vnd.api+json"
        - query args: page[limit], page[offset], fields
        - body: valid json
    """

    jsonapi_content_types = ["application/json", "application/vnd.api+json"]
    page_offset = 0
    page_limit = 100
    is_jsonapi = False  # indicates whether this is a jsonapi request
    _extensions = set()
    filters = {}
    filter = ""  # filter is the custom filter, used as an argument by _s_filter
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
        if not isinstance(self.content_type, str):
            return

        content_type = self.content_type.split(";")[0]
        if content_type not in self.jsonapi_content_types:
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
    def is_bulk(self):
        """
            jsonapi bulk extension, http://springbot.github.io/json-api/extensions/bulk/
        """
        return "bulk" in self._extensions

    def get_jsonapi_payload(self):
        """
            :return: jsonapi request payload
        """
        if not self.is_jsonapi:
            safrs.log.warning('Invalid Media Type! "{}"'.format(self.content_type))
            # raise GenericError('Unsupported Media Type', 415)
        if self.method == "OPTIONS":
            return None
        if self.method not in HTTP_METHODS:
            abort(500)
        result = self.get_json()
        if not isinstance(result, dict):
            raise ValidationError("Invalid JSON Payload : {}".format(result))
        return result

    def parse_jsonapi_args(self):
        """
            parse the jsonapi request arguments:
            - page[offset]
            - page[limit]
            - filter[]
            - fields[]
        """
        self.page_limit = self.args.get("page[limit]", get_config("MAX_PAGE_LIMIT"), type=int)
        self.page_offset = self.args.get("page[offset]", 0, type=int)
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
