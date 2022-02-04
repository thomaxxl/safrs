# Exception Handlers
#
# The application loglevel determines the level of detail dhown to the user.
# If set to debug, too much sensitive info might be shown !
#
# The exceptions will be caught in http_method_decorator and formatted, for example:
# {
#      "title": "Authorization Error: ",
#      "detail": "Authorization Error: ",
#      "code": 401
# }
#
import traceback
from flask import request
from werkzeug.exceptions import NotFound
import safrs
from sqlalchemy.exc import DontWrapMixin
from http import HTTPStatus
from .config import is_debug

HIDDEN_LOG = "(debug logging disabled)"


class JsonapiError(Exception, DontWrapMixin):
    pass


class NotFoundError(JsonapiError, NotFound):
    """
    This exception is raised when an item was not found
    """

    status_code = HTTPStatus.NOT_FOUND.value
    message = "NotFoundError "

    def __init__(self, message="", status_code=HTTPStatus.NOT_FOUND.value, api_code=None):
        """
        :param message: Message to be returned in the (json) body
        :param status_code: HTTP Status code
        :param api_code: API code
        """
        JsonapiError.__init__(self)
        self.status_code = status_code
        safrs.log.error("Not found: %s", message)
        if is_debug():
            self.message += message
        else:
            self.message += HIDDEN_LOG


class UnAuthorizedError(JsonapiError):
    """
    This exception is raised when an authorization error occured
    we use FORBIDDEN(403) instead of UNAUTHORIZED(401) (old http status code descriptions were not clear)
    """

    status_code = HTTPStatus.FORBIDDEN.value
    message = "Authorization Error: "

    def __init__(self, message="", status_code=HTTPStatus.FORBIDDEN.value, api_code=None):
        Exception.__init__(self)
        self.status_code = status_code
        safrs.log.error("UnAuthorizedError: %s", message)
        if is_debug():
            self.message += message
        else:
            self.message += HIDDEN_LOG


class GenericError(JsonapiError):
    """
    This exception is raised when an error has been detected
    """

    status_code = HTTPStatus.INTERNAL_SERVER_ERROR.value  # 500
    message = "Generic Error: "

    def __init__(self, message, status_code=HTTPStatus.INTERNAL_SERVER_ERROR.value, api_code=None):
        Exception.__init__(self)
        self.status_code = status_code
        safrs.log.error("Generic Error: %s", message)
        if is_debug():
            safrs.log.info(f"Error in {request.url}")
            safrs.log.debug(traceback.format_exc(120))
            self.message += str(message)
        else:
            self.message += HIDDEN_LOG


class SystemValidationError(JsonapiError):  # pragma: no cover
    """
    This exception is raised when invalid input has been detected (server side input)
    """

    status_code = HTTPStatus.BAD_REQUEST.value
    message = "Validation Error: "

    def __init__(self, message="", status_code=HTTPStatus.BAD_REQUEST.value, api_code=None):
        Exception.__init__(self)
        self.status_code = status_code
        safrs.log.error("ValidationError: %s", message)
        if is_debug():
            self.message += message
        else:
            self.message += HIDDEN_LOG


class ValidationError(JsonapiError):
    """
    This exception is raised when invalid input has been detected (client side input)
    Always send back the message to the client in the response
    """

    status_code = HTTPStatus.BAD_REQUEST.value
    message = "Validation Error: "

    def __init__(self, message="", status_code=HTTPStatus.BAD_REQUEST.value, api_code=None):
        Exception.__init__(self)
        self.status_code = status_code
        safrs.log.warning("ValidationError: %s", message)
        self.message += message
