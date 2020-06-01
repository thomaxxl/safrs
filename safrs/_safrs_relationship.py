from http import HTTPStatus
from .util import classproperty


# pylint: disable=too-few-public-methods
class SAFRSRelationshipObject:
    """
        Relationship object, used to emulate a SAFRSBase object for the swagger for relationship targets
    """

    _s_class_name = None
    __name__ = "name"
    http_methods = {"GET", "POST", "PATCH", "DELETE"}

    @classmethod
    def _s_get_swagger_doc(cls, http_method):
        """ Create a swagger api model based on the sqlalchemy schema
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
    def _s_relationship_names(cls):
        """
            :return: The relationship names of the target
        """
        return cls._target._s_relationship_names

    @classproperty
    def _s_jsonapi_attrs(cls):
        """
            dummy
            :return: JSON:API attributes
        """
        return {}

    @classproperty
    def _s_type(cls):
        """
            :return: JSON:API type
        """
        return cls._target._s_type

    @classproperty
    def _s_column_names(cls):
        """

        """
        return cls._target._s_column_names

    @classproperty
    def _s_class_name(cls):
        """

        """
        return cls._target.__name__
