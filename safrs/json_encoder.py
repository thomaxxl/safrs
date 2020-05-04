"""
safrs to json encoding
"""
import datetime
import decimal
import json
from flask.json import JSONEncoder
from sqlalchemy.ext.declarative import DeclarativeMeta
from uuid import UUID
import safrs
from .config import is_debug
from .base import SAFRSBase, Included


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
            create the response payload that will be sent to the browser
            :return: dict or None
        """
        if self.response is not None:
            return self.response

        if self.meta is not None:
            return self.meta

        if self.result is not None:
            return {"meta": {"result": self.result}}

        return None


class SAFRSJSONEncoder(JSONEncoder):
    """
        Encodes safrs objs (SAFRSBase subclasses)
    """

    # pylint: disable=too-many-return-statements,logging-format-interpolation
    # pylint: disable=arguments-differ,protected-access,method-hidden
    def default(self, obj, **kwargs):
        """
            override the default json encoding
            :param obj: object to be encoded
            :return: encoded/serizlaized object
        """
        if obj is Included:
            return Included.encode()
        if isinstance(obj, Included):
            result = obj.encode()
            return result
        if isinstance(obj, SAFRSBase):
            result = obj._s_jsonapi_encode()
            return result
        if isinstance(obj, datetime.datetime):
            return obj.isoformat(" ")
        if isinstance(obj, (datetime.date, datetime.time)):
            return obj.isoformat()
        if isinstance(obj, set):
            return list(obj)
        if isinstance(obj, DeclarativeMeta):
            return self.sqla_encode(obj)
        if isinstance(obj, SAFRSFormattedResponse):
            return obj.to_dict()
        elif isinstance(obj, UUID):  # pragma: no cover
            return str(obj)
        if isinstance(obj, decimal.Decimal):  # pragma: no cover
            return str(obj)
        if isinstance(obj, bytes):  # pragma: no cover
            safrs.log.warning("bytes obj, override SAFRSJSONEncoder")
            return obj.hex()

        # We shouldn't get here in a normal setup
        # getting here means we already abused safrs... and we're no longer jsonapi compliant
        if not is_debug():  # pragma: no cover
            # only continue if in debug mode
            safrs.log.warning('JSON Encoding Error: Unknown object type "{}" for {}'.format(type(obj), obj))
            return {"error": "SAFRSJSONEncoder invalid object"}

        return self.ghetto_encode(obj)

    @staticmethod
    def ghetto_encode(obj):  # pragma: no cover
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

    # pragma: no cover
    @staticmethod
    def sqla_encode(obj):  # pragma: no cover
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
