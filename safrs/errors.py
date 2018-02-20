# -*- coding: utf-8 -*
# Exception Handlers
#
# The application loglevel determines the level of detail dhown to the user.
# If set to debug, too much sensitive info might be shown !
#
import traceback
import logging

from sqlalchemy.exc import DontWrapMixin
from flask_restful import abort
from flask_sqlalchemy import SQLAlchemy

class NotFoundError(Exception, DontWrapMixin):
    '''
        This exception is raised when an item was not found
    '''

    status_code = 404
    message = 'NotFoundError'

    def __init__(self, message = '', status_code=404, payload=None):
        Exception.__init__(self)
        
        if log.getEffectiveLevel() == logging.DEBUG:
        
            self.message = message
            log.error('Not found: {}'.format(message))
        


class ValidationError(Exception, DontWrapMixin):
    '''
        This exception is raised when invalid input has been detected
    '''

    status_code = 400
    message = 'Validation Error'

    def __init__(self, message = '', status_code=None, payload=None):
        Exception.__init__(self)
        if log.getEffectiveLevel() == logging.DEBUG:
            self.message = message
            log.error('ValidationError: {}'.format(message))
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
        
        if log.getEffectiveLevel() == logging.DEBUG:
            self.message = message
        
        log.debug(traceback.format_exc())
        log.error('Generic Error: {}'.format(message))

log = logging.getLogger(__name__)
