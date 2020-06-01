# -*- coding: utf-8 -*-
# base.py: implements the SAFRSBase SQLAlchemy db Mixin and related operations
#
# SQLAlchemy database schemas
# pylint: disable=logging-format-interpolation,no-self-argument,no-member,line-too-long,fixme,protected-access
#
import inspect
import datetime
import sqlalchemy
import json
from http import HTTPStatus
from urllib.parse import urljoin
from flask import request, url_for, has_request_context, current_app
from flask_sqlalchemy import Model
from sqlalchemy.orm.session import make_transient
from sqlalchemy import inspect as sqla_inspect
from sqlalchemy.orm.interfaces import ONETOMANY, MANYTOONE, MANYTOMANY
from sqlalchemy.ext.hybrid import hybrid_method, hybrid_property
from sqlalchemy.sql.schema import Column

# safrs dependencies:
import safrs
from .swagger_doc import get_doc, parse_object_doc
from .errors import GenericError, NotFoundError, ValidationError
from .safrs_types import get_id_type
from .util import classproperty
from .config import get_config

#
# Map SQLA types to swagger2 json types
# json supports only a couple of basic data types, which makes our job pretty easy :)
# If a type isn't found in the table, "string" will be used
# (because of this we could actually remove all the "string" types as well)
#
SQLALCHEMY_SWAGGER2_TYPE = {
    "INTEGER": "integer",
    "SMALLINT": "integer",
    "NUMERIC": "number",
    "DECIMAL": "integer",
    "VARCHAR": "string",
    "TEXT": "string",
    "DATE": "string",
    "BOOLEAN": "boolean",
    "BLOB": "string",
    "BYTEA": "string",
    "BINARY": "string",
    "VARBINARY": "string",
    "FLOAT": "number",
    "REAL": "number",
    "DATETIME": "string",
    "BIGINT": "integer",
    "ENUM": "string",
    "INTERVAL": "string",
    "CHAR": "string",
    "TIMESTAMP": "string",
    "TINYINT": "integer",
    "MEDIUMINT": "integer",
    "NVARCHAR": "string",
    "YEAR": "integer",
    "SET": "string",
    "LONGBLOB": "string",
    "TINYTEXT": "string",
    "LONGTEXT": "string",
    "MEDIUMTEXT": "string",
    "UUID": "string",
    "TIME": "string",
}
# casting of swagger types to python types
SWAGGER2_TYPE_CAST = {"integer": int, "string": str, "number": float, "boolean": bool}
JSONAPI_ATTR_TAG = "_s_is_jsonapi_attr"


class jsonapi_attr(hybrid_property):
    """
       hybrid_property type: sqlalchemy.orm.attributes.create_proxied_attribute.<locals>.Proxy
    """

    def __init__(self, *args, **kwargs):
        """
            :param attr: `SAFRSBase` attribute that should be exposed by the jsonapi
            :return: jsonapi attribute decorator

            set `swagger_type` and `default` to customize the swagger
        """
        if args:
            # called when the app starts
            attr = args[0]
            setattr(self, JSONAPI_ATTR_TAG, True)
            obj_doc = parse_object_doc(attr)
            if isinstance(obj_doc, dict):
                for k, v in obj_doc.items():
                    setattr(self, k, v)
        else:
            # the "default" kwarg may have been added by the obj_doc but we no longer
            # need it (and it causes an exception)
            kwargs.pop("default", None)
        super().__init__(*args, **kwargs)

    def setter(self, value):
        safrs.log.debug("Empty '{}' jsonapi_attr setter".format(self.__name__))


def is_jsonapi_attr(attr):
    """
        :param attr: `SAFRSBase` `jsonapi_attr` decorated attribute
        :return: boolean
    """
    return getattr(attr, JSONAPI_ATTR_TAG, False) is True


#
# SAFRSBase superclass
#
class SAFRSBase(Model):
    """ This SQLAlchemy mixin implements Json Serialization for SAFRS SQLalchemy Persistent Objects
        Serialization itself is performed by the ``to_dict`` method
        Initialization and instantiation are quite complex because we rely on the DB schema

        The jsonapi id is generated from the primary keys of the columns

        This class is mostly used as a sqla model mixin therefore the object attributes should not
        match column names or sqla attribute names, this is why most of the methods & properties have
        (or should have, hindsight is great :/) the distinguishing `_s_` prefix
    """

    query_limit = 50
    db_commit = True  # commit instances automatically, see also _s_auto_commit property below
    http_methods = {"GET", "POST", "PATCH", "DELETE", "PUT"}  # http methods, used in case of override
    url_prefix = ""
    allow_client_generated_ids = False  # Indicates whether the client is allowed to create the id

    exclude_attrs = []  # list of attribute names that should not be serialized
    exclude_rels = []  # list of relationship names that should not be serialized

    # The swagger models are kept here, this lookup table will be used when the api swagger is generated
    # on startup
    swagger_models = {"instance": None, "collection": None}

    _s_expose = True  # indicates we want to expose this (see _s_check_perms)

    def __new__(cls, **kwargs):
        """
            If an object with given arguments already exists, this object is instantiated
        """
        # Fetch the PKs from the kwargs so we can lookup the corresponding object
        primary_keys = cls.id_type.get_pks(kwargs.get("id", ""))
        # Lookup the object with the PKs
        instance = cls._s_query.filter_by(**primary_keys).one_or_none()
        if not instance:
            instance = object.__new__(cls)

        return instance

    def __init__(self, *args, **kwargs):
        """
            Object initialization:
            - set the named attributes and add the object to the database
            - create relationships
        """
        # All SAFRSBase subclasses have an id,
        # if no id is supplied, generate a new safrs id (uuid4)
        # instantiate the id with the "id_type", this will validate the id if
        # validation is implemented
        kwargs["id"] = self.id_type(kwargs.get("id", None))

        # Initialize the attribute values: these have been passed as key-value pairs in the
        # kwargs dictionary (from json in case of a web request).
        # Retrieve the values from each attribute (== class table column)
        db_args = {}
        for column_name in self._s_column_names:
            if column_name in kwargs:
                attr_val = self._s_parse_attr_value(column_name, kwargs.get(column_name))
                db_args[column_name] = attr_val

        # Add the related instances
        for rel_name in self._s_relationship_names:
            if rel_name in kwargs:
                rel_attr = kwargs.get(rel_name)
                db_args[rel_name] = rel_attr

        # db_args now contains the class attributes. Initialize the DB model with them
        # All subclasses should have the DB.Model as superclass.
        # (SQLAlchemy doesn't work when using DB.Model as SAFRSBase superclass)
        try:
            safrs.DB.Model.__init__(self, **db_args)
        except Exception as exc:
            # OOPS .. things are going bad, this might happen using sqla automap
            safrs.log.error("Failed to instantiate {}".format(self))
            safrs.log.debug("db args: {}".format(db_args))
            safrs.log.exception(exc)
            safrs.DB.Model.__init__(self)

        if self._s_auto_commit:
            # Add the object to the database if specified by the class parameters
            safrs.DB.session.add(self)
            try:
                safrs.DB.session.commit()
            except sqlalchemy.exc.SQLAlchemyError as exc:
                # Exception may arise when a DB constrained has been violated (e.g. duplicate key)
                raise GenericError(exc)

    @classmethod
    def _s_post(cls, **attributes):
        """
            This method is called when a new item is created with a POST to the json api

            :param attributes: the jsonapi "data" attributes
            :return: new `cls` instance

            `_s_post` performs attribute sanitization and calls `cls.__init__`
            The attributes may contain an "id" if `cls.allow_client_generated_ids` is True
        """
        # Remove 'id' (or other primary keys) from the attributes, unless it is allowed by the
        # SAFRSObject allow_client_generated_ids attribute
        for col_name in cls.id_type.column_names:
            attributes.pop(col_name, None)

        # remove attributes that are not declared in _s_jsonapi_attrs
        attributes = {attr_name: attributes[attr_name] for attr_name in attributes if attr_name in cls._s_jsonapi_attrs}

        if getattr(cls, "allow_client_generated_ids", False) is True:
            # todo, this isn't required per the jsonapi spec, doesn't work well and isn't documented, maybe later
            id = attributes.get("data", {}).get("id")
            # cls.id_type.get_pks(id)
            attributes["id"] = id

        # Create the object instance with the specified id and json data
        # If the instance (id) already exists, it will be updated with the data
        # pylint: disable=not-callable
        instance = cls(**attributes)

        if not instance._s_auto_commit:
            #
            # The item has not yet been added/commited by the SAFRSBase,
            # in that case we have to do it ourselves
            #
            safrs.DB.session.add(instance)
            try:
                safrs.DB.session.commit()
            except sqlalchemy.exc.SQLAlchemyError as exc:  # pragma: no cover
                # Exception may arise when a db constraint has been violated
                # (e.g. duplicate key)
                safrs.log.warning(str(exc))
                raise GenericError(str(exc))

        return instance

    def __setattr__(self, attr_name, attr_val):
        """
            setattr behaves differently for `jsonapi_attr` decorated attributes
        """
        if is_jsonapi_attr(getattr(self.__class__, attr_name, False)):
            getattr(self.__class__, attr_name).setter(attr_val)
        else:
            super().__setattr__(attr_name, attr_val)

    def _s_patch(self, **attributes):
        """
            update the object attributes
            :param **attributes:
        """
        for attr_name, attr_val in attributes.items():
            if attr_name not in self.__class__._s_jsonapi_attrs:
                continue
            _ = self._s_parse_attr_value(attr_name, attr_val)
            # check if write permission is set
            if self._s_check_perm(attr_name, "w"):
                setattr(self, attr_name, attr_val)

    def _s_clone(self, **kwargs):
        """
            Clone an object: copy the parameters and create a new id
            :param *kwargs: TBD
        """
        make_transient(self)
        # pylint: disable=attribute-defined-outside-init
        self.id = self.id_type()
        for parameter in self._s_jsonapi_attrs:
            value = kwargs.get(parameter, None)
            if value is not None:
                setattr(self, parameter, value)
        safrs.DB.session.add(self)
        if self._s_auto_commit:
            safrs.DB.session.commit()
        return self

    def _s_parse_attr_value(self, attr_name, attr_val):
        """
            Parse the given jsonapi attribute value so it can be stored in the db
            :param attr_name: attribute name
            :param attr_val: attribute value
            :return: parsed value
        """
        # Don't allow attributes from web requests that are not specified in _s_jsonapi_attrs
        if not has_request_context():
            # we only care about parsing when working in the request context
            return attr_val

        if attr_name == "id":
            return attr_val

        attr = self.__class__._s_jsonapi_attrs.get(attr_name, None)
        if attr is None:
            raise ValidationError("Invalid attribute {}".format(attr_name))

        if is_jsonapi_attr(attr):
            return attr_val

        # attr is a sqlalchemy.sql.schema.Column now
        if not isinstance(attr, Column):
            raise ValidationError("Not a column")

        if attr_val is None and attr.default:
            attr_val = attr.default.arg
            return attr_val

        if attr_val is None:
            return attr_val

        if getattr(attr, "python_type", None):
            """
                It's possible for a column to specify a custom python_type to use for deserialization
            """
            attr_val = attr.python_type(attr_val)

        try:
            attr.type.python_type
        except NotImplementedError as exc:
            """
                This happens when a custom type has been implemented, in which case the user/dev should know how to handle it:
                override this method and implement the parsing
                https://docs.python.org/2/library/exceptions.html#exceptions.NotImplementedError :
                In user defined base classes, abstract methods should raise this exception when they require derived classes to override the method.
                => simply return the attr_val for user-defined classes
            """
            safrs.log.debug(exc)
            return attr_val

        # skip type coercion on JSON columns, since they could be anything
        if type(attr.type) is sqlalchemy.sql.sqltypes.JSON:
            return attr_val

        """
            Parse datetime and date values for some common representations
            If another format is used, the user should create a custom column type or custom serialization
        """
        if attr_val and attr.type.python_type == datetime.datetime:
            date_str = str(attr_val)
            try:
                if "." in date_str:
                    # str(datetime.datetime.now()) => "%Y-%m-%d %H:%M:%S.%f"
                    attr_val = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S.%f")
                else:
                    # JS datepicker format
                    attr_val = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            except (NotImplementedError, ValueError) as exc:
                safrs.log.warning('Invalid datetime.datetime {} for value "{}"'.format(exc, attr_val))
                attr_val = datetime.datetime.now()
        elif attr_val and attr.type.python_type == datetime.date:
            try:
                attr_val = datetime.datetime.strptime(str(attr_val), "%Y-%m-%d")
            except (NotImplementedError, ValueError) as exc:
                safrs.log.warning('Invalid datetime.date {} for value "{}"'.format(exc, attr_val))
                attr_val = datetime.datetime.now()
        elif attr_val and attr.type.python_type == datetime.time:  # pragma: no cover (todo)
            try:
                date_str = str(attr_val)
                if "." in date_str:
                    # str(datetime.datetime.now()) => "%H:%M:%S.%f"
                    attr_val = datetime.datetime.strptime(str(attr_val), "%H:%M:%S.%f").time()
                else:
                    # JS datepicker format
                    attr_val = datetime.datetime.strptime(str(attr_val), "%H:%M:%S").time()
            except (NotImplementedError, ValueError, TypeError) as exc:
                safrs.log.warning('Invalid datetime.time {} for value "{}"'.format(exc, attr_val))
                attr_val = attr.type.python_type()
        else:
            attr_val = attr.type.python_type(attr_val)

        return attr_val

    def _s_expunge(self):
        """
            expunge an object from its session
        """
        session = sqla_inspect(self).session
        session.expunge(self)

    @classproperty
    def _s_auto_commit(self):
        """
            :return: whether the instance should be automatically commited.
            :rtype: boolen
            fka db_commit: auto_commit is a beter name, but keep db_commit for backwards compatibility
        """
        return self.db_commit

    @_s_auto_commit.setter
    def _s_auto_commit(self, value):
        """
            :param value:
            auto_commit setter
        """
        self.db_commit = value

    @classmethod
    def get_instance(cls, item=None, failsafe=False):
        """
            :param item: instance id or dict { "id" : .. "type" : ..}
            :param failsafe: indicates whether we want an exception to be raised in case the id is not found
            :return: Instance or None. An error is raised if an invalid id is used
        """
        instance = None
        # pylint: disable=invalid-name,redefined-builtin
        if isinstance(item, dict):
            id = item.get("id", None)
            if id is None:
                raise ValidationError("Invalid id")
            if item.get("type") != cls._s_type:
                raise ValidationError("Invalid item type")
        else:
            id = item
        try:
            primary_keys = cls.id_type.get_pks(id)
        except AttributeError:  # pragma: no cover
            # This happens when we request a sample from a class that is not yet loaded
            # when we're creating the swagger models
            safrs.log.debug('AttributeError for class "{}"'.format(cls.__name__))
            return instance  # instance is None!

        if id is not None or not failsafe:
            try:
                instance = cls._s_query.filter_by(**primary_keys).first()
            except Exception as exc:  # pragma: no cover
                raise GenericError("get_instance : {}".format(exc))

            if not instance and not failsafe:
                raise NotFoundError('Invalid "{}" ID "{}"'.format(cls.__name__, id))
        return instance

    @classmethod
    def _s_get_instance_by_id(cls, id):
        """
            :param id: jsonapi_id
            :return: query obj
        """
        primary_keys = cls.id_type.get_pks(id)
        return cls._s_query.filter_by(**primary_keys)

    @property
    def jsonapi_id(self):
        """
            :return: json:api id
            :rtype: str

            if the table/object has a single primary key "id", it will return this id.
            In the other cases, the jsonapi "id" will be generated by the cls.id_type (typically by combining the PKs)

            The id has to be of type string according to the jsonapi json validation schema
        """
        return str(self.id_type.get_id(self))

    @hybrid_property
    def id_type(obj):
        """
            :return: the object's id type
        """
        id_type = get_id_type(obj)
        # monkey patch so we don't have to look it up next time
        obj.id_type = id_type
        return id_type

    @classproperty
    def _s_query(cls):
        """
            :return: sqla query object
        """
        _table = getattr(cls, "_table", None)
        if _table:
            return safrs.DB.session.query(_table)
        return safrs.DB.session.query(cls)

    query = _s_query

    @classproperty
    def _s_column_names(cls):
        """
            :return: list of column names
        """
        return [c.name for c in cls._s_columns]

    @classproperty
    def _s_columns(cls):
        """
            :return: list of columns that are exposed by the api
        """
        mapper = getattr(cls, "__mapper__", None)
        if mapper is None:
            return []

        result = cls.__mapper__.columns

        if has_request_context():
            # In the web context we only return the attributes that are exposable and readable
            # i.e. where the "expose" attribute is set on the db.Column instance
            # and the "r" flag is in the permissions
            result = [c for c in result if cls._s_check_perm(c.name)]

        return result

    @hybrid_property
    def _s_relationships(self):
        """
            :return: the relationships used for jsonapi (de/)serialization
        """
        rels = [rel for rel in self.__mapper__.relationships if self._s_check_perm(rel.key)]
        return rels

    @hybrid_property
    def _s_relationship_names(cls):
        """
            :return: list of realtionship names
        """
        rel_names = [rel.key for rel in cls._s_relationships]
        return rel_names

    @hybrid_property
    def _s_jsonapi_attrs(self):
        """
            :return: dictionary of exposed attribute names and values
        """

        """
            The `fields` variable is used to implement jsonapi "Sparse Fieldsets"
            https://jsonapi.org/format/#fetching-sparse-fieldsets:
              client MAY request that an endpoint return only specific fields in the response on a per-type basis by including a fields[TYPE] parameter.
              The value of the fields parameter MUST be a comma-separated (U+002C COMMA, “,”) list that refers to the name(s) of the fields to be returned.
              If a client requests a restricted set of fields for a given resource type, an endpoint MUST NOT include additional fields in resource objects
              of that type in its response.
            Therefore we extract the required fieldnames from the request args, eg. Users/?Users[name] => [name]
        """
        fields = self.__class__._s_jsonapi_attrs.keys()
        if has_request_context():
            fields = request.fields.get(self._s_class_name, fields)

        result = {}
        for attr in fields:
            attr_val = ""
            if attr in self.__class__._s_jsonapi_attrs.keys():
                attr_val = getattr(self, attr)
            try:
                # use the current_app json_encoder
                if current_app:
                    result[attr] = json.loads(json.dumps(attr_val, cls=current_app.json_encoder))
                else:
                    result[attr] = attr_val
            except UnicodeDecodeError:  # pragma: no cover
                safrs.log.warning("UnicodeDecodeError fetching {}.{}".format(self, attr))
                result[attr] = ""
            except Exception as exc:
                safrs.log.warning("Failed to fetch {}.{}: {}".format(self, attr, exc))

        return result

    @_s_jsonapi_attrs.expression
    def _s_jsonapi_attrs(cls):
        """
            :return: list of jsonapi attribute names
            At the moment we expect the column name to be equal to the column name
            Things will go south if this isn't the case and we should use
            the cls.__mapper__._polymorphic_properties instead
        """
        result = {}
        for column in cls._s_columns:
            # Ignore the exclude_attrs for serialization/deserialization
            attr_name = column.name
            if getattr(column, "expose", True) is not True:
                continue
            if attr_name in cls.exclude_attrs:
                continue
            # don't expose attributes starting with an underscore
            if attr_name.startswith("_"):
                continue
            # jsonapi schema prohibits the use of the fields 'id' and 'type' in the attributes
            # http://jsonapi.org/format/#document-resource-object-fields
            if attr_name == "type":
                # translate type to Type
                result["Type"] = column
            elif not attr_name == "id" and attr_name not in cls._s_relationship_names:
                result[attr_name] = column

        for attr_name, attr_val in cls.__dict__.items():
            if is_jsonapi_attr(attr_val):
                result[attr_name] = attr_val

        return result

    def to_dict(self, *args, **kwargs):
        """
            Create a dictionary with all the instance "attributes"
            this method will be called by SAFRSJSONEncoder to serialize objects

            :return: dictionary object
            ---
            This method is deprecated, use _s_jsonapi_attrs
        """
        return self._s_jsonapi_attrs

    @classproperty
    def _s_class_name(cls):
        """
            :return: the name of the instances
        """
        return cls.__name__

    @classproperty
    def _s_collection_name(cls):
        """
            :return: the name of the collection, this will be used to construct the endpoint
        """
        return getattr(cls, "__tablename__", cls.__name__)

    @classproperty
    def _s_type(cls):
        """
            :return: the jsonapi "type", i.e. the tablename if this is a db model, the classname otherwise
        """
        return cls.__name__

    @classmethod
    def _s_check_perm(cls, property_name, permission="r"):
        """
            Check the column permission (read/write)
            Goal is to extend this in the future
            :param column_name: column name
            :permission:
            :return: Boolean
        """
        if property_name.startswith("_"):
            return False

        for rel in cls.__mapper__.relationships:
            if rel.key != property_name:
                continue
            if rel.key in cls.exclude_rels:
                # relationship name has been set in exclude_rels
                return False
            if not getattr(rel.mapper.class_, "_s_expose", False):
                # only SAFRSBase instances can be exposed
                return False
            if not getattr(rel, "expose", True):
                # relationship `expose` attribute has explicitly been set to False
                return False
            return True

        for column in cls.__mapper__.columns:
            # don't expose attributes starting with an underscore
            if column.name != property_name:
                continue
            if getattr(column, "expose", True) and permission in getattr(column, "permissions", "rw"):
                return True
            return False

        if is_jsonapi_attr(getattr(cls, property_name, None)):
            return True

        raise ValidationError("Invalid property {}".format(property_name))

    @hybrid_method
    def _s_jsonapi_encode(self):
        """
            :return: Encoded object according to the jsonapi specification:
            `data = {
                    "attributes": { ... },
                    "id": "...",
                    "links": { ... },
                    "relationships": { ... },
                    "type": "..."
                    }`
        """
        # params = { self.object_id : self.id }
        # obj_url = url_for(self.get_endpoint(), **params) # Doesn't work :(, todo : why?
        obj_url = url_for(self.get_endpoint())
        if obj_url.endswith("/"):
            obj_url = obj_url[:-1]

        self_link = self._s_url
        attributes = self.to_dict()
        relationships = self._s_get_related()
        data = dict(attributes=attributes, id=self.jsonapi_id, links={"self": self_link}, type=self._s_type, relationships=relationships)

        return data

    def _s_get_related(self):
        """
            :return: related objects

            http://jsonapi.org/format/#fetching-includes

            Inclusion of Related Resources
            Multiple related resources can be requested in a comma-separated list:
            An endpoint MAY return resources related to the primary data by default.
            An endpoint MAY also support an include request parameter to allow
            the client to customize which related resources should be returned.
            In order to request resources related to other resources,
            a dot-separated path for each relationship name can be specified

            All related instances are stored in the `Included` class so we don't have to walk
            the relationships twice
        """
        included_list = getattr(self, "included_list", None)
        if included_list is None:
            # Multiple related resources can be requested in a comma-separated list
            included_csv = request.args.get("include", safrs.SAFRS.DEFAULT_INCLUDED)
            included_list = included_csv.split(",")
        excluded_csv = request.args.get("exclude", "")
        excluded_list = excluded_csv.split(",")
        # In order to recursively request related resources
        # a dot-separated path for each relationship name can be specified
        included_rels = {i.split(".")[0]: i for i in included_list}
        relationships = dict()
        for relationship in self._s_relationships:
            """
                http://jsonapi.org/format/#document-resource-object-relationships:

                The value of the relationships key MUST be an object (a “relationships object”).
                Members of the relationships object (“relationships”) represent
                references from the resource object in which it’s defined to other resource objects.

                Relationships may be to-one or to-many.

                A “relationship object” MUST contain at least one of the following:

                - links: a links object containing at least one of the following:
                    - self: a link for the relationship itself (a “relationship link”).
                    This link allows the client to directly manipulate the relationship.
                    - related: a related resource link
                - data: resource linkage
                - meta: a meta object that contains non-standard meta-information
                        about the relationship.
                A relationship object that represents a to-many relationship
                MAY also contain pagination links under the links member, as described below.
                SAFRS currently implements links with self
            """
            meta = {}
            rel_name = relationship.key
            if rel_name in excluded_list:
                # TODO: document this
                # continue
                pass
            data = None
            if rel_name in included_rels or safrs.SAFRS.INCLUDE_ALL in included_list:
                # the relationship instances should be included
                included_rel = included_rels.get(rel_name)
                # next_included_list contains the recursive relationship names
                next_included_list = included_rel.split(".")[1:] if included_rel else []
                if relationship.direction == MANYTOONE:
                    # manytoone relationship contains a single instance
                    rel_item = getattr(self, rel_name)
                    if rel_item:
                        # create an Included instance that will be used for serialization eventually
                        data = Included(rel_item, next_included_list)
                elif relationship.direction in (ONETOMANY, MANYTOMANY):
                    # manytoone relationship contains a list of instances
                    # Data is optional, it's also really slow for large sets!
                    rel_query = getattr(self, rel_name)
                    limit = request.page_limit
                    if not get_config("ENABLE_RELATIONSHIPS"):
                        meta["warning"] = "ENABLE_RELATIONSHIPS set to false in config.py"
                    elif rel_query:
                        # todo: chekc if lazy=dynamic
                        # In order to work with the relationship as with Query,
                        # you need to configure it with lazy='dynamic'
                        # "limit" may not be possible !
                        if getattr(rel_query, "limit", False):
                            count = rel_query.count()
                            rel_query = rel_query.limit(limit)
                            if rel_query.count() >= get_config("BIG_QUERY_THRESHOLD"):
                                warning = 'Truncated result for relationship "{}",consider paginating this request'.format(rel_name)
                                safrs.log.warning(warning)
                                meta["warning"] = warning
                            items = rel_query.all()
                        else:
                            items = list(rel_query)
                            count = len(items)
                        meta["count"] = count
                        meta["limit"] = limit
                        data = []
                        for rel_item in items:
                            data.append(Included(rel_item, next_included_list))
                else:  # pragma: no cover
                    # shouldn't happen!!
                    safrs.log.error("Unknown relationship direction for relationship {}: {}".format(rel_name, relationship.direction))

            rel_link = urljoin(self._s_url, rel_name)
            links = dict(self=rel_link)
            rel_data = dict(links=links)

            rel_data["data"] = data
            if meta:
                rel_data["meta"] = meta
            relationships[rel_name] = rel_data

        return relationships

    def __unicode__(self):
        """

        """
        name = getattr(self, "name", self.__class__.__name__)
        return name

    def __str__(self):
        """

        """
        name = getattr(self, "name", self.__class__.__name__)
        return "<SAFRS {}>".format(name)

    @classmethod
    def _s_count(cls):
        """
            returning None will cause our jsonapi to perform a count() on the result
            this can be overridden with a cached value for performance on large tables (>1G)
        """
        return None

    #
    # Following methods are used to create the swagger2 API documentation
    #
    @classmethod
    def _s_sample_id(cls):
        """
            :return: a sample id for the API documentation
        """
        sample = cls.query.first()
        if sample:
            try:
                sample_id = sample.jsonapi_id
                return sample_id
            except Exception:
                safrs.log.warning("Failed to retrieve sample id for {}".format(cls))

        sample_id = cls.id_type.sample_id(cls)
        return sample_id

    @classmethod
    def _s_sample_dict(cls):
        """
            :return: a sample to be used as an example payload in the swagger example
        """
        # create a swagger example based on the jsonapi attributes (i.e. the database column schema)
        sample = {}
        for attr_name, attr in cls._s_jsonapi_attrs.items():
            if is_jsonapi_attr(attr):
                arg = getattr(attr, "default", "")
            else:
                column = attr
                arg = None
                if hasattr(column, "sample"):
                    arg = getattr(column, "sample")
                elif hasattr(column, "default") and column.default:
                    if callable(column.default.arg):
                        # todo: check how to display the default args
                        safrs.log.warning("Not implemented: {}".format(column.default.arg))
                        continue
                    else:
                        python_type = SWAGGER2_TYPE_CAST.get(column.type, str)
                        arg = python_type(column.default.arg)
                else:
                    # No default column value speciefd => infer one by type
                    try:
                        if column.type.python_type == int:
                            arg = 0
                        if column.type.python_type == datetime.datetime:
                            arg = str(datetime.datetime.now())
                        elif column.type.python_type == datetime.date:
                            arg = str(datetime.date.today())
                        else:
                            arg = column.type.python_type()
                    except NotImplementedError:
                        # This may happen for custom columns
                        safrs.log.debug("Failed to get python type for column {} (NotImplementedError)".format(column))
                        arg = None
                    except Exception as exc:
                        safrs.log.debug("Failed to get python type for column {} ({})".format(column, exc))
                        # use an empty string when no type is matched, otherwise we may get json encoding
                        # errors for the swagger generation
                        arg = ""

            sample[attr_name] = arg

        return sample

    @classproperty
    def _s_object_id(cls):
        """
            :return: the Flask url parameter name of the object, e.g. UserId
            :rtype: string
        """
        # pylint: disable=no-member
        return cls.__name__ + get_config("OBJECT_ID_SUFFIX")

    @classmethod
    def _s_get_jsonapi_rpc_methods(cls):
        """
            :return: a list of jsonapi_rpc methods for this class
            :rtype: list
        """
        result = []
        try:
            cls_members = inspect.getmembers(cls)
        except sqlalchemy.exc.InvalidRequestError as exc:
            # This may happen if there's no sqlalchemy superclass
            safrs.log.warning("Member inspection failed for {}: {}".format(cls, exc))
            return result

        for _, method in cls_members:  # [(name, method),..]
            rest_doc = get_doc(method)
            if rest_doc is not None:
                result.append(method)
        return result

    # pylint: disable=
    @classmethod
    def _s_get_swagger_doc(cls, http_method):
        """
            :param http_method: the http method for which to retrieve the documentation
            :return: swagger `body` and `response` dictionaries
            :rtype: tuple
            Create a swagger api model based on the sqlalchemy schema.
        """
        body = {}
        responses = {}

        if http_method.upper() in cls.http_methods:
            responses = {HTTPStatus.NOT_FOUND.value: {"description": HTTPStatus.NOT_FOUND.description}}

            if http_method in ("post", "patch"):
                responses = {HTTPStatus.CREATED.value: {"description": HTTPStatus.CREATED.description}}

        return body, responses

    @classmethod
    def get_endpoint(cls, url_prefix=None, type=None):
        """
            :param url_prefix: URL prefix used by the app
            :param type: endpoint type, e.g. "instance"
            :return: the API endpoint
            :rtype: str
        """
        if url_prefix is None:
            url_prefix = cls.url_prefix
        if type == "instance":
            INSTANCE_ENDPOINT_FMT = get_config("INSTANCE_ENDPOINT_FMT")
            endpoint = INSTANCE_ENDPOINT_FMT.format(url_prefix, cls._s_type)
        else:  # type = 'collection'
            endpoint = "{}api.{}".format(url_prefix, cls._s_type)
        return endpoint

    @hybrid_property
    def _s_url(self, url_prefix=""):
        """
            :param url_prefix:
            :return: endpoint url of this instance
        """
        try:
            params = {self._s_object_id: self.jsonapi_id}
            instance_url = url_for(self.get_endpoint(type="instance"), **params)
            result = urljoin(request.url_root, instance_url)
        except RuntimeError:
            # This happens when creating the swagger doc and there is no application registered
            result = ""
        return result

    @_s_url.expression
    def _s_url(cls, url_prefix=""):
        try:
            collection_url = url_for(cls.get_endpoint())
            result = urljoin(request.url_root, collection_url)
        except RuntimeError:
            # This happens when creating the swagger doc and there is no application registered
            result = ""
        return result

    @classmethod
    def _s_meta(cls):
        """
            What is returned in the "meta" part
            may be implemented by the app
        """
        return {}

    @property
    def Type(self):
        """
            jsonapi spec doesn't allow "type" as an attribute nmae, but this is a pretty common column name
            we rename type to Type so we can support it. A bit hacky but better than not supporting "type" at all
            This may cause other errors too, for ex when sorting
            :return: renamed type
        """
        safrs.log.debug('({}): attribute name "type" is reserved, renamed to "Type"'.format(self))
        return self.type

    @Type.setter
    def Type(self, value):
        """
            Type property setter, see comment in the type property
        """
        # pylint: disable=attribute-defined-outside-init
        if not self.Type == value:
            self.Type = value
        self.type = value

    @classmethod
    def _s_filter(cls, *filter_args, **filter_kwargs):
        """
            Apply a filter to this model
            :param filter_args: filter to apply, passed as a request URL parameter
            :return: sqla query object
        """
        safrs.log.info("_s_filter args: {}".format(filter_args))
        safrs.log.info("override the {}._s_filter classmethod to implement your filtering".format(cls.__name__))
        return cls._s_query


class Included:
    """
        This class contains the instances that will be included in the jsonapi response
        we keep a set of instances to avoid storing duplicates
    """

    instances = set()
    instance = None
    data = set()

    def __init__(self, instance, included_list):
        """
            :param instance: the instance to be included
            :param included_list: the list of relationships that should be included for `instance`
        """
        self.instance = instance
        instance.included_list = included_list
        Included.instances.add(instance)

    @hybrid_method
    def encode(self):
        """
            jsonapi encoding of the instance in the relationship dictionary
        """
        return {"id": str(self.instance.jsonapi_id), "type": self.instance._s_type}

    @encode.expression
    def encode(cls):
        """
            encoding of all included instances (in the included[] part of the jsonapi response)
        """
        already_included = set()
        result = []
        while len(cls.instances):
            instance = cls.instances.pop()
            if instance in already_included:
                continue
            try:
                result.append(instance._s_jsonapi_encode())
            except sqlalchemy.orm.exc.DetachedInstanceError as exc:
                # todo: test this
                safrs.log.warning("Included encode: {}".format(exc))
                continue

        return result
