"""
safrs_types.py
"""
import sys
import uuid
import datetime
import hashlib
import re
import json
import safrs
from sqlalchemy.types import PickleType, String
from sqlalchemy.types import TypeDecorator, BLOB
from .errors import ValidationError
from .util import classproperty

if sys.version_info[0] == 3:
    unicode = str
try:
    from validate_email import validate_email
except ModuleNotFoundError as exc:
    print("validate_email module not imported {}".format(exc))


STRIP_SPECIAL = r"[^\w|%|:|/|-|_\-_\. ]"


class JSONType(PickleType):
    """
        JSON DB type is used to store JSON objects in the database
    """

    impl = BLOB

    def __init__(self, *args, **kwargs):

        # kwargs['pickler'] = json
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
    """
        DB String Type class strips special chars when bound
    """

    impl = String(767)

    def __init__(self, *args, **kwargs):

        super(SafeString, self).__init__(*args, **kwargs)

    def process_bind_param(self, value, dialect):

        if value is not None:
            result = re.sub(STRIP_SPECIAL, "_", value)
            if str(result) != str(value):
                # log.warning('({}) Replaced {} by {}'.format(self, value, result))
                pass
        else:
            result = value

        return result


class EmailType(TypeDecorator):
    """
        DB Email Type class: validates email when bound
    """

    impl = String(767)

    def __init__(self, *args, **kwargs):

        super(EmailType, self).__init__(*args, **kwargs)

    def process_bind_param(self, value, dialect):
        if value and not validate_email(value):
            raise ValidationError("Email Validation Error {}".format(value))

        return value


class UUIDType(TypeDecorator):
    """
    UUIDType
    """

    impl = String(40)

    def __init__(self, *args, **kwargs):

        super(UUIDType, self).__init__(*args, **kwargs)

    @staticmethod
    def process_bind_param(value, dialect):

        try:
            uuid.UUID(value, version=4)
        except Exception as exc:
            raise ValidationError("UUID Validation Error {} ({})".format(value, exc))

        return value


class SAFRSID:
    """
        This class creates a jsonapi "id" from the classes PKs
        In case of a composite PK, the pks are joined with the delimiter
        eg.
        pkA = 1, pkB = 2, delimiter = '_' => jsonapi_id = '1_2'

        If you want to create a custom id_type, you can subclass SAFRSID
    """

    primary_keys = ["id"]
    columns = None
    delimiter = "_"

    def __new__(cls, id=None):

        if id is None:
            return cls.gen_id()
        else:
            return cls.validate_id(id)

    @classmethod
    def gen_id(cls):
        """
            Generate a jsonapi id
        """
        # This is the case if an autoincrement id is expected:
        if cls.columns and len(cls.columns) == 1 and cls.columns[0].type.python_type == int:
            return None

        # Some dialects support UUID
        # Maybe we should use db.UUID() instead
        return str(uuid.uuid4())

    @classmethod
    def validate_id(cls, id):
        """
            Validate a given id (eg. check if it's a valid uuid, email etc.)
        """
        result = id
        if len(cls.columns) == 1:
            try:
                result = cls.columns[0].type.python_type(id)
            except Exception:
                raise ValidationError("Invalid id: '{}'.".format(id))
        else:
            safrs.log.debug("ID Validation not implemented")

        return result

    @property
    def name(self):
        """
            name
        """
        return self.delimiter.join(self.primary_keys)

    @classmethod
    def get_id(cls, obj):
        """
            Retrieve the id string derived from the pks of obj
        """
        if cls.columns and len(cls.columns) > 1:
            values = [str(getattr(obj, pk.name)) for pk in cls.columns]
            return cls.delimiter.join(values)

        return getattr(obj, cls.primary_keys[0])

    @classmethod
    def get_pks(cls, id):
        """
            Convert the id string to a pk dict
        """
        values = str(id).split(cls.delimiter)
        result = dict()
        for pk_col, val in zip(cls.columns, values):
            if not val:
                if pk_col.type.python_type == int:
                    val = 0
            try:
                col_name = str(pk_col.name)
                result[col_name] = pk_col.type.python_type(val)
            except (ValueError, TypeError):
                # This may happen when val is empty '' or
                # if when the swagger doc is generated with default uuids
                # todo: fix
                if pk_col.default:
                    result[col_name] = pk_col.default
                else:
                    result[col_name] = ""
            except Exception:
                result[col_name] = ""

        return result

    @classproperty
    def column_names(self):
        """
            :return: a list of columns names of this id type
        """
        return [c.name for c in self.columns]

    @classmethod
    def sample_id(cls, obj):
        if cls.columns and len(cls.columns) == 1 and cls.columns[0].type.python_type == int:
            return 0

        sample = obj.query.first()
        if sample:
            return sample.jsonapi_id

        return "jsonapi_id_string"


def get_id_type(cls, Super=SAFRSID):
    """
    get_id_type
    """
    columns = [col for col in cls.__table__.columns if col.primary_key]
    primary_keys = [col.name for col in columns]
    delimiter = getattr(cls, "delimiter", "_")
    id_type_class = type(cls.__name__ + "_ID", (Super,), {"primary_keys": primary_keys, "columns": columns, "delimiter": delimiter})
    return id_type_class


class SAFRSSHA256HashID(SAFRSID):
    """
    SAFRSSHA256HashID
    """

    @classmethod
    def gen_id(cls):
        """
            Create a hash based on the current time
            This is just an example
            Not cryptographically secure and might cause collisions!
        """
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f").encode("utf-8")
        return hashlib.sha256(now).hexdigest()

    @classmethod
    def validate_id(cls, _id):
        """
        validate_id
        """
        # todo
        return _id
