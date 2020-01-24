# -*- coding: utf-8 -*-
# base.py: implements the SAFRSBase SQLAlchemy db Mixin and related operations
#
# SQLAlchemy database schemas
# pylint: disable=logging-format-interpolation,no-self-argument,no-member,line-too-long,fixme,protected-access
import inspect
import datetime
import sqlalchemy
from http import HTTPStatus
from urllib.parse import urljoin
from flask import request, url_for
from flask_sqlalchemy import Model
from sqlalchemy.orm.session import make_transient
from sqlalchemy import inspect as sqla_inspect
from sqlalchemy.orm.interfaces import ONETOMANY, MANYTOONE, MANYTOMANY
from sqlalchemy.ext.hybrid import hybrid_method, hybrid_property

# safrs dependencies:
import safrs
from .swagger_doc import SchemaClassFactory, get_doc
from .errors import GenericError, NotFoundError, ValidationError
from .safrs_types import get_id_type
from .util import classproperty
from .config import get_config, is_debug

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
}
# casting of swagger types to python types
SWAGGER2_TYPE_CAST = {"integer": int, "string": str, "number": int, "boolean": bool}
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

    def __new__(cls, **kwargs):
        """
            If an object with given arguments already exists, this object is instantiated
        """
        # Fetch the PKs from the kwargs so we can lookup the corresponding object
        primary_keys = cls.id_type.get_pks(kwargs.get("id", ""))
        # Lookup the object with the PKs
        instance = cls._s_query.filter_by(**primary_keys).first()
        if not instance:
            instance = object.__new__(cls)
        else:
            safrs.log.debug("{} exists for {} ".format(cls.__name__, str(kwargs)))

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
        # kwargs dictionary (from json).
        # Retrieve the values from each attribute (== class table column)
        db_args = {}
        columns = self.__table__.columns
        for column in columns:
            attr_val = self._s_parse_attr_value(kwargs, column)
            db_args[column.name] = attr_val

        # Add the related instances
        for rel_name in self._s_relationship_names:
            rel_attr = kwargs.get(rel_name, None)
            if rel_attr:
                # This shouldn't in the work in the web context
                # because the relationships should already have been removed by SAFRSRestAPI.post
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

    def _s_parse_attr_value(self, kwargs, column):
        """
            Try to fetch and parse the (jsonapi attribute) value for a db column from the kwargs
            :param kwargs:
            :param column: database column
            :return parsed value:
        """
        attr_name = column.name
        attr_val = kwargs.get(attr_name, None)
        if attr_val is None and column.default:
            attr_val = column.default.arg
            return attr_val

        if attr_val is None:
            return attr_val

        try:
            column.type.python_type
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

        """
            Parse datetime and date values for some common representations
            If another format is uses, the user should create a custom column type or custom serialization
        """
        if attr_val and column.type.python_type == datetime.datetime:
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

        elif attr_val and column.type.python_type == datetime.date:
            try:
                attr_val = datetime.datetime.strptime(str(attr_val), "%Y-%m-%d")
            except (NotImplementedError, ValueError) as exc:
                safrs.log.warning('Invalid datetime.date {} for value "{}"'.format(exc, attr_val))

        return attr_val

    def _s_expunge(self):
        """
            expunge an object from its session
        """
        session = sqla_inspect(self).session
        session.expunge(self)

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
        except AttributeError:
            # This happens when we request a sample from a class that is not yet loaded
            # when we're creating the swagger models
            safrs.log.debug('AttributeError for class "{}"'.format(cls.__name__))
            return instance  # instance is None!

        if id is not None or not failsafe:
            try:
                instance = cls._s_query.filter_by(**primary_keys).first()
            except Exception as exc:
                safrs.log.error("get_instance : {}".format(exc))

            if not instance and not failsafe:
                raise NotFoundError('Invalid "{}" ID "{}"'.format(cls.__name__, id))
        return instance

    @property
    def jsonapi_id(self):
        """
            :return: json:api id
            :rtype: str

            if the table/object has a single primary key "id", it will return this id.
            In the other cases, the jsonapi "id" will be generated by the cls.id_type (typically by combining the PKs)
        """
        return self.id_type.get_id(self)

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
            :return: list of columns
        """
        mapper = getattr(cls, "__mapper__", None)
        if mapper is None:
            return []
        return list(cls.__mapper__.columns)

    @hybrid_property
    def _s_relationships(self):
        """
            :return: the relationships used for jsonapi (de/)serialization
        """
        rels = [rel for rel in self.__mapper__.relationships if rel.key not in self.exclude_rels]
        return rels

    @classproperty
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
        result = {attr: getattr(self, attr) for attr in self.__class__._s_jsonapi_attrs}
        return result

    @_s_jsonapi_attrs.expression
    def _s_jsonapi_attrs(cls):
        """
            :return: list of jsonapi attribute names
            At the moment we expect the column name to be equal to the column name
            Things will go south if this isn't the case and we should use
            the cls.__mapper__._polymorphic_properties instead
        """
        result = []
        for attr in cls._s_column_names:
            # Ignore the exclude_attrs for serialization/deserialization
            if attr in cls.exclude_attrs:
                continue
            # jsonapi schema prohibits the use of the fields 'id' and 'type' in the attributes
            # http://jsonapi.org/format/#document-resource-object-fields
            if attr == "type":
                # translate type to Type
                result.append("Type")
            elif not attr == "id":
                result.append(attr)

        return result

    @classproperty
    def _s_class_name(cls):
        """
            :return: the name of the instances
        """
        return cls.__name__

    @classproperty
    def _s_collection_name(cls):
        """
            :return: the name of the collection
        """
        return getattr(cls, "__tablename__", cls.__name__)

    @classproperty
    def _s_type(cls):
        """
            :return: the jsonapi "type", i.e. the tablename if this is a db model, the classname otherwise
        """
        return cls.__name__

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
            Type property setter
        """
        # pylint: disable=attribute-defined-outside-init
        if not self.Type == value:
            self.Type = value
        self.type = value

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

    def _s_patch(self, **attributes):
        """
            update the object attributes 
            :param **attributes:
        """
        columns = {col.name: col for col in self._s_columns}
        for attr, value in attributes.items():
            if attr in columns and attr in self._s_jsonapi_attrs:
                value = self._s_parse_attr_value(attributes, columns[attr])
                setattr(self, attr, value)

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

    def to_dict(self, fields=None):
        """
            Create a dictionary with all the instance "attributes"
            this method will be called by SAFRSJSONEncoder to serialize objects

            :param fields: if set, fields to include in the result
            :return: dictionary object

            The optional `fields` attribute is used to implement jsonapi "Sparse Fieldsets"
            https://jsonapi.org/format/#fetching-sparse-fieldsets:
              client MAY request that an endpoint return only specific fields in the response on a per-type basis by including a fields[TYPE] parameter.
              The value of the fields parameter MUST be a comma-separated (U+002C COMMA, “,”) list that refers to the name(s) of the fields to be returned.
              If a client requests a restricted set of fields for a given resource type, an endpoint MUST NOT include additional fields in resource objects
              of that type in its response.
        """
        result = {}
        if fields is None:
            # Check if fields have been provided in the request
            fields = self._s_jsonapi_attrs
            if request:
                fields = request.fields.get(self._s_class_name, fields)

        # filter the relationships, id & type from the data
        for attr in self._s_jsonapi_attrs:
            if attr not in fields:
                continue
            try:
                result[attr] = getattr(self, attr)
            except:
                safrs.log.warning("Failed to fetch {}".format(attr))
                # result[attr] = getattr(self, attr.lower())
        return result

    @classmethod
    def _s_count(cls):
        """
            returning None will cause our jsonapi to perform a count() on the result
            this can be overridden with a cached value for performance on large tables (>1G)
        """
        return None

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
        relationships = dict()
        excluded_csv = request.args.get("exclude", "")
        excluded_list = excluded_csv.split(",")
        included_csv = request.args.get("include", "")
        included_list = included_csv.split(",")

        # In order to request resources related to other resources,
        # a dot-separated path for each relationship name can be specified
        nested_included_list = []
        for inc in included_list:
            if "." in inc:
                nested_included_list += inc.split(".")
        included_list += nested_included_list

        # params = { self.object_id : self.id }
        # obj_url = url_for(self.get_endpoint(), **params) # Doesn't work :(, todo : why?
        obj_url = url_for(self.get_endpoint())
        if obj_url.endswith("/"):
            obj_url = obj_url[:-1]

        self_link = self._s_url

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
            if rel_name in included_list:
                if relationship.direction == MANYTOONE:
                    rel_item = getattr(self, rel_name)
                    if rel_item:
                        data = {"id": rel_item.jsonapi_id, "type": rel_item._s_type}
                elif relationship.direction in (ONETOMANY, MANYTOMANY):
                    # Data is optional, it's also really slow for large sets!!!!!
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
                        data = [{"id": i.jsonapi_id, "type": i._s_type} for i in items]
                else:  # shouldn't happen!!
                    safrs.log.error("Unknown relationship direction for relationship {}: {}".format(rel_name, relationship.direction))
                # add the relationship direction, for debugging purposes.
                if is_debug():
                    # meta["direction"] = relationship.direction.name
                    pass

            rel_link = urljoin(self_link, rel_name)
            links = dict(self=rel_link)
            rel_data = dict(links=links)

            rel_data["data"] = data
            if meta:
                rel_data["meta"] = meta
            relationships[rel_name] = rel_data

        attributes = self.to_dict()
        # extract the required fieldnames from the request args, eg. Users/?Users[name] => [name]
        fields = request.args.get("fields[{}]".format(self._s_type), None)
        if fields:
            # Remove all attributes not listed in the fields csv
            fields = fields.split(",")
            unwanted = set(attributes.keys()) - set(fields)
            for unwanted_key in unwanted:
                attributes.pop(unwanted_key, None)

        data = dict(attributes=attributes, id=self.jsonapi_id, links={"self": self_link}, type=self._s_type, relationships=relationships)

        return data

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

    #
    # Following methods are used to create the swagger2 API documentation
    #
    @classmethod
    def _s_sample_id(cls):
        """
            :return: a sample id for the API documentation, i.e. the first item in the DB
        """
        sample = cls._s_sample()
        if sample:
            j_id = sample.jsonapi_id
        else:
            j_id = ""
        return j_id

    @classmethod
    def _s_sample(cls):
        """
            :return: a sample instance for the API documentation, i.e. the first item in the DB
        """
        first = None

        try:
            first = cls._s_query.first()
        except RecursionError as exc:
            safrs.log.warning("Failed to retrieve sample for {}({})".format(cls, exc))
        except Exception as exc:
            safrs.log.warning("Failed to retrieve sample for {}({})".format(cls, exc))
        return first

    @classmethod
    def _s_sample_dict(cls):
        """
            :return: a sample to be used as an example payload in the swagger example
        """
        # create a swagger example based on the jsonapi attributes (i.e. the database column schema)
        sample = {}
        for column in cls._s_columns:
            if column.name in ("id", "type") or column.name not in cls._s_jsonapi_attrs:
                continue
            arg = None
            if column.default:
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
                    safrs.log.debug("Failed to get python type for column {} (NotImplementedError)".format(column))
                    arg = None
                except Exception as exc:
                    safrs.log.debug("Failed to get python type for column {} ({})".format(column, exc))
            sample[column.name] = arg

        return sample

    @classproperty
    def object_id(cls):
        """
            :return: the Flask url parameter name of the object, e.g. UserId
            :rtype: string
        """
        # pylint: disable=no-member
        return cls.__name__ + get_config("OBJECT_ID_SUFFIX")

    # pylint: disable=
    @classmethod
    def get_swagger_doc(cls, http_method):
        """
            :param http_method: the http method for which to retrieve the documentation
            :return: swagger `body` and `response` dictionaries
            :rtype: tuple
            Create a swagger api model based on the sqlalchemy schema.
        """
        body = {}
        responses = {}

        if http_method in cls.http_methods:
            object_model = cls._get_swagger_doc_object_model()
            responses = {
                HTTPStatus.OK.value: {"description": HTTPStatus.OK.description},
                HTTPStatus.NOT_FOUND.value: {"description": HTTPStatus.NOT_FOUND.description},
            }

            if http_method == "get":
                body = object_model

            if http_method in ("post", "patch"):
                # body = cls.get_swagger_doc_post_parameters()
                responses = {
                    HTTPStatus.OK.value: {"description": HTTPStatus.OK.description},
                    HTTPStatus.CREATED.value: {"description": HTTPStatus.CREATED.description},
                }

        return body, responses

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

    @classmethod
    def _get_swagger_doc_object_model(cls):
        """
            Create a schema for object creation and updates through the HTTP PATCH and POST interfaces
            The schema is created using the sqlalchemy database schema. So there
            is a one-to-one mapping between json input data and db columns
            :return: swagger doc
        """
        fields = {}
        sample_id = cls._s_sample_id()
        sample_instance = cls.get_instance(sample_id, failsafe=True)
        for column in cls._s_columns:
            if column.name not in cls._s_jsonapi_attrs:
                continue
            # convert the column type to string and map it to a swagger type
            column_type = str(column.type)
            # Take care of extended column type declarations, eg. TEXT COLLATE "utf8mb4_unicode_ci" > TEXT
            column_type = column_type.split("(")[0]
            column_type = column_type.split(" ")[0]
            swagger_type = SQLALCHEMY_SWAGGER2_TYPE.get(column_type, None)
            if swagger_type is None:
                safrs.log.warning(
                    'Could not match json datatype for db column type `{}`, using "string" for {}.{}'.format(
                        column_type, cls.__tablename__, column.name
                    )
                )
                swagger_type = "string"
            default = getattr(sample_instance, column.name, None)
            if default is None:
                # swagger api spec doesn't support nullable values
                continue

            field = {"type": swagger_type, "example": str(default)}  # added unicode str() for datetime encoding
            fields[column.name] = field

        model_name = "{}_{}".format(cls.__name__, "CreateUpdate")
        model = SchemaClassFactory(model_name, fields)
        return model

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
            params = {self.object_id: self.jsonapi_id}
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

    @classmethod
    def _s_filter(cls, filter_args):
        """
            Apply a filter to this model
            :param filter_args: filter to apply, passed as a request URL parameter
            :return: sqla query object
        """
        safrs.log.info("_s_filter args: {}".format(filter_args))
        safrs.log.info("override the {}._s_filter classmethod to implement your filtering".format(cls.__name__))
        return cls._s_query


class SAFRSDummy:
    """
        Debug class
    """

    def __getattr__(self, attr):
        print("get", attr)

    def __setattr__(self, attr, val):
        print("set", attr, val)
