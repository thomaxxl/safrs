# -*- coding: utf-8 -*
# Exception Handlers
#
import traceback

from sqlalchemy.exc import DontWrapMixin
from flask_restful import abort

class ValidationError(Exception, DontWrapMixin):
    '''
        This exception is raised when invalid input has been detected
    '''

    status_code = 400

    def __init__(self, message = '', status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        log.error(traceback.format_exc())
        log.error('ValidationError: {}'.format(message))
        db.session.rollback()


class GenericError(Exception, DontWrapMixin):
    '''
        This exception is raised when an error has been detected

        TODO: maybe hide error info from user
    '''

    status_code = 500

    def __init__(self, message):
        Exception.__init__(self)
        self.message = message
        log.critical(traceback.format_exc())
        log.critical('Generic Error: {}'.format(message))
        db.session.rollback()
