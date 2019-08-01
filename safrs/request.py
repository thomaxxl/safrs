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
    is_jsonapi = False
    filters = {}
    filter = ""  # filter is the custom filter, used as an argument by _s_filter

    def __init__(self, *args, **kwargs):
        """
            constructor
        """
        super().__init__(*args, **kwargs)
        if self.content_type in self.jsonapi_content_types:
            self.is_jsonapi = True
            self.parameter_storage_class = TypeConversionDict

        self.parse_jsonapi_args()

    def get_jsonapi_payload(self):
        """
            :return: jsonapi request payload
        """
        if not self.is_jsonapi:
            safrs.log.warning('Invalid Media Type! "{}"'.format(self.content_type))
            # raise('Unsupported Media Type', 415)
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
        # .pop() doesn't work for TypeConversionDict, del manually
        if "page[limit]" in self.args:
            pass
            # del self.args['page[limit]']

        self.page_offset = self.args.get("page[offset]", 0, type=int)
        if "page[offset]" in self.args:
            pass
            # del self.args['page[offset]']

        self.filters = {}
        self.fields = {}
        # Parse the jsonapi filter[] and fields[] args
        for arg, val in self.args.items():
            if arg == "filter":
                self.filter = val

            filter_attr = re.search(r"filter\[(\w+)\]", arg)
            if filter_attr:
                col_name = filter_attr.group(1)
                if not col_name.startswith("_"):  # maybe validate col_name?
                    self.filters[col_name] = val

            # https://jsonapi.org/format/#fetching-sparse-fieldsets
            fields_attr = re.search(r"fields\[(\w+)\]", arg)
            if fields_attr:
                field_type = fields_attr.group(1)
                if not val.startswith("_"):
                    self.fields[field_type] = val.split(",")
