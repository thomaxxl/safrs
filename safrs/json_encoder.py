# safrs to json encoding

import datetime
import decimal
import json
from flask.json.provider import DefaultJSONProvider
from sqlalchemy.ext.declarative import DeclarativeMeta
from uuid import UUID
import safrs
from .config import is_debug
from .base import SAFRSBase, Included
from .jsonapi_formatting import jsonapi_format_response
from typing import Any


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

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Initialize the response object.

        :param args: Positional arguments for response formatting
        :param kwargs: Keyword arguments for response formatting
        """
        self.response = jsonapi_format_response(*args, **kwargs)

    def to_dict(self):  # pragma: no cover
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


class _SAFRSJSONEncoder:
    """
    JSON encoding for safrs objects (SAFRSBase subclasses and common types)
    """

    # pylint: disable=too-many-return-statements,logging-format-interpolation
    # pylint: disable=arguments-differ,protected-access,method-hidden
    def default(self, obj, **kwargs):
        """
        override the default json encoding
        :param obj: object to be encoded
        :return: encoded/serizlaized object
        """
        if obj is None:
            return None
        if obj is Included:
            return Included.encode()
        if isinstance(obj, Included):
            result = obj.encode()
            return result
        if isinstance(obj, datetime.timedelta):
            return str(obj)
        if isinstance(obj, SAFRSBase):
            result = obj._s_jsonapi_encode()
            return result
        if isinstance(obj, datetime.datetime):
            return obj.isoformat(" ")
        if isinstance(obj, (datetime.date, datetime.time)):
            return obj.isoformat()
        if isinstance(obj, set):
            return list(obj)
        if isinstance(obj, SAFRSFormattedResponse):
            return obj.to_dict()
        if isinstance(obj, UUID):  # pragma: no cover
            return str(obj)
        if isinstance(obj, decimal.Decimal):  # pragma: no cover
            return float(obj)
        if isinstance(obj, bytes):  # pragma: no cover
            if obj == b"":
                return ""
            safrs.log.debug("SAFRSJSONEncoder: serializing bytes obj")
            return obj.hex()

        # We shouldn't get here in a normal setup
        # getting here means we already abused safrs... and we're no longer jsonapi compliant
        if not is_debug():  # pragma: no cover
            # only continue if in debug mode
            safrs.log.warning(f'JSON Encoding Error: Unknown object type "{type(obj)}" for {obj}')
            return {"error": "SAFRSJSONEncoder invalid object"}

        if isinstance(obj, DeclarativeMeta):  # pragma: no cover
            return self.sqla_encode(obj)

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


class SAFRSJSONProvider(_SAFRSJSONEncoder, DefaultJSONProvider):
    """
    Flask JSON encoding
    """

    mimetype = "application/vnd.api+json"


class SAFRSJSONEncoder(_SAFRSJSONEncoder, json.JSONEncoder):
    """
    Common JSON encoding
    """

    pass
