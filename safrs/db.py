# -*- coding: utf-8 -*-
#
# SQLAlchemy database schemas
#

# Python3 compatibility
import sys

if sys.version_info[0] == 3:
    unicode = str

import re
import json
import time
import uuid
import inspect
import hashlib
import datetime
import logging

import sqlalchemy
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import desc, orm, Column, ForeignKey, func, and_, or_, Table
from sqlalchemy.orm import scoped_session, sessionmaker, relationship, backref
from sqlalchemy.orm import synonym
from sqlalchemy.orm.session import make_transient
from sqlalchemy.types import PickleType, Text, String, Integer, DateTime, TypeDecorator, Integer
try:
    from validate_email import validate_email
except:
    pass

from sqlalchemy.orm.interfaces import ONETOMANY, MANYTOONE , MANYTOMANY 
from werkzeug import secure_filename
from flask_sqlalchemy import SQLAlchemy
# safrs_rest dependencies:
from safrs.swagger_doc import SchemaClassFactory, documented_api_method, get_doc
from safrs.errors import ValidationError, GenericError, NotFoundError
import pprint
from flask_sqlalchemy import SQLAlchemy

from flask_marshmallow import Marshmallow

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
    'TIMESTAMP' : 'string'
}


STRIP_SPECIAL = '[^\w|%|:|/|-|_\-_\. ]'



class JSONType(PickleType):
    '''
        JSON DB type is used to store JSON objects in the database
    '''

    impl = Text

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
            result = re.sub(STRIP_SPECIAL, '_', str(value).decode('utf-8') )
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


def init_object_schema(obj):
    '''
        set the json_params attribute
        one-to-one mapping between class attributes and db columns
        json_params specify which class attributes will be serialized to json
    '''

    class ObjectSchema(ma.ModelSchema):
        class Meta:
            model = obj.__class__

    obj.object_schema = ObjectSchema()
    obj.json_params = [ col.name for col in obj.__table__.columns ]
    return obj.object_schema


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


class ClassPropertyDescriptor(object):

    def __init__(self, fget, fset=None):
        self.fget = fget
        self.fset = fset

    def __get__(self, obj, klass=None):
        if klass is None:
            klass = type(obj)
        return self.fget.__get__(obj, klass)()

    def __set__(self, obj, value):
        if not self.fset:
            raise AttributeError("can't set attribute")
        type_ = type(obj)
        return self.fset.__get__(obj, type_)(value)

    def setter(self, func):
        if not isinstance(func, (classmethod, staticmethod)):
            func = classmethod(func)
        self.fset = func
        return self    

def classproperty(func):
    if not isinstance(func, (classmethod, staticmethod)):
        func = classmethod(func)

    return ClassPropertyDescriptor(func)


#
# SAFRSBase superclass
#
class SAFRSBase(object):
    '''
        Implement Json Serialization for SAFRSMail SQLalchemy Persistent Objects
        the serialization itself is performed by the to_dict() method
        Initialization and instantiation are quite complex because we rely on the DB schema

        all instances have an id (uuid) and a name
    '''

    object_schema = None
    json_params = None
    id_type = SAFRSID
    
    @classproperty
    def query(cls):
        _table = getattr(cls,'_table', None)
        if _table:
            return db.session.query(_table)    
        return db.session.query(cls)

    @classproperty
    def columns(cls):
        return list(cls.__mapper__.columns)

    @classproperty
    def type(cls):
        return cls.__tablename__

    @classmethod
    def get_endpoint(cls, url_prefix = '/'):
        endpoint = '{}api.{}'.format(url_prefix, cls.__tablename__)
        return endpoint

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

    def __init__(self, *args, **kwargs ):
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
        relationships = self.__mapper__.relationships
        for column in columns:
            arg_value = kwargs.get(column.name, None)
            if arg_value == None and column.default:
                arg_value = column.default.arg
            db_args[column.name] = arg_value

        # db_args now contains the class attributes. Initialize the db model with them
        # All subclasses should have the db.Model as superclass.
        # ( SQLAlchemy doesn't work when using db.Model as SAFRSBase superclass )
        db.Model.__init__(self, **db_args)

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

        db.session.add(self)
        try:
            db.session.commit()
        except sqlalchemy.exc.SQLAlchemyError as exc:
            # Exception may arise when a db constrained has been violated (e.g. duplicate key)
            raise GenericError(str(exc))

    def patch(self, **kwargs):
        for attr in self.json_params:
            value = kwargs.get(attr,None)
            if value:
                setattr(self, attr, value)
    
    @classmethod
    @documented_api_method
    def get_list(self, id_list):
        '''
            description: Retrieve a list of objects with the ids in id_list.
            args:
                id_list:
                    - xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
                    - xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
        '''

        result = []
        for id in id_list:
            instance = self.query.get(id)
            if id:
                result.append(instance)

        return result

    @classmethod
    @documented_api_method
    def lookup(cls,  *args, **kwargs):
        '''
            description : Retrieve all matching objects
            args:
                name: thomas
            --------
            This is actually a wrapper for query, but .query is already taken :)
        '''
        
        try:
            result = cls.query.filter_by(**kwargs).all()
        except Exception as exc:
            raise GenericError("Failed to execute query {}".format(exc))

        return result
    
    @classmethod
    def get_instance(cls, id = None, failsafe = False):
        '''
            Parameters:
                id: instance id

            Returns:
                Instance or None. An error is raised if an invalid id is used
        '''

        instance = None
        if id:
            try:
                instance = cls.query.filter_by(id=id).first()
            except Exception as e:
                log.critical(e)

            if not instance and not failsafe:
                # TODO: id gets reflected back to the user: should we filter it for XSS ?
                # or let the client handle it?
                raise NotFoundError('Invalid "{}" ID "{}"'.format(cls.__name__, id))
        return instance

    def clone(self, *args, **kwargs):
        '''
            Clone an object: copy the parameters and create a new id
        '''

        make_transient(self)
        self.id = self.id_type()
        for parameter in self.json_params:
            value = kwargs.get(parameter, None)
            if value != None:
                setattr(self, parameter, value)
        db.session.add(self)

    @orm.reconstructor
    def init_object_schema(self):
        init_object_schema(self)
        
    def to_dict(self):
        '''
            Create a dictionary with all the object parameters
            this method will be called by SAFRSJSONEncoder 

        '''

        result = {}
        for f in self.json_params:
            if f in ( 'id' , 'type' ) : # jsonapi schema prohibits the use of these fields in the attributes
                continue
            value = getattr(self,f)
            if value == None:
                value = ""
            result[f] = value
        return result

    def __unicode__(self):
        name = getattr(self,'name',self.__class__.__name__)
        return name

    def __str__(self):
        name = getattr(self,'name',self.__class__.__name__)
        return '<SAFRS {}>'.format(name)

    #
    # Following methods are used to create the swagger2 API documentation
    #
    @classmethod
    def sample_id(cls):
        '''
            Retrieve a sample id for the API documentation, i.e. the first item in the DB
        '''

        sample = cls.sample()
        if sample and getattr(sample, 'id', None):
            return sample.id
        else:
            return cls.id_type()

    @classmethod
    def sample(cls):
        '''
            Retrieve a sample instance for the API documentation, i.e. the first item in the DB
        '''

        first = None
        try:
            first = cls.query.first()
        except Exception as e:
            log.warning('Failed to retrieve sample for {}({})'.format(cls,e))
        return first
        

    @classproperty
    def object_id(cls):
        '''
            Returns the Flask url parameter name of the object, e.g. UserId
        '''

        OBJECT_ID ='{}Id'
        return OBJECT_ID.format(cls.__name__)

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
        responses = { '200': {  
                                'description' : '{} object'.format(object_name),
                                'schema': object_model
                             }
                    }

        if http_method == 'patch':
            body = object_model
            responses = { '200' : {
                                    'description' : 'Object successfully Updated',
                                  }
                        }

        if http_method == 'post':
            #body = cls.get_swagger_doc_post_parameters()
            responses = { '200' : {
                                    'description' : 'API call processed successfully',
                                  }
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

        result = []
        for method_name, method in inspect.getmembers(cls):
            fields = {}
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

        for column in cls.__table__.columns:
            if column.name == 'id' : continue
            # convert the column type to string and map it to a swagger type
            column_type  = str(column.type)
            if '(' in column_type:
                column_type = column_type.split('(')[0]
            swagger_type = sqlalchemy_swagger2_type[column_type]
            default = getattr(sample_instance, column.name, None)
            if default == None:
                # swagger api spec doesn't support nullable values
                continue
            field = { 
                      'type' : swagger_type,
                      'example' : unicode(default) # added unicode for datetime encoding
                    }
            fields[column.name] = field

        model_name = '{}_{}'.format(cls.__name__, 'patch')
        model = SchemaClassFactory(model_name, fields)
            
        return model

    def jsonapi_encode(self, ):
        '''
            Encode object according to the jsonapi specification
        '''
        from flask import url_for
        relationships = dict()
        
        for relationship in self.__mapper__.relationships:
            
            try:
                #params = { self.object_id : self.id }
                #obj_url = url_for(self.get_endpoint(), **params) # Doesn't work :(, todo : why?
                obj_url = url_for(self.get_endpoint())
                if not obj_url.endswith('/'):
                    obj_url += '/'
            except:
                # app not initialized
                obj_url = ''
            
            rel_name = relationship.key
            if relationship.direction in (ONETOMANY, MANYTOMANY):
                items = list(getattr(self, rel_name, []))
                data  = [] # [{ 'id' : i.id , 'type' : self.__name__ } for i in items]
            else:
                data = None
            
            #self_link = '{}/{}/relationships/{}'.format(obj_url,
            self_link = '{}{}/{}'.format( obj_url,
                                          self.id,
                                          rel_name)
            links  = dict( self = self_link, related = '' )
            
            relationships[rel_name] = dict(links = links, data = data)

        data = dict( attributes = self.to_dict(),
                     id = self.id,
                     type = self.type,
                     relationships = relationships
                    )
        
        return data


log = logging.getLogger(__name__)
#
# Fix flask-sqlalchemy's stupid session crap
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
