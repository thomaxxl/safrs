"""
    jsonapi_attr: custom jsonapi attributes
"""

from sqlalchemy.ext.hybrid import hybrid_property
from .swagger_doc import parse_object_doc
from typing import Any

JSONAPI_ATTR_TAG = "_s_is_jsonapi_attr"


class jsonapi_attr(hybrid_property):
    """
    hybrid_property type: sqlalchemy.orm.attributes.create_proxied_attribute.<locals>.Proxy
    """

    def __init__(self, *args, **kwargs):
        """
        :param attr: `SAFRSBase` attribute that should be exposed by the jsonapi
        :return: jsonapi attribute decorator

        set `swagger_type` and `default` to customize the swagger
        """
        setattr(self, JSONAPI_ATTR_TAG, True)  # checked by is_jsonapi_attr()

        if args:
            # called when the app starts
            attr = args[0]
            obj_doc = parse_object_doc(attr)
            if isinstance(obj_doc, dict):
                for k, v in obj_doc.items():
                    setattr(self, k, v)
        else:
            # the "default" kwarg may have been added by the obj_doc but we no longer
            # need it (and it causes an exception)
            kwargs.pop("default", None)
        super().__init__(*args, **kwargs)

    def getter(self, fget):
        """
        Provide a decorator that defines a getter method.
        """

        return self._copy(fget=fget)

    def setter(self, fset):
        """
        Provide a decorator that defines a setter method.
        """

        return self._copy(fset=fset)


def is_jsonapi_attr(attr: Any) -> bool:
    """
    :param attr: `SAFRSBase` `jsonapi_attr` decorated attribute
    :return: boolean
    """
    return getattr(attr, JSONAPI_ATTR_TAG, False) is True
