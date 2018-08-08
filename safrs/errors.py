'''errors.py'''
# -*- coding: utf-8 -*
# Exception Handlers
#
# The application loglevel determines the level of detail dhown to the user.
# If set to debug, too much sensitive info might be shown !
#
import traceback
import logging
from sqlalchemy.exc import DontWrapMixin


class NotFoundError(Exception, DontWrapMixin):
    '''
    This exception is raised when an item was not found
    '''
    status_code = 404
    message = 'NotFoundError'

    def __init__(self, message=''):
        Exception.__init__(self)
        if LOGGER.getEffectiveLevel() == logging.DEBUG:
            self.message = message
            LOGGER.error('Not found: %s', message)

class ValidationError(Exception, DontWrapMixin):
    '''
    This exception is raised when invalid input has been detected
    '''
    status_code = 400
    message = 'Validation Error'
    def __init__(self, message=''):
        Exception.__init__(self)
        if LOGGER.getEffectiveLevel() == logging.DEBUG:
            self.message = message
            LOGGER.error('ValidationError: %s', message)
        # todo: security logging...

class GenericError(Exception, DontWrapMixin):
    '''
    This exception is raised when an error has been detected
    TODO: maybe hide error info from user
    '''
    status_code = 500
    message = 'Generic Error'
    def __init__(self, message):
        Exception.__init__(self)
        if LOGGER.getEffectiveLevel() == logging.DEBUG:
            self.message = message
        LOGGER.debug(traceback.format_exc())
        LOGGER.error('Generic Error: %s', message)

LOGGER = logging.getLogger(__name__)