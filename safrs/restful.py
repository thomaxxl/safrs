# -*- coding: utf-8 -*-
#
# This code implements REST HTTP methods and sqlalchemy to json marshalling
#
# Several global variables are expected to be set: app, db, cors_domain
#

import copy
import inspect
import uuid
import traceback
import datetime

from flask import Flask, make_response, url_for
from flask import Flask, Blueprint, got_request_exception, redirect, session, url_for
from flask import Flask, jsonify, request, Response, g, render_template, send_from_directory
from flask.json import JSONEncoder
from flask_restful import reqparse
from jinja2 import utils
from flask_restful.utils import cors
from flask_restful_swagger_2 import Resource, swagger
from flask_restful_swagger_2 import Api as ApiBase
from functools import wraps
# safrs_rest dependencies:
from db import SAFRSBase, ValidationError
from swagger_doc import swagger_doc, is_public, parse_object_doc, swagger_relationship_doc
from errors import ValidationError, GenericError
from flask_restful import abort


class Api(ApiBase):
    '''
        Subclass of the flask_restful_swagger API class where we add the expose_object method
        this method creates an API endpoint for the SAFRSBase object and corresponding swagger
        documentation
    '''

    def expose_object(self, safrs_object, url_prefix = '/', **properties):
        '''
            creates a class of the form 

            @api_decorator
            class Class_API(SAFRSRestAPI):
                SAFRSObject = safrs_object

            add the class as an api resource to /SAFRSObject and /SAFRSObject/{id}
        '''

        safrs_object_tablename = safrs_object.__tablename__
        api_class_name = '{}_API'.format(safrs_object_tablename)
        url = '/{}'.format(safrs_object_tablename)
        endpoint = '{}api.{}'.format(url_prefix, safrs_object_tablename)

        properties['SAFRSObject'] = safrs_object
        swagger_decorator = swagger_doc(safrs_object)

        # Create the class and decorate it 
        api_class = api_decorator(type(api_class_name, 
                                        (SAFRSRestAPI,), 
                                        properties),
                                  swagger_decorator)    
    
        log.info('Exposing class {} on {}, endpoint: {}'.format(safrs_object_tablename, url, endpoint))
        
        self.add_resource(api_class, 
                          url,
                          endpoint= endpoint, 
                          methods = ['GET','POST', 'PUT'])

        url = '{}{}/<string:{}Id>'.format(url_prefix, safrs_object_tablename,safrs_object.__name__ )
        endpoint = "{}api.{}Id".format(url_prefix, safrs_object_tablename)

        log.info('Exposing class {} on {}, endpoint: {}'.format(safrs_object_tablename, url, endpoint))

        self.add_resource( api_class, 
                           url,
                           endpoint=endpoint)

        object_doc = parse_object_doc(safrs_object)
        object_doc['name'] = safrs_object_tablename
        self._swagger_object['tags'].append(object_doc)

        relationships =  safrs_object.__mapper__.relationships
        for relationship in relationships:
            self.expose_relationship(relationship, url, tags = [ safrs_object_tablename])
            

    def expose_relationship(self, relationship, url_prefix, tags):
        '''
            Expose a relationship tp the REST API:
            A relationship consists of a parent and a child class
            creates a class of the form 

            @api_decorator
            class Parent_X_Child_API(SAFRSRestAPI):
                SAFRSObject = safrs_object

            add the class as an api resource to /SAFRSObject and /SAFRSObject/{id}
            
        '''

        properties = {}
        safrs_object = relationship.mapper.class_
        safrs_object_tablename = relationship.key
        rel_name = relationship.key

        parent_class = relationship.parent.class_ 
        parent_name  = parent_class.__name__
        
        # Name of the endpoint class
        api_class_name = '{}_X_{}_API'.format(parent_name,rel_name)
        url = '{}/{}'.format(url_prefix, rel_name)
        endpoint = '{}-api.{}'.format(url_prefix, rel_name)

        # Relationship object
        rel_object = type(rel_name, (SAFRSRelationshipObject,), {'relationship' : relationship } )

        properties['SAFRSObject'] = rel_object
        swagger_decorator = swagger_relationship_doc(rel_object, tags)
    
        api_class = api_decorator( type(api_class_name, 
                                        (SAFRSRestRelationshipAPI,), 
                                        properties),
                                        swagger_decorator)    
        
        # Expose the relationship for the parent class: 
        # GET requests to this endpoint retrieve all item ids
        log.info('Exposing relationship {} on {}, endpoint: {}'.format(rel_name, url, endpoint))
        self.add_resource(api_class, 
                          url,
                          endpoint= endpoint, 
                          methods = ['GET','PUT'])

        child_object_id = safrs_object.__name__
        if safrs_object == parent_class:
            # Avoid having duplicate argument ids in the url
            child_object_id += '2'

        # Expose the relationship for <string:ChildId>, this lets us 
        # query and delete the class relationship properties for a given 
        # child id
        url = '{}/{}/<string:{}Id>'.format(url_prefix, rel_name , child_object_id)
        endpoint = "{}-api.{}Id".format(url_prefix, rel_name)

        log.info('Exposing {} relationship {} on {}, endpoint: {}'.format(parent_name, rel_name, url, endpoint))
        
        self.add_resource( api_class, 
                           url,
                           endpoint=endpoint,
                           methods = ['GET','POST','DELETE'])


    def add_resource(self, resource, *urls, **kwargs):
        '''
            This method is partly copied from flask_restful_swagger_2/__init__.py

            I changed it because we don't need path id examples when 
            there's no {id} in the path. We filter out the unwanted parameters

        '''
        
        from flask_restful_swagger_2 import validate_definitions_object, parse_method_doc
        from flask_restful_swagger_2 import validate_path_item_object, extract_swagger_path

        path_item = {}
        definitions = {}
        resource_methods = kwargs.get('methods',['GET','PUT','POST','DELETE'])

        for method in [m.lower() for m in resource.methods]:
            if not method.upper() in resource_methods:
                continue
            f = resource.__dict__.get(method, None)
            if not f:
                continue

            operation = f.__dict__.get('__swagger_operation_object', None)
            if operation:
                operation, definitions_ = self._extract_schemas(operation)
                path_item[method] = operation
                definitions.update(definitions_)
                summary = parse_method_doc(f, operation)
                if summary:
                    operation['summary'] = summary

        validate_definitions_object(definitions)
        self._swagger_object['definitions'].update(definitions)
        
        if path_item:
            validate_path_item_object(path_item)
            for url in urls:
                if not url.startswith('/'):
                    raise ValidationError('paths must start with a /')
                swagger_url = extract_swagger_path(url)
                for method in [m.lower() for m in resource.methods]:
                    method_doc = copy.deepcopy(path_item.get(method))
                    if not method_doc:
                        continue

                    filtered_parameters = []
                    for parameter in method_doc.get('parameters',[]):
                        object_id = '{%s}'%parameter.get('name')

                        if method == 'get' and not swagger_url.endswith('Id}') :
                            param = {'default': 'all', 'type': 'string', 'name': 'details', 'in': 'query'}
                            if not param in filtered_parameters:
                                filtered_parameters.append(param)
                        
                        if method == 'post' and not swagger_url.endswith('Id}') and not parameter.get('description','').endswith('(classmethod)'):
                            # Only classmethods should be added when there's no {id} in the POST path for this method
                            continue
                        if not ( parameter.get('in') == 'path' and not object_id in swagger_url ):
                            # Only if a path param is in path url then we add the param
                            filtered_parameters.append(parameter)
 
                    #log.debug(method_doc)  
                    method_doc['parameters'] = filtered_parameters
                    path_item[method] = method_doc

                    if method == 'get' and not swagger_url.endswith('Id}'):
                        # If no {id} was provided, we return a list of all the objects
                        try:
                            method_doc['description'] += ' list (See GET /{id} for details)'
                            method_doc['responses']['200']['schema'] = ''
                        except:
                            pass

                self._swagger_object['paths'][swagger_url] = path_item


        self._swagger_object['securityDefinitions'] = {
                "api_key": {
                    "type": "apiKey",
                    "name": "api_key",
                    "in": "query"
                }}

        self._swagger_object['security'] = [ "api_key" ]
        super(ApiBase, self).add_resource(resource, *urls, **kwargs)


def http_method_decorator(fun):
    '''
        Decorator for the REST methods
        - commit the database
        - convert all exceptions to a JSON serializable GenericError
    '''

    @wraps(fun)
    def method_wrapper(*args, **kwargs):
        try:
            result = fun(*args, **kwargs)
            db.session.commit()
            return result
        except ValidationError as e:
            status_code = getattr(e, 'status_code')
            abort( status_code, error = e.message )
        except Exception as e:
            status_code = getattr(e, 'status_code', 400)
            traceback.print_exc()
            abort( status_code, error = 'Unknown Error' )

    return method_wrapper


def api_decorator(cls, swagger_decorator):
    '''
        Decorator for the API views:
            - add swagger documentation ( swagger_decorator )
            - add cors 
            - add generic exception handling

        We couldn't use inheritance because the rest method decorator 
        references the cls.SAFRSObject which isn't known 
    '''

    cors_domain = globals().get('cors_domain','No_cors_domain')
    for method_name in [ 'get' , 'put', 'post', 'delete', 'patch' ]: # HTTP methods
        method = getattr(cls, method_name, None)
        if not method: 
            continue
        # Add swagger documentation
        decorated_method = swagger_decorator(method)
        # Add cors
        decorated_method = cors.crossdomain(origin=cors_domain)(decorated_method)
        # Add exception handling
        decorated_method = http_method_decorator(decorated_method)
        setattr(cls,method_name,decorated_method)

    return cls


OBJECT_ID ='{}Id'

def object_id(obj):
    '''
        return the id of an API endpoint.
        e.g. if the SAFRSObject class is User, return "UserId" to be used in the 
        swagger url path: /User/<str:UserId>
    '''

    return OBJECT_ID.format(obj.SAFRSObject.__name__)


class SAFRSRestAPI(Resource, object):
    '''
        REST Superclass: implement HTTP Methods (get, post, put, delete, ...)
        and helpers
    '''

    SAFRSObject = None # Flask views will need to set this to the SQLAlchemy db.Model class
    default_order = None # used by sqla order_by
    object_id = None

    def __init__(self, *args, **kwargs):
        '''
            object_id is the url parameter name
        '''
        self.object_id = self.SAFRSObject.object_id()
        
    def get(self, **kwargs):
        '''
            HTTP GET: return instances
            If no id is given: return all instances
            If an id is given, get an instance by id
            If a method is given, call the method on the instance
        '''
        
        id = kwargs.get(self.object_id,None)
        #method_name = kwargs.get('method_name','')

        if not id:
            # If no id is given, check if it's passed through a request arg
            id = request.args.get('id')

        if id:
            instance = self.SAFRSObject.get_instance(id)
            if not instance:
                raise ValidationError('Invalid {}'.format(self.object_id))
            # Call the method if it doesn't exist, return instance :)
            #method = getattr(instance, method_name, lambda : instance)
            #result = { 'result' : method() }
            result = instance
        else:
            instances = self.SAFRSObject.query.all()
            details = request.args.get('details',None)
            if details == None:
                result = [ item.id for item in instances ]
                log.debug(result)
                
            else:
                result = [ item for item in instances ]
            
        return jsonify(result)    

    def put(self, **kwargs):
        '''
            Create or update the object specified by id
        '''

        id = kwargs.get(self.object_id, None)
        
        data = request.get_json()
        if data == None:
            data = {}
        if id:
            data['id'] = id

        # Create the object instance with the specified id and json data
        # If the instance (id) already exists, it will be updated with the data
        instance = self.SAFRSObject(**data)
        # object id is the endpoint parameter, for example "UserId" for a User SAFRSObject
        obj_id   = object_id(self)
        obj_args = { obj_id : instance.id }
        # Retrieve the object json and return it to the client
        obj_data = self.get(**obj_args)
        response = make_response(obj_data, 201)
        # Set the Location header to the newly created object
        response.headers['Location'] = url_for(self.endpoint, **obj_args)
        return response

    def delete(self, **kwargs):
        '''
            Delete an object by id or by filter
        '''    
        
        id = kwargs.get(self.object_id, None)
        
        filter = {}
        if id:
            filter = dict(id = id)
        else:
            json_data = request.get_json()
            if json_data:
                filter = json_data.get('filter', {} )
        if not filter:
            raise ValidationError('Invalid ID or Filter {} {}'.format(kwargs,self.object_id))
        
        for instance in self.SAFRSObject.query.filter_by(**filter).all():
            db.session.delete(instance)
            db.session.commit()

        return jsonify({}) , 204

    def post(self, **kwargs):
        '''
            HTTP POST: apply actions
            Retrieves objects from the DB based on a given query filter (in POST data)
            Returns a dictionary usable by jquery-bootgrid
        ''' 

        id = kwargs.get(self.object_id, None)
        method_name = kwargs.get('method_name','')
        
        json_data = request.get_json()
        if not method_name:
            method_name = json_data.get('method',None)
        args = json_data.get('args') if json_data else dict(request.args)
        
        if not id:
            id = request.args.get('id')
        
        if id:
            instance = self.SAFRSObject.get_instance(id)
            if not instance:
                # If no instance was found this means the user supplied 
                # an invalid ID
                raise ValidationError('Invalid ID')
        
        else:
            # No ID was supplied, apply method to the class itself
            instance = self.SAFRSObject

        if method_name:
            # call the method specified by method_name
            method_result = self.call_method_by_name(instance, method_name, args)
            result = { 'result' : method_result }
            return jsonify(result)

        # No id given, return all instances matching the filter
        try:
            filter      = json_data.get('filter',{})
            sort        = json_data.get('sort', '' )
            current     = int(json_data.get('current',0)) 
            row_count   = int(json_data.get('rowCount',50))
            search      = json_data.get('searchPhrase','')
        except:
            raise ValidationError('Invalid arguments')
        
        instances = self.get_instances(filter, sort, search)
        if current < 0 : current = 1
        
        result = {  'current'  : current,
                    'rows'     : instances[ current : current + row_count ],
                    'rowCount' : row_count,
                    'total'    : instances.count()
                 }

        return jsonify( result )

    def call_method_by_name(self, instance, method_name, args):
        '''
            Call the instance method specified by method_name
        '''

        method = getattr(instance, method_name, False)
            
        if not method:
            # Only call methods for Campaign and not for superclasses (e.g. db.Model)
            raise ValidationError('Invalid method "{}"'.format(method_name))
        if not is_public(method):
            raise ValidationError('Method is not public')

        if not args: args = {}
            
        result = method(**args)    
        return result
    
    def get_instances(self, filter, method_name, sort, search = ''):
        '''
            Get all instances. Subclasses may want to override this 
            (for example to sort results)
        '''

        if method_name:
            method(**args)

        #columns   = self.SAFRSObject.__table__.columns
        # or query to implement jq grid search functionality
        #or_query  = [ col.ilike('%{}%'.format(search)) for col in columns ]
        #instances = self.SAFRSObject.query.filter_by(**filter).filter(or_(*or_query)).order_by(self.default_order)
        
        instances = self.SAFRSObject.query.filter_by(**filter).order_by(None)
        
        return instances

class SAFRSRelationshipObject(object):

    __tablename__ = 'tabname'
    __name__ = 'name'

    @classmethod
    def get_swagger_doc(cls,func):
        return {}, {}

    @staticmethod
    def test():
        return 


class SAFRSRestRelationshipAPI(Resource, object):

    SAFRSObject = None

    def __init__(self, *args, **kwargs):
        '''
            A request to this endpoint is of the form

            /Parents/{ParentId}/children/{ChildId}

            Following attributes are set:
                - parent_class: class of the parent ( e.g. Parent , __tablename__ : Parents )
                - child_class : class of the child 
                - rel_name : name of the relationship ( e.g. children )
                - parent_object_id : url parameter name of the parent ( e.g. {ParentId} )
                - child_object_id : url parameter name of the child ( e.g. {ChildId} )

            SAFRSObject has been set with the type constructor in expose_relationship
        '''

        self.parent_class = self.SAFRSObject.relationship.parent.class_
        self.child_class = self.SAFRSObject.relationship.mapper.class_
        self.rel_name = self.SAFRSObject.relationship.key
        # The object_ids are the ids in the swagger path e.g {FileId}
        self.parent_object_id = self.parent_class.object_id()
        self.child_object_id = self.child_class.object_id()

        if self.parent_object_id == self.child_object_id:
            # see expose_relationship: if a relationship consists of 
            # two same objects, the object_id should be different (i.e. append "2")
            self.child_object_id += '2'

    def get(self, **kwargs):
        '''
            Retrieve a relationship or list of relationship member ids
        '''

        parent, child, relation = self.parse_args(**kwargs)

        if kwargs.get(self.child_object_id):
            # If {ChildId} is passed in the url, return the child object
            if child in relation:
                # item is in relationship, return the child
                result = child
            else:
                return 'Not Found', 404
        else:
            # No {ChildId} given: 
            # return a list of all relationship items
            # if request.args contains "details", return full details
            details = request.args.get('details',None)
            if details == None:
                result = [ item.id for item in relation ]
            else:
                result = [ item for item in relation ]
        return jsonify(result), 200
        

    def put(self, **kwargs):
        '''
            Update or create a relationship child item

            to be used to create or update one-to-many mappings but also works for many-to-many etc.
        '''

        parent, child, relation = self.parse_args(**kwargs)
        
        data  = request.get_json()

        if child and not child.id == kwargs.get('id'):
            raise ValidationError('ID mismatch')

        child = self.child_class(**data)

        if not child:
            raise ValidationError('Child Not found')
        
        relation = getattr(parent, self.rel_name )
        relation.append(child)
        
        # arguments for GET : {ParentId} , {ChildId}
        obj_args = { 
                     self.parent_object_id : parent.id,
                     self.child_object_id  : child.id
                    }
        
        obj_data = self.get(**obj_args)
        
        # Retrieve the object json and return it to the client
        response = make_response(obj_data, 201)
        # Set the Location header to the newly created object
        response.headers['Location'] = url_for(self.endpoint, **obj_args)
        return response

    def post(self, **kwargs):
        '''
            Create a relationship
        '''

        kwargs['require_child'] = True
        parent, child, relation = self.parse_args(**kwargs)
        relation.append(child)

        return jsonify(child), 201
        

    def delete(self, **kwargs):
        '''
            Delete a relationship
        '''

        kwargs['require_child'] = True
        parent, child, relation = self.parse_args(**kwargs)
        if child in relation:
            relation.remove(child)
        else:
            log.warning('Child not in relation')

        return jsonify({}), 204

    def parse_args(self, **kwargs):
        '''
            Parse relationship args
            An error is raised if the parent doesn't exist. 
            An error is raised if the child doesn't exist and the 
            "require_child" argument is set in kwargs, 
            
            Returns
                parent, child, relation
        '''

        parent_id = kwargs.get(self.parent_object_id,'')
        parent = self.parent_class.get_instance(parent_id)
        if not parent:
            raise ValidationError('Invalid Parent Id')
        child = None
        child_id = kwargs.get(self.child_object_id,None)
        if child_id != None:
            child = self.child_class.get_instance(child_id)
        if not child and kwargs.get('require_child', False):
            raise ValidationError('Invalid Child Id')

        relation = getattr(parent, self.rel_name )

        return parent, child, relation


class SAFRSJSONEncoder(JSONEncoder, object):
    '''
        Encodes safrsmail objects (SAFRSBase subclasses)
    '''

    def default(self,object):
        if isinstance(object, SAFRSBase):
            return object.to_dict()
        if isinstance(object, datetime.datetime):
            return object.isoformat()
        return JSONEncoder.default(self, object)


def safrs_serialize(obj):
    '''
        Marshmallow serialization doesn't always work. 
        We serialize an object to a dict the easy way.
    '''
    result = {}
    for f in obj.json_params:
        result[f] = getattr(obj,f)
    return result