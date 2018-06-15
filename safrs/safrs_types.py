import sys
if sys.version_info[0] == 3:
    unicode = str
from safrs.errors import ValidationError
from sqlalchemy.types import PickleType, Text, String, Integer, DateTime, TypeDecorator, Integer, BLOB
import uuid, datetime, hashlib, re

try:
    from validate_email import validate_email
except:
    pass


STRIP_SPECIAL = '[^\w|%|:|/|-|_\-_\. ]'


class JSONType(PickleType):
    '''
        JSON DB type is used to store JSON objects in the database
    '''

    impl = BLOB

    def __init__(self, *args, **kwargs):        
        
        #kwargs['pickler'] = json
        super(JSONType, self).__init__(*args, **kwargs)

    def process_bind_param(self, value, dialect):
        
        if value is not None:
            value = json.dumps(value, ensure_ascii=True)
        return value

    def process_result_value(self, value, dialect):

        if value is not None:
            value = json.loads(value)
        return value


class SafeString(TypeDecorator):
    '''
        DB String Type class strips special chars when bound
    '''

    impl = String(767)

    def __init__(self, *args, **kwargs):

        super(SafeString, self).__init__(*args, **kwargs)     

    def process_bind_param(self, value, dialect):
        
        if value != None:
            result = re.sub(STRIP_SPECIAL, '_', value)
            if str(result) != str(value):
                #log.warning('({}) Replaced {} by {}'.format(self, value, result))
                pass
        else:
            result = value

        return result


class EmailType(TypeDecorator):
    '''
        DB Email Type class: validates email when bound
    '''

    impl = String(767)

    def __init__(self, *args, **kwargs):

        super(EmailType, self).__init__(*args, **kwargs)     

    def process_bind_param(self, value, dialect):
        if value and not validate_email(value):
            raise ValidationError('Email Validation Error {}'.format(value))

        return value

class UUIDType(TypeDecorator):

    impl = String(40)

    def __init__(self, *args, **kwargs):

        super(UUIDType, self).__init__(*args, **kwargs)     

    def process_bind_param(self, value, dialect):

        try:
            UUID(value, version=4)
        except:
            raise ValidationError('UUID Validation Error {}'.format(value))

        return value


class SAFRSID(object):
    '''
        - gen_id
        - validate_id
    '''

    def __new__(cls, id = None):
        
        if id == None:
            return cls.gen_id()
        else:
            return cls.validate_id(id)

    @classmethod
    def gen_id(cls):
        return str(uuid.uuid4())

    @classmethod
    def validate_id(cls, id):
        try:
            uuid.UUID(id, version=4)
            return id
        except:
            raise ValidationError('Invalid ID')


class SAFRSSHA256HashID(SAFRSID):

    @classmethod
    def gen_id(self):
        '''
            Create a hash based on the current time
            This is just an example 
            Not cryptographically secure and might cause collisions!
        '''
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f").encode('utf-8')
        return hashlib.sha256(now).hexdigest()

    @classmethod
    def validate_id(self, id):
        # todo
        pass

