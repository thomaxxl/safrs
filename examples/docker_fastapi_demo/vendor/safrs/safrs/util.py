#
from typing import Any


class ClassPropertyDescriptor:
    """
    ClassPropertyDescriptor
    """

    def __init__(self: Any, fget: Any, fset: Any=None) -> None:
        self.fget = fget
        self.fset = fset

    def __get__(self: Any, obj: Any, klass: Any=None) -> Any:
        """
        __get__
        """
        if klass is None:
            klass = type(obj)
        return self.fget.__get__(obj, klass)()

    def __set__(self: Any, obj: Any, value: Any) -> Any:
        """
        __set__
        """
        if not self.fset:
            raise AttributeError("can't set attribute")
        type_ = type(obj)
        return self.fset.__get__(obj, type_)(value)

    def setter(self: Any, func: Any) -> "ClassPropertyDescriptor":
        """
        setter
        """
        if not isinstance(func, (classmethod, staticmethod)):
            func = classmethod(func)
        self.fset = func
        return self


def classproperty(func: Any) -> ClassPropertyDescriptor:
    """
    classproperty
    """
    if not isinstance(func, (classmethod, staticmethod)):
        func = classmethod(func)

    return ClassPropertyDescriptor(func)
