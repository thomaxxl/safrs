# -*- coding: utf-8 -*-
"""
    db.py: implements the SAFRSBase SQLAlchemy db Mixin and related operations
"""
#
# SQLAlchemy database schemas
# pylint: disable=logging-format-interpolation,no-self-argument,no-member,line-too-long,fixme,protected-access
import inspect
import datetime
import logging
from urllib.parse import urljoin
from flask import request, url_for
from flask_sqlalchemy import Model
import sqlalchemy
from sqlalchemy import orm
from sqlalchemy.orm.session import make_transient
from sqlalchemy import inspect as sqla_inspect
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm.interfaces import ONETOMANY, MANYTOONE, MANYTOMANY

# safrs dependencies:
import safrs
from .swagger_doc import SchemaClassFactory, get_doc
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
}

#
# SAFRSBase superclass
#
class SAFRSBase(Model):
    """
        This SQLAlchemy mixin implements Json Serialization for SAFRS SQLalchemy Persistent Objects
        Serialization itself is performed by the ``to_dict`` method
        Initialization and instantiation are quite complex because we rely on the DB schema

        The jsonapi id is generated from the primary keys of the columns

        The object attributes should not match column names,
        this is why most of the methods & properties have the '_s_' prefix!
    """
    query_limit = 50
    # set this to False if you want to use the SAFRSBase in combination
    # with another framework, eg flask-admin
    # The caller will have to add and commit the object by itself then...
    db_commit = True
    http_methods = {}  # http methods, used in case of override
    url_prefix = ""
    allow_client_generated_ids = False

    exclude_attrs = []
    exclude_rels = []

    def __new__(cls, **kwargs):
        """
            If an object with given arguments already exists, this object is instantiated
        """
        # Fetch the PKs from the kwargs so we can lookup the corresponding object
        primary_keys = cls.id_type.get_pks(kwargs.get("id", ""))
        # Lookup the object with the PKs
        instance = cls.query.filter_by(**primary_keys).first()
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

        if self.db_commit:
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
        except NotImplementedError:
            """
                https://docs.python.org/2/library/exceptions.html#exceptions.NotImplementedError :
                In user defined base classes, abstract methods should raise this exception when they require derived classes to override the method.
                => simply return the attr_val for user-defined classes
            """
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
        session = sqla_inspect(self).session
        session.expunge(self)
    
    # pylint: disable=
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
            if item.get("type") != cls._s_type or id is None:
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

        if not id is None or not failsafe:
            try:
                instance = cls.query.filter_by(**primary_keys).first()
            except Exception as exc:
                safrs.log.error("get_instance : %s", str(exc))

            if not instance and not failsafe:
                # TODO: id gets reflected back to the user: should we filter it for XSS ?
                # or let the client handle it?
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
        _table = getattr(cls, "_table", None)
        if _table:
            return safrs.DB.session.query(_table)
        return safrs.DB.session.query(cls)

    query = _s_query

    @classproperty
    def _s_column_names(cls):
        return [c.name for c in cls.__mapper__.columns]

    @classproperty
    def _s_columns(cls):
        return list(cls.__mapper__.columns)

    @classproperty
    def _s_jsonapi_attrs(cls):
        '''
            :return: list of jsonapi attribute names
            At the moment we expect the column name to be equal to the column name
            Things will go south if this isn't thee case and we should use
            the cls.__mapper__._polymorphic_properties instead
        '''
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
        return cls.__tablename__

    @classproperty
    def _s_type(cls):
        """
            :return: the jsonapi "type", i.e. the tablename if this is a db model, the classname otherwise
        """
        return getattr(cls,'__tablename__',cls.__name__)

    # jsonapi spec doesn't allow "type" as an attribute nmae, but this is a pretty common column name
    # we rename type to Type so we can support it. A bit hacky but better than not supporting "type" at all
    # This may cause other errors too, for ex when sorting
    @property
    def Type(self):
        safrs.log.warning('({}): attribute name "type" is reserved, renamed to "Type"'.format(self))
        return self.type

    @Type.setter
    def Type(self, value):
        # pylint: disable=attribute-defined-outside-init
        if not self.Type == value:
            self.Type = value
        self.type = value

    @property
    def _s_relationships(self):
        """
            :return: the relationships used for jsonapi (de/)serialization
        """
        rels = [ rel for rel in self.__mapper__.relationships if rel.key not in self.exclude_rels ]
        return rels

    @classproperty
    def _s_relationship_names(cls):
        rel_names = [rel.key for rel in cls.__mapper__.relationships if rel.key not in cls.exclude_rels]
        return rel_names

    def _s_patch(self, **attributes):
        columns = {col.name: col for col in self._s_columns}
        for attr, value in attributes.items():
            if attr in columns and attr in self._s_jsonapi_attrs:
                value = self._s_parse_attr_value(attributes, columns[attr])
                setattr(self, attr, value)

    def _s_clone(self, **kwargs):
        """
            Clone an object: copy the parameters and create a new id
        """
        make_transient(self)
        # pylint: disable=attribute-defined-outside-init
        self.id = self.id_type()
        for parameter in self._s_column_names:
            value = kwargs.get(parameter, None)
            if value is not None:
                setattr(self, parameter, value)
        safrs.DB.session.add(self)

    def to_dict(self, fields=None):
        """
            :param fields: if set, fields to include in the result
            :return: dictionary object

            Create a dictionary with all the instance "attributes"
            this method will be called by SAFRSJSONEncoder to serialize objects

            The optional `fields` attribute is used to implement jsonapi "Sparse Fieldsets"
            https://jsonapi.org/format/#fetching-sparse-fieldsets:
              client MAY request that an endpoint return only specific fields in the response on a per-type basis by including a fields[TYPE] parameter.
              The value of the fields parameter MUST be a comma-separated (U+002C COMMA, “,”) list that refers to the name(s) of the fields to be returned.
              If a client requests a restricted set of fields for a given resource type, an endpoint MUST NOT include additional fields in resource objects of that type in its response.
        """
        result = {}
        if fields is None:
            # Check if fields have been provided in the request
            if request:
                fields = request.fields.get(self._s_type, self._s_jsonapi_attrs)
            else:
                fields = self._s_jsonapi_attrs

        # filter the relationships, id & type from the data
        for attr in self._s_jsonapi_attrs:
            if not attr in fields:
                continue
            try:
                result[attr] = getattr(self, attr)
            except:
                log.warning("Failed to fetch {}".format(attr))
                result[attr] = getattr(self, attr.lower())
        return result

    @classmethod
    def _s_count(cls):
        """
            returning None will cause our jsonapi to perform a count() on the result
            this can be overridden with a cached value for performance on large tables (>1G)
        """
        return None

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

        for relationship in self.__mapper__.relationships:
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
                        data = {"id": rel_item.jsonapi_id, "type": rel_item.__tablename__}
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
                                warning = 'Truncated result for relationship "{}",consider paginating this request'.format(
                                    rel_name
                                )
                                safrs.log.warning(warning)
                                meta["warning"] = warning
                            items = rel_query.all()
                        else:
                            items = list(rel_query)
                            count = len(items)
                        meta["count"] = count
                        meta["limit"] = limit
                        data = [{"id": i.jsonapi_id, "type": i.__tablename__} for i in items]
                else:  # shouldn't happen!!
                    safrs.log.error(
                        "Unknown relationship direction for relationship {}: {}".format(
                            rel_name, relationship.direction
                        )
                    )
                # add the relationship direction, for debugging purposes.
                if safrs.log.getEffectiveLevel() < logging.INFO:
                    meta["direction"] = relationship.direction.name

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

        data = dict(
            attributes=attributes,
            id=self.jsonapi_id,
            links={"self": self_link},
            type=self._s_type,
            relationships=relationships,
        )

        return data

    def __iter__(self):
        return iter(self.to_dict())

    def _from_dict(self, data):
        """
            Deserialization (this is handled by __init__ parsing of kwargs for now)
        """
        pass

    def __unicode__(self):
        name = getattr(self, "name", self.__class__.__name__)
        return name

    def __str__(self):
        name = getattr(self, "name", self.__class__.__name__)
        return "<SAFRS {}>".format(name)

    #
    # Following methods are used to create the swagger2 API documentation
    #
    # pylint: disable=
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

    # pylint: disable=
    @classmethod
    def _s_sample(cls):
        """
            :return: a sample instance for the API documentation, i.e. the first item in the DB
        """
        first = None

        try:
            first = cls._s_query.first()
        except Exception as exc:
            safrs.log.warning("Failed to retrieve sample for {}({})".format(cls, exc))
        return first

    @classmethod
    def _s_sample_dict(cls):
        """
            :return: a sample to be used as an example payload in the swagger example
        """
        """sample = cls._s_sample()
        if sample:
            return sample.to_dict()"""
        sample = {}
        for column in cls._s_columns:
            if column.name in ("id", "type") or column.name not in cls._s_jsonapi_attrs:
                continue
            arg = None
            if column.default:
                if callable(column.default.arg):
                    # todo: check how to display the default args
                    continue
                else:
                    arg = column.default.arg
            try:
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
            Returns the Flask url parameter name of the object, e.g. UserId
        """
        # pylint: disable=no-member
        return cls.__name__ + get_config("OBJECT_ID_SUFFIX")

    # pylint: disable=
    @classmethod
    def get_swagger_doc(cls, http_method):
        """
            :param http_method: the http method for which to retrieve the documentation
            :return: swagger `body` and `response` dictionaries

            Create a swagger api model based on the sqlalchemy schema.
        """
        body = {}
        responses = {}
        object_name = cls.__name__

        object_model = cls._get_swagger_doc_object_model()
        responses = {"200": {"description": "{} object".format(object_name), "schema": object_model}}

        if http_method == "patch":
            body = object_model
            responses = {"200": {"description": "Object successfully updated"}}

        if http_method == "post":
            # body = cls.get_swagger_doc_post_parameters()
            responses = {"201": {"description": "Object successfully created"}, "403": {"description": "Invalid data"}}

        if http_method == "get":
            responses = {"200": {"description": "Success"}}
            # responses['200']['schema'] = {'$ref': '#/definitions/{}'.format(object_model.__name__)}
        
        return body, responses

    @classmethod
    def _s_get_jsonapi_rpc_methods(cls):
        """
            :return: a list of jsonapi_rpc methods for this class
        """
        result = []
        # pylint: disable=unused-variable
        for name, method in inspect.getmembers(cls):
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
            if column.name in ("id", "type"):
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

        model_name = "{}_{}".format(cls.__name__, "patch")
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

    def get_attr(self, attr):
        """
            :param attr: jsonapi attribute name
            :return: attribute value from the corresponding column of the sqla object
        """
        if attr in self._s_column_names:
            return getattr(self, attr)

    @classmethod
    def _s_filter(cls, filter_args):
        """
            Apply a filter to this model
            :param filter_args: filter to apply, passed as a request URL parameter
            :return: sqla query object
        """
        safrs.log.info("_s_filter args: {}".format(filter_args))
        safrs.log.info("override the {}._s_filter classmethod to implement your filtering".format(cls.__name__))
        return cls.query


class SAFRSDummy:
    """
        Debug class
    """
    def __getattr__(self, attr):
        print("get", attr)

    def __setattr__(self, attr, val):
        print("set", attr, val)
