#
from functools import _lru_cache_wrapper
from typing import Callable, Union


class ClassPropertyDescriptor:
    """
    ClassPropertyDescriptor
    """

    def __init__(self, fget: classmethod, fset: None = None) -> None:
        self.fget = fget
        self.fset = fset

    def __get__(self, obj, klass=None):
        """
        __get__
        """
        if klass is None:
            klass = type(obj)
        return self.fget.__get__(obj, klass)()

    def __set__(self, obj, value):
        """
        __set__
        """
        if not self.fset:
            raise AttributeError("can't set attribute")
        type_ = type(obj)
        return self.fset.__get__(obj, type_)(value)

    def setter(self, func: Callable) -> "ClassPropertyDescriptor":
        """
        setter
        """
        if not isinstance(func, (classmethod, staticmethod)):
            func = classmethod(func)
        self.fset = func
        return self


def classproperty(func: Union[Callable, _lru_cache_wrapper]) -> ClassPropertyDescriptor:
    """
    classproperty
    """
    if not isinstance(func, (classmethod, staticmethod)):
        func = classmethod(func)

    return ClassPropertyDescriptor(func)
