from typing import Any
from .base import SAFRSBase
from .util import classproperty


class JABase(SAFRSBase):
    """
    description: Stateless class example
    """

    instances: list[Any] = []

    _s_url = "https://safrs/.."
    _s_relationships: dict[str, Any] = {}
    _s_query = None

    def __new__(cls: Any, *args: Any, **kwargs: Any) -> Any:
        """
        override SAFRSBase.__new__
        """
        result = object.__new__(cls)
        cls.instances.append(result)
        return result

    def __init__(self: Any, *args: Any, **kwargs: Any) -> None:
        """
        Constructor
        """
        self.id = kwargs.get("id")
        # self.name = kwargs.get("name")

    @classproperty
    def s_type(cls: Any) -> Any:
        """
        Implementations should override this to provide custom types

        :return: jsonapi type string
        """
        return "JAType_" + cls.__name__

    @classmethod
    def get(cls: Any, *args: Any, **kwargs: Any) -> Any:
        """
        description: JA GET
        """
        return {}

    def patch(self: Any, *args: Any, **kwargs: Any) -> Any:
        """
        description: JA PATCH
        """
        return {}

    def delete(self: Any) -> Any:
        """
        Called for a HTTP DELETE
        """
        return None

    @property
    def jsonapi_id(self: Any) -> Any:
        return self.id

    @classmethod
    def _s_count(cls: Any) -> Any:
        """
        jsonapi response count parameter
        """
        return 0
