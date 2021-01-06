from http import HTTPStatus
from .util import classproperty


# pylint: disable=too-few-public-methods
class SAFRSRelationshipObject:
    """
    Relationship object, used to emulate a SAFRSBase object for the swagger for relationship targets
    so we can call the same methods on a relationship target as we do when using SAFRSBase
    """

    _s_class_name = None
    __name__ = "name"
    http_methods = {"GET", "POST", "PATCH", "DELETE"}
    swagger_models = {"instance": None, "collection": None}

    @classmethod
    def _s_get_swagger_doc(cls, http_method):
        """Create a swagger api model based on the sqlalchemy schema
        if an instance exists in the DB, the first entry is used as example
        :param http_method: HTTP method for which to generate the doc
        :return: swagger body, responses
        """
        body = {}
        responses = {}
        object_name = cls.__name__

        object_model = {}
        responses = {str(HTTPStatus.OK.value): {"description": "{} object".format(object_name), "schema": object_model}}

        if http_method.upper() in ("POST", "GET"):
            responses = {
                str(HTTPStatus.OK.value): {"description": HTTPStatus.OK.description},
                str(HTTPStatus.NOT_FOUND.value): {"description": HTTPStatus.NOT_FOUND.description},
            }

        return body, responses

    @classproperty
    def _s_relationships(cls):
        """
        :return: The relationship names of the target
        """
        return cls._target._s_relationships

    @classproperty
    def _s_jsonapi_attrs(cls):
        """
        :return: target JSON:API attributes
        """
        return cls._target._s_jsonapi_attrs

    @classproperty
    def _s_type(cls):
        """
        :return: JSON:API type
        """
        return cls._target._s_type

    @classproperty
    def _s_class_name(cls):
        """
        :return: name of the target class
        """
        return cls._target.__name__
