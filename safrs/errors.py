"""errors.py"""
# -*- coding: utf-8 -*
# Exception Handlers
#
# The application loglevel determines the level of detail dhown to the user.
# If set to debug, too much sensitive info might be shown !
#
import traceback
import logging
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

    def __init__(self, message="", status_code=HTTPStatus.NOT_FOUND.value):
        Exception.__init__(self)
        self.status_code = status_code
        if safrs.log.getEffectiveLevel() <= logging.DEBUG:
            self.message += message
            safrs.log.error("Not found: %s", message)
        else:
            self.message += HIDDEN_LOG


class ValidationError(Exception, DontWrapMixin):
    """
    This exception is raised when invalid input has been detected
    """

    status_code = HTTPStatus.BAD_REQUEST.value
    message = "Validation Error: "

    def __init__(self, message="", status_code=HTTPStatus.BAD_REQUEST.value):
        Exception.__init__(self)
        self.status_code = status_code
        if safrs.log.getEffectiveLevel() <= logging.DEBUG:
            self.message += message
            safrs.log.error("ValidationError: %s", message)
        else:
            self.message += HIDDEN_LOG


class GenericError(Exception, DontWrapMixin):
    """
    This exception is raised when an error has been detected
    """

    status_code = 403  # HTTPStatus.INTERNAL_SERVER_ERROR.value
    message = "Generic Error: "

    def __init__(self, message, status_code=HTTPStatus.INTERNAL_SERVER_ERROR.value):
        Exception.__init__(self)
        self.status_code = status_code
        if is_debug():
            safrs.log.info("Error in {}".format(request.url))
            self.message = str(message)
        else:
            self.message += HIDDEN_LOG

        safrs.log.debug(traceback.format_exc(120))
        safrs.log.error("Generic Error: %s", message)
