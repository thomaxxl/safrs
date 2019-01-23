'''
safrs to json encoding
'''
from flask.json import JSONEncoder
from .db import SAFRSBase
import safrs
import datetime
import logging


class SAFRSFormattedResponse:
    '''
        Custom response object
    '''

    data = None
    meta = None
    errors = None
    result = None
    response = None

    def to_dict(self):

        if not self.response is None:
            return self.response

        if not self.meta is None:
            return self.meta

        if not self.result is None:
            return {'meta' : {'result' : self.result}}



class SAFRSJSONEncoder(JSONEncoder):
    '''
        Encodes safrs objects (SAFRSBase subclasses)
    '''

    def default(self, object):
        if isinstance(object, SAFRSBase):
            result = object._s_jsonapi_encode()
            return result
        if isinstance(object, datetime.datetime):
            return object.isoformat(' ')
        if isinstance(object, datetime.date):
            return object.isoformat()
        # We shouldn't get here in a normal setup
        # getting here means we already abused safrs... and we're no longer jsonapi compliant
        if isinstance(object, set):
            return list(object)
        if isinstance(object, DeclarativeMeta):
            return self.sqla_encode(object)
        if isinstance(object, SAFRSFormattedResponse):
            return object.to_dict()
        if isinstance(object, SAFRSFormattedResponse):
            return object.to_dict()
        if isinstance(object, decimal.Decimal):
            return str(object)
        if isinstance(object, bytes):
            safrs.LOGGER.warning('bytes object, TODO')

        else:
            safrs.LOGGER.warning('Unknown object type "{}" for {}'.format(type(object), object))
        return self.ghetto_encode(object)

    def ghetto_encode(self, object):
        '''
            ghetto_encode : if everything else failed, try to encode the public object attributes
            i.e. those attributes without a _ prefix
        '''
        try:
            result = {}
            for k, v in vars(object).items():
                if not k.startswith('_'):
                    if isinstance(v, (int, float, )) or v is None:
                        result[k] = v
                    else:
                        result[k] = str(v)
        except TypeError:
            result = str(object)
        return result

    def sqla_encode(self, obj):
        '''
        sqla_encode
        '''
        fields = {}
        for field in [x for x in dir(obj) if not x.startswith('_') and x != 'metadata']:
            data = obj.__getattribute__(field)
            try:
                # this will raise an exception if the data can't be serialized
                fields[field] = json.dumps(data)
            except TypeError:
                fields[field] = str(data)

        # a json-encodable dict
        return fields


    
