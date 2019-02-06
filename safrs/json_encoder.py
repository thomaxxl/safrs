'''
safrs to json encoding
'''
from flask.json import JSONEncoder
from sqlalchemy.ext.declarative import DeclarativeMeta
from .db import SAFRSBase, SAFRSDummy
import safrs
import datetime
import logging
import decimal


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
        '''
            create a dictionary
        '''
        if not self.response is None:
            return self.response

        if not self.meta is None:
            return self.meta

        if not self.result is None:
            return {'meta' : {'result' : self.result}}


class SAFRSJSONEncoder(JSONEncoder):
    '''
        Encodes safrs objs (SAFRSBase subclasses)
    '''

    def default(self, obj):
        '''
            called by default
            :param obj: object to be encoded
            :return: encoded/serizlaized object
        '''
        if isinstance(obj, SAFRSBase):
            result = obj._s_jsonapi_encode()
            return result
        if isinstance(obj, datetime.datetime):
            return obj.isoformat(' ')
        if isinstance(obj, datetime.date):
            return obj.isoformat()
        if isinstance(obj, SAFRSDummy):
            return {}
        # We shouldn't get here in a normal setup
        # getting here means we already abused safrs... and we're no longer jsonapi compliant
        if safrs.log.getEffectiveLevel() >= logging.INFO: # only continue if in debug mode
            safrs.log.warning('Unknown obj type "{}" for {}'.format(type(obj), obj))
            return {"error" : "invalid object"}
        if isinstance(obj, set):
            return list(obj)
        if isinstance(obj, DeclarativeMeta):
            return self.sqla_encode(obj)
        if isinstance(obj, SAFRSFormattedResponse):
            return obj.to_dict()
        if isinstance(obj, SAFRSFormattedResponse):
            return obj.to_dict()
        if isinstance(obj, decimal.Decimal):
            return str(obj)
        if isinstance(obj, bytes):
            safrs.log.warning('bytes obj, TODO')

        else:
            safrs.log.warning('Unknown obj type "{}" for {}'.format(type(obj), obj))
        return self.ghetto_encode(obj)

    def ghetto_encode(self, obj):
        '''
            if everything else failed, try to encode the public obj attributes
            i.e. those attributes without a _ prefix
            :param obj: object to be encoded
            :return: encoded/serizlaized object
        '''
        try:
            result = {}
            for k, v in vars(obj).items():
                if not k.startswith('_'):
                    if isinstance(v, (int, float, )) or v is None:
                        result[k] = v
                    else:
                        result[k] = str(v)
        except TypeError:
            result = str(obj)
        return result

    def sqla_encode(self, obj):
        '''
        encode an SQLAlchemy object
        :param obj: sqlalchemy object to be encoded
        :return: encoded object
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
