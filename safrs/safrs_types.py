# Some custom types for db columns and jsonapi id coding
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


STRIP_SPECIAL = r"[^\w|%|:|/|-|_\-_\. ]"


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
    parent_class = None

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
                raise ValidationError(f"Invalid id: '{id}'.")
        else:
            pass
            # safrs.log.debug("ID Validation not implemented for {}".format(cls))

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

        pk = getattr(obj, cls.primary_keys[0], None)
        if pk is None:
            pk_names = [obj.colname_to_attrname(c.name) for c in cls.columns[0].table.columns if c.primary_key]
            values = [str(getattr(obj, pk_name)) for pk_name in pk_names]
            return cls.delimiter.join(values)
        return pk

    @classmethod
    def get_pks(cls, jsonapi_id):
        """
        Convert the jsonapi_id string to a pk dict
        in case the PK is composite it consists of PKs joined by cls.delimiter
        Note: there may be an issue when the cls.delimiter is contained in an id
        :return: primary key dict
        """
        if len(cls.columns) == 1:
            values = [jsonapi_id]
        else:
            values = str(jsonapi_id).split(cls.delimiter)
        if len(values) != len(cls.columns):
            raise ValidationError(f"PK values ({values}) do not match columns ({cls.columns})")
        result = dict()
        for pk_col, val in zip(cls.columns, values):
            if not val:
                if pk_col.type.python_type == int:
                    val = 0
            try:
                col_name = str(cls.parent_class.colname_to_attrname(pk_col.name))
                result[col_name] = pk_col.type.python_type(val)
            except (ValueError, TypeError):  # pragma: no cover
                # This may happen when val is empty '' or
                # if when the swagger doc is generated with default uuids
                # todo: fix
                if pk_col.default:
                    result[col_name] = pk_col.default
                else:
                    result[col_name] = ""
            except Exception as exc:  # pragma: no cover
                safrs.log.warning(f"PK Error: {exc}")
                result[col_name] = ""

        return result

    @classproperty
    def column_names(cls):
        """
        :return: a list of columns names of this id type
        """
        return [c.name for c in cls.columns]

    @classmethod
    def extract_pks(cls, kw_dict):
        """
        Extract the primary keys from kw_dict (these are the kwargs passed to SAFRSBase.new())
        In case of composite keys we construct the jsonapi_id by using the delimiter to join the values
        :return: primary keys dict
        """
        pks = {k: str(kw_dict[k]) for k in cls.column_names}
        id = cls.delimiter.join(pks.values())
        return cls.get_pks(id)

    @classmethod
    def sample_id(cls, obj):
        if cls.columns and len(cls.columns) == 1 and cls.columns[0].type.python_type == int:
            return 0
        sample = None
        try:
            sample = obj.query.first()
        except Exception as exc:
            safrs.log.debug(exc)
            pass
        if sample:
            return sample.jsonapi_id

        return "jsonapi_id_string"


def get_id_type(cls, Super=SAFRSID, delimiter="_"):
    """
    get_id_type
    """
    primary_keys = columns = ["id"]
    if hasattr(cls, "__table__"):
        columns = [col for col in cls.__table__.columns if col.primary_key]
        primary_keys = [cls.colname_to_attrname(col.name) for col in columns]
    delimiter = getattr(cls, "_s_pk_delimiter", "_")
    id_type_class = type(
        cls.__name__ + "_ID", (Super,), {"primary_keys": primary_keys, "columns": columns, "delimiter": delimiter, "parent_class": cls}
    )
    return id_type_class


class SAFRSSHA256HashID(SAFRSID):  # pragma: no cover
    """
    SAFRSSHA256HashID class for a hash based id
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


class JSONType(PickleType):  # pragma: no cover
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


class SafeString(TypeDecorator):  # pragma: no cover
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


class UUIDType(TypeDecorator):  # pragma: no cover
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
            raise ValidationError(f"UUID Validation Error {value} ({exc})")

        return value
