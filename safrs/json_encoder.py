"""
safrs to json encoding
"""
import datetime
import logging
import decimal
import json
from flask.json import JSONEncoder
from sqlalchemy.ext.declarative import DeclarativeMeta
import safrs
from .db import SAFRSBase, SAFRSDummy

class SAFRSFormattedResponse:
    """
        Custom response object
    """

    # pylint: disable=too-few-public-methods
    data = None
    meta = None
    errors = None
    result = None
    response = None

    def __init__(self, *args, **kwargs):
        """
            :param data:
            :param meta:
            :param links:
            :param errors:
            :param count:
        """
        self.response = safrs.jsonapi_format_response(*args, **kwargs)


    def to_dict(self):
        """
            create a dictionary
        """
        if not self.response is None:
            return self.response

        if not self.meta is None:
            return self.meta

        if not self.result is None:
            return {"meta": {"result": self.result}}

        return None


class SAFRSJSONEncoder(JSONEncoder):
    """
        Encodes safrs objs (SAFRSBase subclasses)
    """

    # pylint: disable=too-many-return-statements,logging-format-interpolation,protected-access,method-hidden
    def default(self, obj):
        """
            override the default json encoding
            :param obj: object to be encoded
            :return: encoded/serizlaized object
        """
        if isinstance(obj, SAFRSBase):
            result = obj._s_jsonapi_encode()
            return result
        if isinstance(obj, datetime.datetime):
            return obj.isoformat(" ")
        if isinstance(obj, datetime.date):
            return obj.isoformat()
        if isinstance(obj, SAFRSDummy):
            return {}
        if isinstance(obj, set):
            return list(obj)
        if isinstance(obj, DeclarativeMeta):
            return self.sqla_encode(obj)
        if isinstance(obj, SAFRSFormattedResponse):
            return obj.to_dict()
        if isinstance(obj, decimal.Decimal):
            return str(obj)
        if isinstance(obj, bytes):
            safrs.log.warning("bytes obj, TODO")

        # We shouldn't get here in a normal setup
        # getting here means we already abused safrs... and we're no longer jsonapi compliant
        if safrs.log.getEffectiveLevel() >= logging.INFO:
            # only continue if in debug mode
            safrs.log.warning('Unknown obj type "{}" for {}'.format(type(obj), obj))
            return {"error": "invalid object"}
        
        return self.ghetto_encode(obj)

    @staticmethod
    def ghetto_encode(obj):
        """
            if everything else failed, try to encode the public obj attributes
            i.e. those attributes without a _ prefix
            :param obj: object to be encoded
            :return: encoded/serizlaized object
        """
        try:
            result = {}
            for k, v in vars(obj).items():
                if not k.startswith("_"):
                    if isinstance(v, (int, float)) or v is None:
                        result[k] = v
                    else:
                        result[k] = str(v)
        except TypeError:
            result = str(obj)
        return result

    @staticmethod
    def sqla_encode(obj):
        """
        encode an SQLAlchemy object
        :param obj: sqlalchemy object to be encoded
        :return: encoded object
        """
        fields = {}
        for field in [x for x in dir(obj) if not x.startswith("_") and x != "metadata"]:
            data = obj.__getattribute__(field)
            try:
                # this will raise an exception if the data can't be serialized
                fields[field] = json.dumps(data)
            except TypeError:
                fields[field] = str(data)

        # a json-encodable dict
        return fields
