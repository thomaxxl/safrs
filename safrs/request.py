'''
jsonapi request
'''
import re
from werkzeug.datastructures import TypeConversionDict
from flask import Request
from .config import get_config

# pylint: disable=too-many-ancestors
class SAFRSRequest(Request):
    '''
        Parse jsonapi-related the request arguments
    '''
    page_offset = 0
    page_limit = -1
    filters = {}
    parameter_storage_class = TypeConversionDict

    def __init__(self, *args, **kwargs):
        '''
            constructor
        '''
        super().__init__(*args, **kwargs)
        self.parse_jsonapi_args()

    def parse_jsonapi_args(self):
        '''
            parse the jsonapi request arguments:
            - page[offset]
            - page[limit]
            - filter[]
            - fields[]
        '''
        self.page_limit = self.args.get('page[limit]', get_config('MAX_PAGE_LIMIT'), type=int)
        # .pop() doesn't work for TypeConversionDict, del manually
        if 'page[limit]' in self.args:
            del self.args['page[limit]']

        self.page_offset = self.args.get('page[offset]', 0, type=int)
        if 'page[offset]' in self.args:
            del self.args['page[offset]']

        self.filters = {}
        self.fields = {}
        # Parse the jsonapi filter[] and fields[] args
        for arg, val in self.args.items():
            filter_attr = re.search(r'filter\[(\w+)\]', arg)
            if filter_attr:
                col_name = filter_attr.group(1)
                if not col_name.startswith('_'): # maybe validate col_name?
                    self.filters[col_name] = val

            fields_attr = re.search(r'fields\[(\w+)\]', arg)
            if fields_attr:
                field_name = fields_attr.group(1)
                if not field_name.startswith('_'):
                    self.fields[field_name] = val
        