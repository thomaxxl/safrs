# Exception Handlers
#
# The application loglevel determines the level of detail dhown to the user.
# If set to debug, too much sensitive info might be shown !
#
import traceback
from flask import request
import safrs
from sqlalchemy.exc import DontWrapMixin
from http import HTTPStatus
from .config import is_debug

HIDDEN_LOG = "(debug logging disabled)"


class NotFoundError(Exception, DontWrapMixin):
    """
    This exception is raised when an item was not found
    """

    status_code = HTTPStatus.NOT_FOUND.value
    message = "NotFoundError "

    def __init__(self, message="", status_code=HTTPStatus.NOT_FOUND.value, api_code=None):
        Exception.__init__(self)
        self.status_code = status_code
        safrs.log.error("Not found: %s", message)
        if is_debug():
            self.message += message
        else:
            self.message += HIDDEN_LOG


class ValidationError(Exception, DontWrapMixin):
    """
    This exception is raised when invalid input has been detected
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


class UnAuthorizedError(Exception, DontWrapMixin):
    """
    This exception is raised when an authorization error occured
    """

    status_code = HTTPStatus.UNAUTHORIZED.value
    message = "Authorization Error: "

    def __init__(self, message="", status_code=HTTPStatus.UNAUTHORIZED.value, api_code=None):
        Exception.__init__(self)
        self.status_code = status_code
        safrs.log.error("UnAuthorizedError: %s", message)
        if is_debug():
            self.message += message
        else:
            self.message += HIDDEN_LOG


class GenericError(Exception, DontWrapMixin):
    """
    This exception is raised when an error has been detected
    """

    status_code = 403  # HTTPStatus.INTERNAL_SERVER_ERROR.value
    message = "Generic Error: "

    def __init__(self, message, status_code=HTTPStatus.INTERNAL_SERVER_ERROR.value, api_code=None):
        Exception.__init__(self)
        self.status_code = status_code
        safrs.log.error("Generic Error: %s", message)
        if is_debug():
            safrs.log.info("Error in {}".format(request.url))
            safrs.log.debug(traceback.format_exc(120))
            self.message += str(message)
        else:
            self.message += HIDDEN_LOG
