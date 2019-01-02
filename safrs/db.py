# -*- coding: utf-8 -*-
#
# SQLAlchemy database schemas
#
import sys
import inspect
import datetime
import logging
import sqlalchemy
import safrs
from sqlalchemy import orm
from sqlalchemy.orm.session import make_transient
from sqlalchemy import inspect as sqla_inspect
from flask_sqlalchemy import SQLAlchemy, Model
# safrs_rest dependencies:
from .swagger_doc import SchemaClassFactory, documented_api_method, get_doc, jsonapi_rpc
from .errors import GenericError, NotFoundError, ValidationError
from .safrs_types import SAFRSID, get_id_type
from .util import classproperty
from .config import OBJECT_ID_SUFFIX
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method

db = safrs.db

#
# Map SQLA types to swagger2 json types
# json supports only a couple of basic data types, which makes our job pretty easy :)
#
SQLALCHEMY_SWAGGER2_TYPE = {
    'INTEGER'   : 'integer',
    'SMALLINT'  : 'integer',
    'NUMERIC'   : 'number',
    'DECIMAL'   : 'integer',
    'VARCHAR'   : 'string',
    'TEXT'      : 'string',
    'DATE'      : 'string',
    'BOOLEAN'   : 'boolean',
    'BLOB'      : 'string',
    'BYTEA'     : 'string',
    'BINARY'    : 'string',
    'VARBINARY' : 'string',
    'FLOAT'     : 'number',
    'REAL'      : 'number',
    'DATETIME'  : 'string',
    'BIGINT'    : 'integer',
    'ENUM'      : 'string',
    'INTERVAL'  : 'string',
    'CHAR'      : 'string',
    'TIMESTAMP' : 'string',
    'TINYINT'   : 'integer',
    'MEDIUMINT' : 'integer',
    'NVARCHAR'  : 'string',
    'YEAR'      : 'integer',
    'SET'       : 'string',
    'LONGBLOB'  : 'string',
    'TINYTEXT'  : 'string',
    'LONGTEXT'  : 'string',
    'MEDIUMTEXT': 'string',
    'UUID'      : 'string'
}


#
# SAFRSBase superclass
#
class SAFRSBase(Model):
    '''
        This class implements Json Serialization for SAFRS SQLalchemy Persistent Objects
        Serialization itself is performed by the ``to_dict`` method
        Initialization and instantiation are quite complex because we rely on the DB schema

        The jsonapi id is generated from the primary keys of the columns

        The object attributes should not match column names,
        this is why the attributes have the '_s_' prefix!
    '''

    query_limit = 50
    # set this to False if you want to use the SAFRSBase in combination
    # with another framework, eg flask-admin
    # The caller will have to add and commit the object by itself then...
    db_commit = True
    def __new__(cls, **kwargs):
        '''
            If an object with given arguments already exists, this object is instantiated
        '''
        '''if getattr(cls, 'id_type', None) is None:
            cls.id_type = get_id_type(cls)'''
        # Fetch the PKs from the kwargs so we can lookup the corresponding object
        primary_keys = cls.id_type.get_pks(kwargs.get('id', ''))
        # Lookup the object with the PKs
        instance = cls.query.filter_by(**primary_keys).first()
        if not instance:
            instance = object.__new__(cls)
        else:
            safrs.LOGGER.debug('{} exists for {} '.format(cls.__name__, str(kwargs)))

        return instance

    def __init__(self, *args, **kwargs):
        '''
            Object initialization:
            - set the named attributes and add the object to the database
            - create relationships
        '''

        # All SAFRSBase subclasses have an id,
        # if no id is supplied, generate a new safrs id (uuid4)
        # instantiate the id with the "id_type", this will validate the id if
        # validation is implemented
        kwargs['id'] = self.id_type(kwargs.get('id', None))

        # Initialize the attribute values: these have been passed as key-value pairs in the
        # kwargs dictionary (from json).
        # Retrieve the values from each attribute (== class table column)
        db_args = {}
        columns = self.__table__.columns
        relationships = self._s_relationships
        for column in columns:
            arg_value = kwargs.get(column.name, None)
            if arg_value is None and column.default:
                arg_value = column.default.arg

            # Parse datetime and date values
            if column.type.python_type == datetime.datetime:
                arg_value = datetime.datetime.strptime(str(arg_value), '%Y-%m-%d %H:%M:%S.%f')
            elif column.type.python_type == datetime.date:
                arg_value = datetime.datetime.strptime(str(arg_value), '%Y-%m-%d')

            db_args[column.name] = arg_value

        # db_args now contains the class attributes. Initialize the DB model with them
        # All subclasses should have the DB.Model as superclass.
        # ( SQLAlchemy doesn't work when using DB.Model as SAFRSBase superclass )
        try:
            db.Model.__init__(self, **db_args)
        except Exception as exc:
            # OOPS .. things are going bad , this might happen using sqla automap
            safrs.LOGGER.error('Failed to instantiate object')
            db.Model.__init__(self)

        # Parse all provided relationships: empty the existing relationship and
        # create new instances for the relationship objects
        for rel in relationships:
            continue
            # Create instance for relationships
            if kwargs.get(rel.key):
                rel_attr = getattr(self, rel.key)
                del rel_attr[:]
                rel_params = kwargs.get(rel.key)
                for rel_param in rel_params:
                    rel_object = rel.mapper.class_(**rel_param)
                    rel_attr.append(rel_object)

        if self.db_commit:
            # Add the object to the database if specified by the class parameters
            db.session.add(self)
            try:
                db.session.commit()
            except sqlalchemy.exc.SQLAlchemyError as exc:
                # Exception may arise when a DB constrained has been violated (e.g. duplicate key)
                raise GenericError(str(exc))

    def _s_expunge(self):
        session = sqla_inspect(self).session
        session.expunge(self)

    @property
    def jsonapi_id(self):
        '''
            jsonapi_id: if the table/object has a single primary key "id", it will return this id
            in the other cases, the jsonapi "id" will be generated by the cls.id_type
        '''
        return self.id_type.get_id(self)

    @hybrid_property
    def id_type(obj):
        '''
            
        '''
        id_type = get_id_type(obj)
        # monkey patch so we don't have to look it up next time
        obj.id_type = id_type
        return id_type

    @classproperty
    def _s_query(cls):
        _table = getattr(cls, '_table', None)
        if _table:
            return db.session.query(_table)
        return db.session.query(cls)

    query = _s_query

    @classproperty
    def _s_column_names(cls):
        return [c.name for c in cls.__mapper__.columns]

    @classproperty
    def _s_columns(cls):
        return list(cls.__mapper__.columns)

    @classproperty
    def _s_jsonapi_attrs(cls):
        result = []
        for attr in cls._s_column_names:
            # jsonapi schema prohibits the use of the fields 'id' and 'type' in the attributes
            # http://jsonapi.org/format/#document-resource-object-fields
            if attr == 'type':
                # translate type to Type
                result.append('Type')
            elif not attr == 'id':
                result.append(attr)

        return result
    
    #pylint: disable=
    @classproperty
    def _s_class_name(cls):
        return cls.__tablename__

    #pylint: disable=
    @classproperty
    def _s_type(cls):
        return cls.__tablename__

    # jsonapi spec doesn't allow "type" as an attribute nmae, but this is a pretty common column name
    # we rename type to Type so we can support it. A bit hacky but better than not supporting "type" at all
    @property
    def Type(self):
        log.warning('attribute "type" is not supported ({}), renamed to "Type"'.format(self))
        return self.type

    @Type.setter
    def Type(self, value):
        if not self.Type == value:
            self.Type = value
        self.type = value
    
    

    @property
    def _s_relationships(self):
        return self.__mapper__.relationships

    def _s_patch(self, **attributes):
        for attr, value in attributes.items():
            if attr in self._s_column_names:
                setattr(self, attr, value)
    #pylint: disable=
    @classmethod
    def get_instance(cls, item=None, failsafe=False):
        '''
        Parameters:
            item: instance id or dict { "id" : .. "type" : ..}
            failsafe: indicates whether we want an exception to be raised
                      in case the id is not found

            Returns:
                Instance or None. An error is raised if an invalid id is used
        '''
        if isinstance(item, dict):
            id = item.get('id', None)
            if item.get('type') != cls._s_type:
                raise ValidationError('Invalid item type')
        else:
            id = item

        try:
            primary_keys = cls.id_type.get_pks(id)
        except AttributeError:
            # This happens when we request a sample from a class that is not yet loaded
            # when we're creating the swagger models
            safrs.LOGGER.info('AttributeError for class "{}"'.format(cls.__name__))
            return

        instance = None
        if not id is None or not failsafe:
            try:
                instance = cls.query.filter_by(**primary_keys).first()
            except Exception as exc:
                safrs.LOGGER.error('get_instance : %s', str(exc))
            
            if not instance and not failsafe:
                # TODO: id gets reflected back to the user: should we filter it for XSS ?
                # or let the client handle it?
                raise NotFoundError('Invalid "{}" ID "{}"'.format(cls.__name__, id))
        return instance

    def _s_clone(self, **kwargs):
        '''
            Clone an object: copy the parameters and create a new id
        '''

        make_transient(self)
        self.id = self.id_type()
        for parameter in self._s_column_names:
            value = kwargs.get(parameter, None)
            if value is not None:
                setattr(self, parameter, value)
        db.session.add(self)

    @orm.reconstructor
    def init_object_schema(self):
        '''
        init_object_schema
        '''
        pass

    def _s_to_dict(self):
        '''
            Serialization
            Create a dictionary with all the object parameters
            this method will be called by SAFRSJSONEncoder to serialize objects
        '''
        result = {}
        # filter the relationships, id & type from the data
        for attr in self._s_jsonapi_attrs:
            try:
                result[attr] = getattr(self, attr)
            except:
                result[attr] = getattr(self, attr.lower())
        return result

    to_dict = _s_to_dict

    def __iter__(self):
        return iter(self._s_to_dict())

    def _s_from_dict(self, data):
        '''
            Deserialization
        '''
        pass

    def __unicode__(self):
        name = getattr(self, 'name', self.__class__.__name__)
        return name

    def __str__(self):
        name = getattr(self, 'name', self.__class__.__name__)
        return '<SAFRS {}>'.format(name)

    #
    # Following methods are used to create the swagger2 API documentation
    #
    #pylint: disable=
    @classmethod
    def _s_sample_id(cls):
        '''
        Retrieve a sample id for the API documentation, i.e. the first item in the DB
        '''
        sample = cls._s_sample()
        if sample:
            id = sample.jsonapi_id
        else:
            id = ""
        return id
  
    #pylint: disable=
    @classmethod
    def _s_sample(cls):
        '''
        Retrieve a sample instance for the API documentation, i.e. the first item in the DB
        '''
        first = None

        try:
            first = cls._s_query.first()
        except Exception as exc:
            safrs.LOGGER.warning('Failed to retrieve sample for {}({})'.format(cls, exc))
        return first

    @classmethod
    def _s_sample_dict(cls):
        sample = cls._s_sample()
        if sample:
            return sample._s_to_dict()
        
        sample = {}
        for column in cls._s_columns:
            if column.name in ('id','type'):
                continue
            arg = ''
            try:
                arg = column.type.python_type()
            except:
                safrs.LOGGER.debug('Failed to get python type for column {}'.format(column))
            if column.default:
                arg = column.default.arg

            sample[column.name] = arg
        return sample

    #pylint: disable=
    @classproperty
    def object_id(cls):
        '''
            Returns the Flask url parameter name of the object, e.g. UserId
        '''
        return cls.__name__ + OBJECT_ID_SUFFIX
    #pylint: disable=
    @classmethod
    def get_swagger_doc(cls, http_method):
        '''
            Create a swagger api model based on the sqlalchemy schema
            if an instance exists in the DB, the first entry is used as example
        '''

        body = {}
        responses = {}
        object_name = cls.__name__

        object_model = cls.get_swagger_doc_object_model()
        responses = {'200': {
                             'description' : '{} object'.format(object_name),
                             'schema': object_model
                            }
                    }

        if http_method == 'patch':
            body = object_model
            responses = {'200' : {
                                  'description' : 'Object successfully updated',
                                }
                        }

        if http_method == 'post':
            #body = cls.get_swagger_doc_post_parameters()
            responses = {'201' : {
                                  'description' : 'Object successfully created',
                                },
                         '403' : {
                                  'description' : 'Invalid data',
                                },
                        }

        if http_method == 'get':
            responses = {'200' : {
                                  'description' : 'Success',
                                }
                        }
            #responses['200']['schema'] = {'$ref': '#/definitions/{}'.format(object_model.__name__)}

        return body, responses

    @classmethod
    def get_documented_api_methods(cls):
        '''
        Retrieve the jsonapi_rpc methods (fka documented_api_method)
        get_documented_api_methods
        '''
        result = []
        for name, method in inspect.getmembers(cls):
            rest_doc = get_doc(method)
            if rest_doc is not None:
                result.append(method)
        return result

    @classmethod
    def get_swagger_doc_object_model(cls):
        '''
            Create a schema for object creation and updates through the HTTP PATCH and POST interfaces
            The schema is created using the sqlalchemy database schema. So there
            is a one-to-one mapping between json input data and db columns
        '''
        fields = {}
        sample_id = cls._s_sample_id()
        sample_instance = cls.get_instance(sample_id, failsafe=True)
        for column in cls._s_columns:
            if column.name in ('id', 'type'):
                continue
            # convert the column type to string and map it to a swagger type
            column_type = str(column.type)
            # Take care of extended column type declarations, eg. TEXT COLLATE "utf8mb4_unicode_ci" > TEXT
            column_type = column_type.split('(')[0]
            column_type = column_type.split(' ')[0]
            swagger_type = SQLALCHEMY_SWAGGER2_TYPE.get(column_type,None)
            if swagger_type is None:
                safrs.LOGGER.warning('Could not match json datatype for db column type `{}`, using "string" for {}.{}'.format(column_type, cls.__tablename__, column.name))
                swagger_type = 'string'
            default = getattr(sample_instance, column.name, None)
            if default is None:
                # swagger api spec doesn't support nullable values
                continue

            field = {'type' : swagger_type,
                     'example' : str(default) } # added unicode str() for datetime encoding
            fields[column.name] = field

        model_name = '{}_{}'.format(cls.__name__, 'patch')
        model = SchemaClassFactory(model_name, fields)
        return model

    @classmethod
    def get_endpoint(cls, url_prefix=''):
        '''
            Return the API endpoint
        '''
        endpoint = '{}api.{}'.format(url_prefix, cls._s_type)
        return endpoint

    @classmethod
    def _s_meta(cls):
        '''
            What is returned in the "meta" part
            may be implemented by the app
        '''
        return {}

