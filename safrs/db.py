# -*- coding: utf-8 -*-
#
# SQLAlchemy database schemas
#

# Python3 compatibility
import sys
import inspect
import logging
import sqlalchemy
import pprint
from sqlalchemy import orm
from sqlalchemy.orm.session import make_transient
from sqlalchemy import inspect as sqla_inspect
from flask_marshmallow import Marshmallow
from flask_sqlalchemy import SQLAlchemy
# safrs_rest dependencies:
from .swagger_doc import SchemaClassFactory, documented_api_method, get_doc, jsonapi_rpc
from .errors import GenericError, NotFoundError
from .safrs_types import SAFRSID
from .util import classproperty
from .config import OBJECT_ID_SUFFIX

if sys.version_info[0] == 3:
    unicode = str


#
# Map SQLA types to swagger2 types
#
sqlalchemy_swagger2_type = {
    'INTEGER'   : 'integer',
    'SMALLINT'  : 'integer',
    'NUMERIC'   : 'number',
    'DECIMAL'   : 'integer',
    'VARCHAR'   : 'string',
    'TEXT'      : 'string',
    'DATE'      : 'string',
    'BOOLEAN'   : 'integer',
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
    'NVARCHAR'  : 'string'
}


def init_object_schema(obj):
    '''
        set the json_params attribute
        one-to-one mapping between class attributes and db columns
        json_params specify which class attributes will be serialized to json
    '''

    class ObjectSchema(ma.ModelSchema):
        class Meta:
            model = obj.__class__
            
    obj.__class__.object_schema = ObjectSchema()




from flask_sqlalchemy import Model, SQLAlchemy

#
# SAFRSBase superclass
#
class SAFRSBase(Model):
    '''
        Implement Json Serialization for SAFRSMail SQLalchemy Persistent Objects
        the serialization itself is performed by the to_dict() method
        Initialization and instantiation are quite complex because we rely on the DB schema

        all instances have an id (uuid) and a name

        The object attributes should not match column names, this is why the attributes have the '_s_' prefix!
    '''

    object_schema = None
    id_type = SAFRSID
    query_limit = 50
    db_commit = True   # set this to False if you want to use the SAFRSBase in combination with another framework, eg flask-admin
                       # The caller will have to add and commit the object by itself then...
    
    def __new__(cls, **kwargs):
        '''
            If an object with given arguments already exists, this object is instantiated
        '''
        # Fetch the PKs from the kwargs so we can lookup the corresponding object
        primary_keys = {}
        for col in cls.__table__.columns:
            if col.primary_key:
                primary_keys [ col.name ] = kwargs.get(col.name)

        # Lookup the object with the PKs
        instance = cls.query.filter_by(**primary_keys).first()
        if not instance:
            instance = object.__new__(cls)
        else:
            log.debug('{} exists for {} '.format(cls.__name__, str(kwargs)))
            
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
        
        # Set the json parameters
        init_object_schema(self)
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
            db_args[column.name] = arg_value

        # db_args now contains the class attributes. Initialize the db model with them
        # All subclasses should have the db.Model as superclass.
        # ( SQLAlchemy doesn't work when using db.Model as SAFRSBase superclass )
        try:
            db.Model.__init__(self, **db_args)
        except Exception as exc:
            # OOPS .. things are going bad , this might happen using sqla automap
            log.error('Failed to instantiate object')
            db.Model.__init__(self)
        
        # Parse all provided relationships: empty the existing relationship and 
        # create new instances for the relationship objects
        for rel in relationships:
            continue
            # Create instance for relationships
            if kwargs.get(rel.key):
                rel_attr = getattr(self,rel.key)
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
                # Exception may arise when a db constrained has been violated (e.g. duplicate key)
                raise GenericError(str(exc))


    def _s_expunge(self):
        session = sqla_inspect(self).session
        session.expunge(self)
    
    @classproperty
    def _s_query(cls):
        _table = getattr(cls,'_table', None)
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
            if not attr in ('id', 'type') : 
                # jsonapi schema prohibits the use of these fields in the attributes
                # http://jsonapi.org/format/#document-resource-object-fields
                result.append(attr)
        return result

    @classproperty
    def _s_class_name(cls):
        return cls.__tablename__

    @classproperty
    def _s_type(cls):
        return cls.__tablename__

    @property
    def _s_relationships(self):
        return self.__mapper__.relationships

    def _s_patch(self, **attributes):
        for attr, value in attributes.items():
            if attr in self._s_column_names:
                setattr(self, attr, value)
    
    @classmethod
    #@documented_api_method
    def get_list(self, id_list):
        '''
            description: [deprecated] use csv filter[id] instead
            args:
                id_list:
                    - xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
                    - xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
        '''

        result = []
        for id in id_list:
            instance = self._s_query.get(id)
            if id:
                result.append(instance)

        return result
    
    @classmethod
    #@documented_api_method
    def lookup_re_mysql(cls, **kwargs):
        '''
            pageable: True
            description : Regex search all matching objects (works only in MySQL!!!)
            args:
                name: thom.*
        '''
        from .jsonapi import SAFRSFormattedResponse, paginate, jsonapi_format_response

        result = cls
        response = SAFRSFormattedResponse()
        
        for k, v in kwargs.items():
            column = getattr(cls, k, None)
            if not column:
                raise ValidationError('Invalid Column "{}"'.format(k))
            try:
                result = result.query.filter(column.op('regexp')(v))
                instances = result
                links, instances, count = paginate(instances)
                data = [ item for item in instances ]
                meta = {}
                errors = None
                response.response = jsonapi_format_response(data, meta, links, errors, count)

            except Exception as exc:
                raise GenericError("Failed to execute query {}".format(exc))

        return result.all()

    @classmethod
    #@documented_api_method
    def startswith(cls, **kwargs):
        '''
            pageable: True
            description : lookup column names
            args:
                name: t
        '''
        from .jsonapi import SAFRSFormattedResponse, paginate, jsonapi_format_response

        result = cls
        response = SAFRSFormattedResponse()
        try:
            instances = result.query
            links, instances, count = paginate(instances)
            data = [ item for item in instances ]
            meta = {}
            errors = None
            response.response = jsonapi_format_response(data, meta, links, errors, count)

        except Exception as exc:
            raise GenericError("Failed to execute query {}".format(exc))

        for k, v in kwargs.items():
            column = getattr(cls, k, None)
            if not column:
                raise ValidationError('Invalid Column "{}"'.format(k))
            try:
                instances = result.query.filter(column.like(v + '%'))
                links, instances, count = paginate(instances)
                data = [ item for item in instances ]
                meta = {}
                errors = None
                response.response = jsonapi_format_response(data, meta, links, errors, count)

            except Exception as exc:
                raise GenericError("Failed to execute query {}".format(exc))

        return response


    @classmethod
    def get_instance(cls, item = None, failsafe = False):
        '''
            Parameters:
                item: instance id or dict { "id" : .. "type" : ..}
                failsafe: indicates whether we want an exception to be raised in case the id is not found

            Returns:
                Instance or None. An error is raised if an invalid id is used
        '''
        if isinstance(item, dict):
            id = item.get('id', None)
            if item.get('type') != cls._s_type:
                raise ValidationError('Invalid item type')
        else:
            id = item

        instance = None
        if not id is None or not failsafe:
            try:
                #instance = cls._s_query.filter_by(id=id).first()
                instance = cls._s_query.get(id)
            except Exception as exc:
                log.error('get_instance : ' + str(exc))

            if not instance and not failsafe:
                # TODO: id gets reflected back to the user: should we filter it for XSS ?
                # or let the client handle it?
                raise NotFoundError('Invalid "{}" ID "{}"'.format(cls.__name__, id))
        return instance

    def clone(self, **kwargs):
        '''
            Clone an object: copy the parameters and create a new id
        '''

        make_transient(self)
        self.id = self.id_type()
        for parameter in self._s_column_names:
            value = kwargs.get(parameter, None)
            if value != None:
                setattr(self, parameter, value)
        db.session.add(self)

    @orm.reconstructor
    def init_object_schema(self):
        init_object_schema(self)

    def _s_to_dict(self):
        '''
            Serialization
            Create a dictionary with all the object parameters
            this method will be called by SAFRSJSONEncoder to serialize objects
        '''
        result = {}
        # filter the relationships, id & type from the data
        for attr in self._s_jsonapi_attrs:
            result[attr] = getattr(self, attr)
        return result

    to_dict = _s_to_dict

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
    @classmethod
    def sample_id(cls):
        '''
            Retrieve a sample id for the API documentation, i.e. the first item in the DB
        '''
        id = cls.id_type()
        sample = cls.sample()
        if sample and not getattr(sample, 'id', None) is None:
            id = sample.id
        return id

    @classmethod
    def sample(cls):
        '''
            Retrieve a sample instance for the API documentation, i.e. the first item in the DB
        '''

        first = None
        try:
            first = cls._s_query.first()
        except Exception as exc:
            log.warning('Failed to retrieve sample for {}({})'.format(cls, exc))
        return first
        
    #pylint: disable=
    @classproperty
    def object_id(cls):
        '''
            Returns the Flask url parameter name of the object, e.g. UserId
        '''

        return cls.__name__ + OBJECT_ID_SUFFIX

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
            responses = { '200' : {
                                    'description' : 'Success',
                                  }
                        }
            #responses['200']['schema'] = {'$ref': '#/definitions/{}'.format(object_model.__name__)}

        return body, responses

    @classmethod
    def get_documented_api_methods(cls):
        '''

        '''
        result = []
        for method_name, method in inspect.getmembers(cls):
            rest_doc = get_doc(method)
            if rest_doc != None:
                result.append(method)

        return result

    @classmethod
    def get_swagger_doc_object_model(cls):
        '''
            Create a schema for object creation and updates through the HTTP PUT interface

            The schema is created using the sqlalchemy database schema. So there 
            is a one-to-one mapping between json input data and db columns 
        '''

        fields = {}    
        sample_id = cls.sample_id()
        sample_instance  = cls.get_instance(sample_id, failsafe = True)

        for column in cls._s_columns:
            if column.name == 'id': 
                continue
            # convert the column type to string and map it to a swagger type
            column_type  = str(column.type)
            if '(' in column_type:
                column_type = column_type.split('(')[0]
            swagger_type = sqlalchemy_swagger2_type[column_type]
            default = getattr(sample_instance, column.name, None)
            if default is None:
                # swagger api spec doesn't support nullable values
                continue
            field = {'type' : swagger_type,
                     'example' : unicode(default)} # added unicode for datetime encoding
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


log = logging.getLogger(__name__)
#
# Work around flask-sqlalchemy's session crap
# ( globals() doesn't work when using "builtins" module )
# If db isn't specified we want to use the declarative base
#
def get_db():
    try:
        return db
    except:
        log.warning('Reinitializing Database')
        return SQLAlchemy()

db = get_db()
ma = Marshmallow()
