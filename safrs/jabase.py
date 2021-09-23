from .base import SAFRSBase
from .util import classproperty


class JABase(SAFRSBase):
    """
    description: Stateless class example
    """

    instances = []

    _s_url = "https://safrs/.."
    _s_relationships = {}
    _s_query = None

    def __new__(cls, *args, **kwargs):
        """
        override SAFRSBase.__new__
        """
        result = object.__new__(cls)
        cls.instances.append(result)
        return result

    def __init__(self, *args, **kwargs):
        """
        Constructor
        """
        self.id = kwargs.get("id")
        # self.name = kwargs.get("name")

    @classproperty
    def s_type(cls):
        """
        Implementations should override this to provide custom types

        :return: jsonapi type string
        """
        return "JAType_" + cls.__name__

    @classmethod
    def get(cls, *args, **kwargs):
        """
        description: JA GET
        """
        return {}

    def patch(self, *args, **kwargs):
        """
        description: JA PATCH
        """
        return {}

    def delete(self):
        """
        Called for a HTTP DELETE
        """
        return None

    @property
    def jsonapi_id(self):
        return self.id

    @classmethod
    def _s_count(cls):
        """
        jsonapi response count parameter
        """
        return 0
