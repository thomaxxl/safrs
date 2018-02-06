#
# Functions for api documentation: these decorators generate the swagger schemas
#
import inspect, yaml, uuid, logging
from flask_restful_swagger_2 import Schema, swagger
from safrs.errors import ValidationError
from safrs.config import USE_API_METHODS

log = logging.getLogger()

REST_DOC  = '__rest_doc' # swagger doc attribute name. If this attribute is set 
                         # this means that the function is reachable through HTTP POST
DOC_DELIMITER = '----'   # used as delimiter between the rest_doc swagger yaml spec and regular documentation

def parse_object_doc(object):
    '''
        Parse the yaml description from the "documented_api_method"-decorated methods
    '''

    api_doc  = {}
    obj_doc  = str(inspect.getdoc(object))    
    yaml_doc = None
    raw_doc  = obj_doc.split(DOC_DELIMITER)[0]
    try:
        yaml_doc = yaml.load(raw_doc)
    except SyntaxError:
        pass                
        
    except Exception as e:
        raise ValidationError('Failed to parse api doc')    
    
    if isinstance(yaml_doc, dict):
        api_doc.update(yaml_doc)

    return api_doc


def documented_api_method(func):
    '''
        Decorator to expose functions in the REST API:
        When a method is decorated with documented_api_method, this means
        it becomes available for use through HTTP POST (i.e. public)
    '''
    if USE_API_METHODS:
        api_doc = parse_object_doc(func)
        setattr(func, REST_DOC, api_doc)
    return func


def is_public(method):
    return hasattr(method, REST_DOC)

def get_doc(method):
    return getattr(method, REST_DOC, None)


def SchemaClassFactory(name, properties):
    '''
        Generate a Schema class, used to describe swagger schemas
    '''

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            # here, the properties variable is the one passed to the
            # ClassFactory call
            if key not in properties:
                raise ValidationError('Argument {} not valid for {}'.format( 
                                       (key, self.__class__.__name__) ))
            setattr(self, key, value)
    
    newclass = type( name, 
                     (Schema,),
                     {'__init__': __init__,
                      'properties' : properties
                    })
    
    return newclass


def schema_from_object(name, object):

    def replace_None(object):
        # None aka "null" is invalid in swagger schema definition => recursively replace all "None" by ""
        if object is None:
            return ''
        if type(object) is dict:
            result = {}
            for k, v in object.items():
                v = replace_None(v)
                result[k] = v
            return result
        if type(object) is list:
            result = []
            for i in object:
                result.append(replace_None(i))
            return result
        return object

    properties = {}

    if type(object) == str:
        properties = { 'example' : k, 'type' : 'string' }
    
    elif type(object) == int:
        properties = { 'example' : k, 'type' : 'integer' }

    elif type(object) == dict:
        for k, v in object.items():
            if type(v) == str:
                properties[k] = { 'example' : v, 'type' : 'string' }
            if type(v) == int:
                properties[k] = { 'example' : v, 'type' : 'integer' }
            if type(v) == dict or type(v) == list:
                if type(v) == dict:
                    v = replace_None(v)
                properties[k] = { 'example' : v, 'type' : 'string' }
            if v is None:
                properties[k] = { 'example' : "", 'type' : 'string' }
    else:
        raise ValidationError('Invalid schema object type {}'.format(type(object)))

    # generate random name 
    return SchemaClassFactory(name + str(uuid.uuid4()), properties)



def get_swagger_doc_post_arguments(cls, method_name = None):
    '''
        create a schema for all methods which can be called through the
        REST POST interface

        A method is called with following JSON payload:
        { 
            "meta"   : { 
                         "args" : { 
                                    "parameter1" : "value1" ,
                                    "parameter2" : "value2" , 
                                  }
                       } 
        }

        The schema is created using the values from the documented_api_method decorator,
        returned by get_doc() 

        We use "meta" to remain compliant with the jsonapi schema
    '''

    parameters = []

    #for method_name, method in inspect.getmembers(cls, predicate=inspect.ismethod):
    for name, method in inspect.getmembers(cls):
        if name != method_name: 
            continue
        fields = {}
        rest_doc = get_doc(method)
        description = rest_doc.get('description','')
        if rest_doc:
            
            method_args = rest_doc.get('args',[])
            if method_args:
                model_name = '{}_{}'.format(cls.__name__, method_name)
                model = SchemaClassFactory(model_name, method_args )
                method_field = {
                                 'method' : method_name,
                                 'args' : method_args,
                                }
                fields['meta'] = schema_from_object(model_name, method_field)

            elif method_args:
                model_name = '{}_{}'.format(cls.__name__, method_name)
                model = SchemaClassFactory(model_name, method_args )
                arg_field = { 
                               'schema' : model,
                               'type'   : 'string',
                            }
                fields['meta'] = arg_field

        return fields, description, method

    log.critical('Shouldnt get here')



def swagger_method_doc(cls, method_name, tags = None):

    def swagger_doc_gen( func ):
        
        class_name = cls.__name__
        if tags == None :
            doc_tags = [ table_name ]
        else:
            doc_tags = tags

        doc = { 'tags': doc_tags,
                'description': 'Invoke {}.{}'.format(class_name, method_name),
                'summary': 'Invoke {}.{}'.format(class_name, method_name),
              }

        model_name  = '{} {} {}'.format('invoke ', class_name, method_name)
        param_model = SchemaClassFactory(model_name, {})

        post_param, description, method = get_swagger_doc_post_arguments(cls, method_name)

        '''if inspect.ismethod(method) and method.__self__ is cls:
            # Mark classmethods: only these can be called when no {id} is given as parameter
            # in the swagger ui
            description += ' (classmethod)' '''

            
        parameters = []
        #
        # Retrieve the swagger schemas for the documented_api_methods
        #
        model_name  = '{} {} {}'.format(func.__name__, cls.__name__, method_name)
        param_model = SchemaClassFactory(model_name, post_param)
        parameters.append({
                            'name': model_name,
                            'in': 'body',
                            'description' : description,
                            'schema' : param_model,
                            'required' : True
                          })

        # URL Path Parameter
        default_id  = cls.sample_id()
        parameters.append({
                        'name': cls.object_id, # parameter id, e.g. UserId
                        'in': 'path',
                        'type': 'string',
                        'default': default_id,
                        'required' : True
                      })

        doc['parameters'] = parameters
        doc["produces"]   = [ "application/json" ]
        doc['responses']  = responses = { '200' : { 
                                    'description' : 'Success' 
                                    }
                        }

        #doc['parameters'] = [{'required': True, 'name': 'post Hash get_list', 'schema': param_model, 'type': 'string', 'in': 'body', 'description': 'Retrieve a list of objects with the ids in id_list. (classmethod)'}]

        @swagger.doc(doc)
        def wrapper( self, *args, **kwargs ):
            val = func( self, *args, **kwargs )
            return val
        
        return wrapper

    return swagger_doc_gen

#
# Decorator is called when a swagger endpoint class is instantiated
# from API.expose_object eg.
#
def swagger_doc(cls, tags = None):

    def swagger_doc_gen( func ):
        '''
            Decorator used to document (SAFRSBase) class methods exposed in the API
        '''
        
        default_id  = cls.sample_id()
        class_name  = cls.__name__ 
        table_name  = cls.__tablename__
        http_method = func.__name__.lower()
        parameters  = [{
                        'name': cls.object_id, # parameter id, e.g. UserId
                        'in': 'path',
                        'type': 'string',
                        'default': default_id,
                        'required' : True
                      }]
        
        if tags == None :
            doc_tags = [ table_name ]
        else:
            doc_tags = tags

        doc = { 'tags': doc_tags,
                'description': 'Returns a {}'.format(class_name),
              }

        responses = {}

        if http_method == 'get':
            doc['summary'] =  'Retrieve a {} object'.format(class_name)
            _ , responses = cls.get_swagger_doc(http_method)
            
        elif http_method == 'post':
            _, responses = cls.get_swagger_doc(http_method)
            doc['summary'] =  'Create a {} object'.format(class_name)

            #
            # Create the default POST body schema
            #        
            sample = cls.sample()
            if sample:
                sample_data = schema_from_object('{} POST sample'.format(class_name) ,
                                                { 'data' : 
                                                    { 'attributes' : sample._s_to_dict(), 
                                                      'id' : cls.sample_id(),
                                                      'type' : class_name 
                                                    }
                                                })
            elif cls.sample_id():
                sample_data = schema_from_object('{} POST sample'.format(class_name) ,
                                                { 'data' : 
                                                    { 'attributes' : {}, 
                                                      'id' : cls.sample_id(),
                                                      'type' : class_name 
                                                    }
                                                })
            else:
                sample_data = {}
            
            post_model = SchemaClassFactory('POST body {}'.format(class_name), {'data': sample_data })
            parameters.append({
                                'name': 'POST body',
                                'in': 'body',
                                'description' : '{} attributes'.format(class_name),
                                'schema' : sample_data,
                                'required' : True
                              })

        elif http_method == 'delete':
            doc['summary'] =  doc['description'] = 'Delete a {} object'.format(class_name)
            responses = { '204' : { 
                                    'description' : 'Object Deleted' 
                                    },
                          '404' : { 
                                    'description' : 'Object Not Found' 
                                    }
                        }

        elif http_method == 'patch':
            doc['summary'] =  'Update a {} object'.format(class_name)
            post_model, responses = cls.get_swagger_doc('patch')
            sample = cls.sample()
            if sample:
                sample_data = schema_from_object('{} POST sample'.format(class_name) ,
                                                { 'data' : 
                                                    { 'attributes' : sample._s_to_dict(), 
                                                      'id' : cls.sample_id(),
                                                      'type' : class_name 
                                                    }
                                                })
            else:
                sample_data = {}
            
            post_model = SchemaClassFactory('POST body {}'.format(class_name), {'data': sample_data })
            parameters.append({
                                'name': 'POST body',
                                'in': 'body',
                                'description' : '{} attributes'.format(class_name),
                                'schema' : sample_data,
                                'required' : True
                              })
        else:
            # one of 'options', 'head', 'patch'
            log.debug('no documentation for "{}" '.format(http_method))
        
        doc['parameters'] = parameters
        doc['responses']  = responses
        doc["produces"]   = [ "application/json" ]
        
        @swagger.doc(doc)
        def wrapper( self, *args, **kwargs ):
            val = func( self, *args, **kwargs )
            return val
        
        return wrapper

    return swagger_doc_gen


def swagger_relationship_doc(cls, tags = None):

    def swagger_doc_gen( func ):
        '''
            Decorator used to document relationship methods exposed in the API
        '''

        parent_class = cls.relationship.parent.class_
        child_class  = cls.relationship.mapper.class_
        class_name   = cls.__name__ 
        table_name   = cls.__tablename__
        http_method  = func.__name__.lower()
        parameters   = [{
                        'name': parent_class.object_id,
                        'in': 'path',
                        'type': 'string',
                        'default': parent_class.sample_id(),
                        'description': '{} item'.format(parent_class.__name__),
                        'required' : True
                       },
                       {
                        'name': child_class.object_id,
                        'in': 'path',
                        'type': 'string',
                        'default': child_class.sample_id(),
                        'description': '{} item'.format(class_name),
                        'required' : True
                       }]

        parent_name = parent_class.__name__

        if tags == None :
            doc_tags = [ table_name ]
        else:
            doc_tags = tags

        doc = { 'tags': doc_tags,
                'description': 'Returns {} {} ids'.format(parent_name, cls.relationship.key),
              }

        responses = {}

        if http_method == 'get':
            doc['summary'] =  'Retrieve a {} object'.format(class_name)
            _ , responses = cls.get_swagger_doc(http_method)
            
        elif http_method == 'post':
            _, responses = cls.get_swagger_doc(http_method)
            doc['summary'] = 'Update {}'.format(cls.relationship.key)
            doc['description'] =  'Add a {} object to the {} relation on {}'.format(child_class.__name__, 
                                                                                cls.relationship.key,
                                                                                parent_name)
            # TODO: change this crap
            put_model, responses = child_class.get_swagger_doc('patch')
            rel_post_schema = schema_from_object('{} Relationship'.format(class_name), 
                                                { "data":  [ 
                                                            { 'type' : child_class.__name__  , 'id' : child_class.sample_id() } 
                                                           ] 
                                                })
            parameters.append( {
                                    'name': '{} body'.format(class_name),
                                    'in': 'body',
                                    'description' : '{} POST model'.format(class_name),
                                    'schema' : rel_post_schema,
                                    'required': True,
                                    }
                                )


        elif http_method == 'delete':
            doc['summary'] = 'Delete from {} {}'.format(parent_name, cls.relationship.key)
            doc['description'] = 'Delete a {} object from the {} relation on {}'.format(child_class.__name__, 
                                                                                cls.relationship.key,
                                                                                parent_name)
            responses = { '204' : { 
                                    'description' : 'Object Deleted' 
                                    }
                        }

        elif http_method == 'patch' or http_method == 'put':
            put_model, responses = child_class.get_swagger_doc(http_method)
            doc['summary'] =  'Update a {} object'.format(class_name)
            parameters.append({ 
                                'name': 'test',
                                'in': 'body',
                                'type': 'string',
                                'schema' : put_model
                              })
            responses = { '201' : { 
                                    'description' : 'Object Created' 
                                    }
                        }
        else:
            # one of 'options', 'head', 'patch'
            log.debug('no documentation for "{}" '.format(http_method))
        
        doc['parameters'] = parameters
        doc['responses']  = responses
        
        @swagger.doc(doc)
        def wrapper( self, *args, **kwargs ):
            val = func( self, *args, **kwargs )
            return val
        
        return wrapper

    return swagger_doc_gen