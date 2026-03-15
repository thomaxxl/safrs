"""
    jsonapi_attr: custom jsonapi attributes
"""

from sqlalchemy.ext.hybrid import hybrid_property
from .api_doc import parse_object_doc
from typing import Any

JSONAPI_ATTR_TAG = "_s_is_jsonapi_attr"
JSONAPI_ATTR_METADATA_TAG = "_s_jsonapi_attr_metadata_keys"
_HYBRID_PROPERTY_KWARGS = {"fget", "fset", "fdel", "expr", "custom_comparator", "update_expr"}


class _JSONAPIAttrProperty(hybrid_property):
    """
    hybrid_property type: sqlalchemy.orm.attributes.create_proxied_attribute.<locals>.Proxy
    """

    def __init__(self: Any, *args: Any, **kwargs: Any) -> None:
        """
        :param attr: `SAFRSBase` attribute that should be exposed by the jsonapi
        :return: jsonapi attribute decorator

        set `swagger_type` and `default` to customize the swagger
        """
        setattr(self, JSONAPI_ATTR_TAG, True)  # checked by is_jsonapi_attr()

        doc_metadata = {}
        if args:
            # called when the app starts
            attr = args[0]
            obj_doc = parse_object_doc(attr)
            if isinstance(obj_doc, dict):
                for k, v in obj_doc.items():
                    doc_metadata[k] = v
        for key in list(kwargs):
            if key not in _HYBRID_PROPERTY_KWARGS:
                doc_metadata[key] = kwargs.pop(key)
        super().__init__(*args, **kwargs)
        setattr(self, JSONAPI_ATTR_METADATA_TAG, set(doc_metadata))
        for key, value in doc_metadata.items():
            setattr(self, key, value)

    def _copy(self: Any, **kwargs: Any) -> Any:
        clone = super()._copy(**kwargs)
        setattr(clone, JSONAPI_ATTR_TAG, True)
        metadata_keys = set(getattr(self, JSONAPI_ATTR_METADATA_TAG, set()))
        setattr(clone, JSONAPI_ATTR_METADATA_TAG, metadata_keys)
        for key in metadata_keys:
            if hasattr(self, key):
                setattr(clone, key, getattr(self, key))
        return clone

    def getter(self: Any, fget: Any) -> Any:
        """
        Provide a decorator that defines a getter method.
        """

        return self._copy(fget=fget)

    def setter(self: Any, fset: Any) -> Any:
        """
        Provide a decorator that defines a setter method.
        """

        return self._copy(fset=fset)


def jsonapi_attr(*args: Any, **kwargs: Any) -> Any:
    if args and callable(args[0]):
        return _JSONAPIAttrProperty(*args, **kwargs)

    def _decorator(fget: Any) -> Any:
        return _JSONAPIAttrProperty(fget, **kwargs)

    return _decorator


def is_jsonapi_attr(attr: Any) -> bool:
    """
    :param attr: `SAFRSBase` `jsonapi_attr` decorated attribute
    :return: boolean
    """
    return getattr(attr, JSONAPI_ATTR_TAG, False) is True


def jsonapi_attr_is_write_only(attr: Any) -> bool:
    return is_jsonapi_attr(attr) and bool(getattr(attr, "write_only", False))


def jsonapi_attr_is_read_only(attr: Any) -> bool:
    if not is_jsonapi_attr(attr):
        return False
    if bool(getattr(attr, "read_only", False)):
        return True
    return getattr(attr, "fset", None) is None


def lookup_jsonapi_attr(owner: Any, attr_name: str) -> Any:
    """
    Resolve an effective jsonapi_attr on ``owner`` using normal MRO shadowing rules.
    """
    cls = owner if isinstance(owner, type) else owner.__class__
    for base in cls.__mro__:
        candidate = base.__dict__.get(attr_name)
        if candidate is None:
            continue
        if is_jsonapi_attr(candidate):
            return candidate
        return None
    return None


def get_jsonapi_attrs(owner: Any) -> dict[str, Any]:
    """
    Collect visible jsonapi_attr definitions for ``owner`` across its MRO.
    """
    cls = owner if isinstance(owner, type) else owner.__class__
    visible_attrs: dict[str, Any] = {}
    for base in cls.__mro__:
        for attr_name, attr_value in base.__dict__.items():
            if attr_name not in visible_attrs:
                visible_attrs[attr_name] = attr_value
    return {attr_name: attr_value for attr_name, attr_value in visible_attrs.items() if is_jsonapi_attr(attr_value)}
