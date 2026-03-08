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

    def __init__(self: Any, *args: Any, **kwargs: Any) -> None:
        """
        Initialize the response object.

        :param args: Positional arguments for response formatting
        :param kwargs: Keyword arguments for response formatting
        """
        self.response = jsonapi_format_response(*args, **kwargs)

    def to_dict(self: Any) -> Any:  # pragma: no cover
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
    @staticmethod
    def _encode_primitive(obj: Any) -> tuple[bool, Any]:
        if obj is None:
            return True, None
        if obj is Included:
            return True, Included.encode()
        if isinstance(obj, Included):
            return True, obj.encode()
        if isinstance(obj, datetime.timedelta):
            return True, str(obj)
        if isinstance(obj, datetime.datetime):
            return True, obj.isoformat(" ")
        if isinstance(obj, (datetime.date, datetime.time)):
            return True, obj.isoformat()
        if isinstance(obj, set):
            return True, list(obj)
        if isinstance(obj, UUID):  # pragma: no cover
            return True, str(obj)
        if isinstance(obj, decimal.Decimal):  # pragma: no cover
            return True, float(obj)
        if isinstance(obj, bytes):  # pragma: no cover
            if obj == b"":
                return True, ""
            safrs.log.debug("SAFRSJSONEncoder: serializing bytes obj")
            return True, obj.hex()
        return False, None

    @staticmethod
    def _encode_safrs_types(obj: Any) -> tuple[bool, Any]:
        if isinstance(obj, SAFRSBase):
            return True, obj._s_jsonapi_encode()
        if isinstance(obj, SAFRSFormattedResponse):
            return True, obj.to_dict()
        return False, None

    def _encode_debug_fallback(self, obj: Any) -> Any:
        if not is_debug():  # pragma: no cover
            safrs.log.warning(f'JSON Encoding Error: Unknown object type "{type(obj)}" for {obj}')
            return {"error": "SAFRSJSONEncoder invalid object"}
        if isinstance(obj, DeclarativeMeta):  # pragma: no cover
            return self.sqla_encode(obj)
        return self.ghetto_encode(obj)

    def default(self: Any, obj: Any) -> Any:
        """
        override the default json encoding
        :param obj: object to be encoded
        :return: encoded/serizlaized object
        """
        encoded, value = self._encode_primitive(obj)
        if encoded:
            return value
        encoded, value = self._encode_safrs_types(obj)
        if encoded:
            return value
        return self._encode_debug_fallback(obj)

    @staticmethod
    def ghetto_encode(obj: Any) -> Any:  # pragma: no cover
        """
        if everything else failed, try to encode the public obj attributes
        i.e. those attributes without a _ prefix
        :param obj: object to be encoded
        :return: encoded/serizlaized object
        """
        result: Any = {}
        try:
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
    def sqla_encode(obj: Any) -> Any:  # pragma: no cover
        """
        encode an SQLAlchemy object
        :param obj: sqlalchemy object to be encoded
        :return: encoded object
        """
        fields: dict[str, Any] = {}
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
