from http import HTTPStatus
from typing import Dict, Tuple, Any
from .util import classproperty


# pylint: disable=too-few-public-methods
class SAFRSRelationshipObject:
    """
    Relationship object, used to emulate a SAFRSBase object for the swagger for relationship targets
    so we can call the same methods on a relationship target as we do when using SAFRSBase.
    """

    _s_class_name: str = None
    __name__: str = "name"
    http_methods: set = {"GET", "POST", "PATCH", "DELETE"}
    swagger_models: Dict[str, Any] = {"instance": None, "collection": None}

    @classmethod
    def _s_get_swagger_doc(cls, http_method: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Create a swagger API model based on the SQLAlchemy schema.
        If an instance exists in the DB, the first entry is used as an example.

        :param http_method: HTTP method for which to generate the doc
        :return: Tuple containing the swagger body and responses
        """
        body: Dict[str, Any] = {}
        responses: Dict[str, Any] = {}
        object_name: str = cls.__name__

        object_model: Dict[str, Any] = {}
        responses = {str(HTTPStatus.OK.value): {"description": f"{object_name} object", "schema": object_model}}

        if http_method.upper() in {"POST", "GET"}:
            responses = {
                str(HTTPStatus.OK.value): {"description": HTTPStatus.OK.description},
                str(HTTPStatus.NOT_FOUND.value): {"description": HTTPStatus.NOT_FOUND.description},
            }

        return body, responses

    @classproperty
    def _s_relationships(cls) -> Any:
        """
        :return: The relationship names of the target
        """
        return cls._target._s_relationships

    @classproperty
    def _s_jsonapi_attrs(cls) -> Any:
        """
        :return: Target JSON:API attributes
        """
        return cls._target._s_jsonapi_attrs

    @classproperty
    def _s_type(cls) -> str:
        """
        :return: JSON:API type
        """
        return cls._target._s_type

    @classproperty
    def _s_class_name(cls) -> str:
        """
        :return: Name of the target class
        """
        return cls._target.__name__
