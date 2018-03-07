# -*- coding: utf-8 -*-
#
# This code implements REST HTTP methods and sqlalchemy to json marshalling
#
# Configuration parameters:
# - endpoint
#
# todo: 
# - __ underscores
# - tests
# - validation
# - hardcoded strings > config (SAFRS_INSTANCE_SUFFIX, URL_FMT)
# - expose canonical endpoints
# - jsonapi : pagination, include
# - move all swagger related stuffto swagger_doc
# - pagination, fieldsets, filtering, inclusion => filter page fields sort include
# - duplicate entries / pk's => error
# - orm reconstructor
# - safrs subclassing
# - marshmallow & encoding
#
'''
http://jsonapi.org/format/#content-negotiation-servers

Server Responsibilities
Servers MUST send all JSON API data in response documents with the header Content-Type: application/vnd.api+json without any media type parameters.
Servers MUST respond with a 415 Unsupported Media Type status code if a request specifies the header Content-Type: application/vnd.api+json with any media type parameters.

This shoudl be implemented by the app, for example using @app.before_request  and @app.after_request

'''
import copy
import inspect
import uuid
import traceback
import datetime
import logging
import sqlalchemy

from flask import Flask, make_response, url_for
from flask import Blueprint, got_request_exception, redirect, session
from flask import jsonify, request, Response, g, render_template, send_from_directory
from flask.json import JSONEncoder
from flask_restful import reqparse
from flask_restful.utils import cors
from flask_restful_swagger_2 import Resource, swagger, Api as FRSApiBase
from flask_restful import abort
from flask_sqlalchemy import SQLAlchemy
from jinja2 import utils
from functools import wraps
from jsonschema import validate
from sqlalchemy.orm.interfaces import ONETOMANY, MANYTOONE, MANYTOMANY 

# safrs_rest dependencies:
from .db import SAFRSBase, db, log
from .swagger_doc import swagger_doc, swagger_method_doc, is_public, parse_object_doc, swagger_relationship_doc
from .errors import ValidationError, GenericError, NotFoundError
from .config import OBJECT_ID_SUFFIX, INSTANCE_URL_FMT, CLASSMETHOD_URL_FMT, RELATIONSHIP_URL_FMT, INSTANCEMETHOD_URL_FMT, UNLIMITED
from .config import ENDPOINT_FMT, INSTANCE_ENDPOINT_FMT, RESOURCE_URL_FMT

SAFRS_INSTANCE_SUFFIX = OBJECT_ID_SUFFIX + '}'



class Api(FRSApiBase):
    '''
        Subclass of the flask_restful_swagger API class where we add the expose_object method
        this method creates an API endpoint for the SAFRSBase object and corresponding swagger
        documentation
    '''

    def expose_object(self, safrs_object, url_prefix = '', **properties):
        '''
            This methods creates the API url endpoints for the SAFRObjects

            creates a class of the form 

            @api_decorator
            class Class_API(SAFRSRestAPI):
                SAFRSObject = safrs_object

            add the class as an api resource to /SAFRSObject and /SAFRSObject/{id}

            tablename: safrs_object.__tablename__, e.g. "Users"
            classname: safrs_object.__name__, e.g. "User"

        '''

        api_class_name = '{}_API'.format(safrs_object._s_type)

        # tags indicate where in the swagger hierarchy the endpoint will be shown
        tags = [ safrs_object._s_type ]
        
        url = RESOURCE_URL_FMT.format(url_prefix,safrs_object._s_type)

        endpoint = safrs_object.get_endpoint(url_prefix)

        properties['SAFRSObject'] = safrs_object
        swagger_decorator = swagger_doc(safrs_object)

        # Create the class and decorate it 
        api_class = api_decorator(type(api_class_name, 
                                        (SAFRSRestAPI,), 
                                        properties),
                                  swagger_decorator)    
        
        # Expose the collection
        log.info('Exposing {} on {}, endpoint: {}'.format(safrs_object._s_type, url, endpoint))
        self.add_resource(api_class, 
                          url,
                          endpoint= endpoint, 
                          methods = ['GET','POST', 'PUT'])

        url = INSTANCE_URL_FMT.format(url_prefix, safrs_object._s_type,safrs_object.__name__ )
        endpoint = INSTANCE_ENDPOINT_FMT.format(url_prefix, safrs_object._s_type)
        # Expose the instances
        self.add_resource( api_class, 
                           url,
                           endpoint=endpoint)
        log.info('Exposing {} instances on {}, endpoint: {}'.format(safrs_object._s_type, url, endpoint))
        
        object_doc = parse_object_doc(safrs_object)
        object_doc['name'] = safrs_object._s_type
        self._swagger_object['tags'].append(object_doc)

        relationships =  safrs_object.__mapper__.relationships
        for relationship in relationships:
            self.expose_relationship(relationship, url, tags = tags)

        self.expose_methods(safrs_object, url_prefix, tags = tags)


    def expose_methods(self, safrs_object, url_prefix, tags):
        '''
            Expose the safrs "documented_api_method" decorated methods
        '''

        api_methods = safrs_object.get_documented_api_methods()
        for api_method in api_methods:
            method_name = api_method.__name__
            api_method_class_name = 'method_{}_{}'.format(safrs_object.__tablename__, method_name)
            if getattr(api_method,'__self__',None) is safrs_object:
                # method is a classmethod, make it available at the class level
                url = CLASSMETHOD_URL_FMT.format( url_prefix, 
                                                  safrs_object.__tablename__, 
                                                  method_name)
            else:
                url = INSTANCEMETHOD_URL_FMT.format(url_prefix, 
                                                    safrs_object.__tablename__, 
                                                    safrs_object.object_id, 
                                                    method_name)
                
            endpoint = ENDPOINT_FMT.format(url_prefix, safrs_object.__tablename__ + '.' + method_name)
            swagger_decorator = swagger_method_doc(safrs_object, method_name, tags)
            properties = { 
                            'SAFRSObject' : safrs_object, 
                            'method_name' : method_name 
                        }
            api_class = api_decorator( type(api_method_class_name, 
                                        (SAFRSRestMethodAPI,), 
                                        properties),
                                        swagger_decorator)
            log.info('Exposing method {} on {}, endpoint: {}'.format(safrs_object.__tablename__ + '.' + api_method.__name__, url, endpoint))
            self.add_resource(api_class, 
                          url,
                          endpoint= endpoint, 
                          methods = ['POST'])

            
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

        API_CLASSNAME_FMT = '{}_X_{}_API'

        properties = {}
        safrs_object = relationship.mapper.class_
        safrs_object_tablename = relationship.key
        rel_name = relationship.key

        parent_class = relationship.parent.class_ 
        parent_name  = parent_class.__name__
        
        # Name of the endpoint class
        api_class_name = API_CLASSNAME_FMT.format(parent_name,rel_name)
        url = RELATIONSHIP_URL_FMT.format(url_prefix, rel_name)
        endpoint = ENDPOINT_FMT.format(url_prefix, rel_name)

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
                          methods = ['GET','POST'])

        #child_object_id = safrs_object.__name__
        child_object_id = safrs_object.object_id

        if safrs_object == parent_class:
            # Avoid having duplicate argument ids in the url: append a 2 in case of a self-referencing relationship
            # todo : test again
            child_object_id += '2'

        # Expose the relationship for <string:ChildId>, this lets us 
        # query and delete the class relationship properties for a given 
        # child id
        url = (RELATIONSHIP_URL_FMT + '/<string:{}>').format(url_prefix, rel_name , child_object_id)
        endpoint = "{}-api.{}Id".format(url_prefix, rel_name)

        log.info('Exposing {} relationship {} on {}, endpoint: {}'.format(parent_name, rel_name, url, endpoint))
        
        self.add_resource( api_class, 
                           url,
                           endpoint=endpoint,
                           methods = ['GET','DELETE'])


    def add_resource(self, resource, *urls, **kwargs):
        '''
            This method is partly copied from flask_restful_swagger_2/__init__.py

            I changed it because we don't need path id examples when 
            there's no {id} in the path. We filter out the unwanted parameters

        '''
        
        from flask_restful_swagger_2 import validate_definitions_object, parse_method_doc
        from flask_restful_swagger_2 import validate_path_item_object, extract_swagger_path, Extractor

        path_item = {}
        definitions = {}
        resource_methods = kwargs.get('methods',['GET','PUT','POST','DELETE', 'PATCH'])

        for method in [m.lower() for m in resource.methods]:
            if not method.upper() in resource_methods:
                continue
            f = getattr(resource, method, None)
            if not f:
                continue

            operation = getattr(f,'__swagger_operation_object', None)
            if operation:
                #operation, definitions_ = self._extract_schemas(operation)
                operation, definitions_ = Extractor.extract(operation)
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

                        if method == 'get' and not swagger_url.endswith(SAFRS_INSTANCE_SUFFIX) :
                            # limit parameter specifies the number of items to return
                            param = { 'default': 0,  # The 0 isn't rendered though
                                      'type': 'integer', 
                                      'name': 'page[offset]', 
                                      'in': 'query', 
                                      'format' : 'int64',
                                      'required' : False,
                                      'description' : 'Page offset'
                                    }
                            if not param in filtered_parameters:
                                filtered_parameters.append(param)
                            
                            param = { 'default': 10, 
                                      'type': 'integer', 
                                      'name': 'page[limit]', 
                                      'in': 'query', 
                                      'format' : 'int64',
                                      'required' : False,
                                      'description' : 'max number of items'
                                    }
                            if not param in filtered_parameters:
                                filtered_parameters.append(param)
                            
                            param = { 'default': '', 
                                      'type': 'string', 
                                      'name': 'include', 
                                      'in': 'query', 
                                      'format' : 'int64',
                                      'required' : False,
                                      'description' : 'related objects to include'
                                    }
                            if not param in filtered_parameters:
                                filtered_parameters.append(param)
                        
                            param = { 'default': "", 
                                      'type': 'string', 
                                      'name': 'fields[{}]'.format(parameter.get('name')), 
                                      'in': 'query', 
                                      'format' : 'int64',
                                      'required' : False,
                                      'description' : 'fields'
                                    }
                            if not param in filtered_parameters:
                                filtered_parameters.append(param)
                        
                        if not ( parameter.get('in') == 'path' and not object_id in swagger_url ):
                            # Only if a path param is in path url then we add the param
                            filtered_parameters.append(parameter)
 
                    #log.debug(method_doc)  
                    method_doc['parameters'] = filtered_parameters
                    path_item[method] = method_doc

                    if method == 'get' and not swagger_url.endswith(SAFRS_INSTANCE_SUFFIX):
                        # If no {id} was provided, we return a list of all the objects
                        try:
                            method_doc['description'] += ' list (See GET /{{} for details)'.format(SAFRS_INSTANCE_SUFFIX)
                            method_doc['responses']['200']['schema'] = ''
                        except:
                            pass

                self._swagger_object['paths'][swagger_url] = path_item


        '''self._swagger_object['securityDefinitions'] = {
                "api_key": {
                    "type": "apiKey",
                    "name": "api_key",
                    "in": "query"
                }}

        self._swagger_object['security'] = [ "api_key" ]'''
        super(FRSApiBase, self).add_resource(resource, *urls, **kwargs)


def http_method_decorator(fun):
    '''
        Decorator for the REST methods
        - commit the database
        - convert all exceptions to a JSON serializable GenericError

        This method will be called for all requests
    '''

    @wraps(fun)
    def method_wrapper(*args, **kwargs):
        try:
            result = fun(*args, **kwargs)
            db.session.commit()
            return result

        except ( ValidationError, GenericError, NotFoundError ) as exc:
            traceback.print_exc()
            status_code = getattr(exc, 'status_code')
            message = exc.message

        except Exception as exc:
            status_code = getattr(exc, 'status_code', 500)
            traceback.print_exc()
            if logging.getLogger().getEffectiveLevel() > logging.DEBUG:
                message = 'Unknown Error'
            else:
                message = str(exc)
            
        db.session.rollback()
        errors = dict(detail = message)
        abort(status_code , errors = [errors])
        
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

    cors_domain = globals().get('cors_domain',None)
    for method_name in [ 'get' , 'post', 'delete', 'patch', 'put' ]: # HTTP methods 
        method = getattr(cls, method_name, None)
        if not method: 
            continue
        # Add swagger documentation
        decorated_method = swagger_decorator(method)
        # Add cors
        if cors_domain != None:
            decorated_method = cors.crossdomain(origin=cors_domain)(decorated_method)
        # Add exception handling
        decorated_method = http_method_decorator(decorated_method)
        setattr(cls,method_name,decorated_method)

    return cls


def paginate(object):
    '''
        http://jsonapi.org/format/#fetching-pagination
    
        A server MAY choose to limit the number of resources returned in a response to a subset (“page”) of the whole set available.
        A server MAY provide links to traverse a paginated data set (“pagination links”).
        Pagination links MUST appear in the links object that corresponds to a collection. To paginate the primary data, supply pagination links in the top-level links object. To paginate an included collection returned in a compound document, supply pagination links in the corresponding links object.

        The following keys MUST be used for pagination links:

        first: the first page of data
        last: the last page of data
        prev: the previous page of data
        next: the next page of data

        We use page[offset] and page[limit]

    '''
    offset = request.args.get('page[offset]',0)
    limit  = request.args.get('page[limit]', UNLIMITED)
    links  = {
        'first' : 0,
        'last'  : 0,
        'prev'  : 0,
        'next'  : 0,
    }
    instances = object.query.offset(offset).limit(limit).all()
    return links, instances
            
def get_included(data, page):
    '''
        http://jsonapi.org/format/#fetching-includes

        Inclusion of Related Resources
        An endpoint MAY return resources related to the primary data by default.
        An endpoint MAY also support an include request parameter to allow the client to customize which related resources should be returned.
    '''

    result  = []
    include = request.args.get('include', None)
    if not include:
        return result
    
    if isinstance(data, list):
        return [ get_included(obj) for obj in data ]
    
    # When we get here, data has to be a SAFRSBase instance
    assert(isinstance(data, SAFRSBase))
    instance = data

    # Multiple related resources can be requested in a comma-separated list
    includes = include.split(',')

    for include in includes:
        if '.' in include:
            endpoint, relationship = include.split('.')
        else:
            relationship = include
        
        if relationship in [ r.key for r in instance._s_relationships]:
            links, included = paginate(getattr(instance,relationship))
            result  += included

    return result



class SAFRSRestAPI(Resource, object):
    '''
        Flask webservice wrapper for the underlying Resource Object: an sqla db model (SAFRSBase subclass : cls.SAFRSObject)

        This class implements HTTP Methods (get, post, put, delete, ...) and helpers     

        http://jsonapi.org/format/#document-resource-objects
        A resource object MUST contain at least the following top-level members:
        - id
        - type

        In addition, a resource object MAY contain any of these top-level members:

        attributes: an attributes object representing some of the resource’s data.
        relationships: a relationships object describing relationships between the resource and other JSON API resources.
        links: a links object containing links related to the resource.
        meta: a meta object containing non-standard meta-information about a resource that can not be represented as an attribute or relationship.

        e.g.
        {
            "id": "1f1c0e90-9e93-4242-9b8c-56ac24e505e4",
            "type": "car",
            "attributes": {
                "color": "red"
            },
            "relationships": {
                "driver": {
                    "data": {
                        "id": "55550e90-9e93-4242-9b8c-56ac24e505e5", 
                        "type": "person"
                    }
                }
        }

        A resource object’s attributes and its relationships are collectively called its “fields”.
    '''

    SAFRSObject = None # Flask views will need to set this to the SQLAlchemy db.Model class
    default_order = None # used by sqla order_by
    object_id = None

    def __init__(self, *args, **kwargs):
        '''
            object_id is the function used to create the url parameter name (eg "User" -> "UserId" )
            this parameter is used in the swagger endpoint spec, eg. /Users/{UserId} where the UserId parameter
            is the id of the underlying SAFRSObject. 
        '''
        self.object_id = self.SAFRSObject.object_id
        
    def get(self, **kwargs):
        '''
            HTTP GET: return instances
            If no id is given: return all instances
            If an id is given, get an instance by id
            If a method is given, call the method on the instance

            http://jsonapi.org/format/#document-top-level

            A JSON object MUST be at the root of every JSON API request and response containing data. This object defines a document’s “top level”.

            A document MUST contain at least one of the following top-level members:
            - data: the document’s “primary data”
            - errors: an array of error objects
            - meta: a meta object that contains non-standard meta-information.

            A document MAY contain any of these top-level members:
            - jsonapi: an object describing the server’s implementation
            - links: a links object related to the primary data.
            - included: an array of resource objects that are related to the primary data and/or each other (“included resources”).
        '''

        data    = None
        meta    = {}
        errors  = None

        links   = None
        included= None
        jsonapi = dict( version = '1.0' )
        
        id = kwargs.get(self.object_id,None)
        #method_name = kwargs.get('method_name','')

        limit = request.args.get('limit', UNLIMITED)
        meta['limit'] = limit

        if id:
            # Retrieve the instance with the provided id
            instance = self.SAFRSObject.get_instance(id)
            if not instance:
                raise ValidationError('Invalid {}'.format(self.object_id))

            for rel in instance.__mapper__.relationships:
                log.info(rel)
                log.info(rel.key)

            data  = instance
            links = { 
                       'self' : url_for(instance.get_endpoint())
                    }
            meta.update(dict(instance_meta =  instance._s_meta()))
            
        else:
            # retrieve a collection
            links, instances = paginate(self.SAFRSObject)
            data = [ item for item in instances ]
            
        
        included = get_included(data, limit)
        result   = dict(data = data)
        
        if errors:
            result['errors'] = errors
        if meta:
            result['meta'] = meta
        if jsonapi:
            result['jsonapi'] = jsonapi
        if links:
            result['links'] = links
        if included:
            result['included'] = included
        
        return jsonify(result)    

    def patch(self, **kwargs):
        '''
            Create or update the object specified by id
        '''

        id = kwargs.get(self.object_id, None)
        if not id:
            raise ValidationError('Invalid ID')
        
        json  = request.get_json()
        if type(json) != dict:
            raise ValidationError('Invalid Object Type')
        
        data = json.get('data')

        if not data or type(data) != dict or data.get('id', None) != id:
            raise ValidationError('Invalid Data Object')

        attributes = data.get('attributes',{})
        attributes['id'] = id

        # Create the object instance with the specified id and json data
        # If the instance (id) already exists, it will be updated with the data
        instance = self.SAFRSObject.get_instance(id)
        if not instance:
            raise ValidationError('Invalid ID')
        instance._s_patch(**attributes)
        
        # object id is the endpoint parameter, for example "UserId" for a User SAFRSObject
        obj_args = { instance.object_id : instance.id }
        # Retrieve the object json and return it to the client
        obj_data = self.get(**obj_args)
        response = make_response(obj_data, 201)
        # Set the Location header to the newly created object
        response.headers['Location'] = url_for(self.endpoint, **obj_args)
        return response

    def get_json(self):
        '''
            Extract and validate json request payload
        '''

        json  = request.get_json()
        if type(json) != dict:
            raise ValidationError('Invalid Object Type')

        # TODO: Validate jsonapi

        return json
        

    def post(self, **kwargs):
        '''
            http://jsonapi.org/format/#crud-creating
            Creating Resources
            A resource can be created by sending a POST request to a URL that represents a collection of resources. 
            The request MUST include a single resource object as primary data. 
            The resource object MUST contain at least a type member.

            If a relationship is provided in the relationships member of the resource object, 
            its value MUST be a relationship object with a data member. 
            The value of this key represents the linkage the new resource is to have.

            Response:
            403: This implementation does not accept client-generated IDs
            201: Created
            202: Accepted (processing has not been completed by the time the server responds)
            404: Not Found
            409: Conflict
    
            Location Header identifying the location of the newly created resource
            Body : created object
        '''

        payload = self.get_json()
        method_name = payload.get('meta',{}).get('method', None)

        id = kwargs.get(self.object_id, None)
        if id != None:
            # Treat this request like a patch
            response = self.patch(**kwargs)

        else:
            # Create a new instance of the SAFRSObject
            data = payload.get('data')
            if data == None:
                raise ValidationError('Request contains no data')
            if type(data) != dict:
                raise ValidationError('data is not a dict object')
            
            obj_type = data.get('type', None)
            if not obj_type: # or type.. 
                raise ValidationError('Invalid type member')

            attributes = data.get('attributes',{})
            # Create the object instance with the specified id and json data
            # If the instance (id) already exists, it will be updated with the data
            instance = self.SAFRSObject(**attributes)
             # object_id is the endpoint parameter, for example "UserId" for a User SAFRSObject
            obj_args = { instance.object_id : instance.id }
            # Retrieve the object json and return it to the client
            obj_data = self.get(**obj_args)
            response = make_response(obj_data, 201)
            # Set the Location header to the newly created object
            response.headers['Location'] = url_for(self.endpoint, **obj_args)

        return response


    def delete(self, **kwargs):
        '''
            Delete an object by id or by filter

            http://jsonapi.org/format/1.1/#crud-deleting:
            Responses
                202 Accepted
                If a deletion request has been accepted for processing, but the processing has not been completed by the
                time the server responds, the server MUST return a 202 Accepted status code.

                204 No Content
                A server MUST return a 204 No Content status code if a deletion request is successful and no content is 
                returned.

                200 OK
                A server MUST return a 200 OK status code if a deletion request is successful and the server responds 
                with only top-level meta data.

                404 NOT FOUND
                A server SHOULD return a 404 Not Found status code if a deletion request fails due to the resource not 
                existing.
        '''    
        
        id = kwargs.get(self.object_id, None)
        
        if id:
            instance = self.SAFRSObject.get_instance(id)
            db.session.delete(instance)
        else:
            raise NotFoundError(id, status_code=404)
            
        return make_response(jsonify({}), 204)

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


class SAFRSRestMethodAPI(Resource, object):
    '''
        Flask webservice wrapper for the underlying SAFRSBase documented_api_method

        Only HTTP POST is supported        
    '''

    SAFRSObject = None # Flask views will need to set this to the SQLAlchemy db.Model class
    method_name = None

    def __init__(self, *args, **kwargs):
        '''
            object_id is the function used to create the url parameter name (eg "User" -> "UserId" )
            this parameter is used in the swagger endpoint spec, eg. /Users/{UserId} where the UserId parameter
            is the id of the underlying SAFRSObject. 
        '''
        self.object_id = self.SAFRSObject.object_id

    def post(self, **kwargs):
        '''
            HTTP POST: apply actions, return 200 regardless
        ''' 

        id = kwargs.get(self.object_id, None)
        
        if id != None:
            instance = self.SAFRSObject.get_instance(id)
            if not instance:
                # If no instance was found this means the user supplied 
                # an invalid ID
                raise ValidationError('Invalid ID')
        
        else:
            # No ID was supplied, apply method to the class itself
            instance = self.SAFRSObject

        method = getattr(instance, self.method_name, None)

        if not method:
            # Only call methods for Campaign and not for superclasses (e.g. db.Model)
            raise ValidationError('Invalid method "{}"'.format(method_name))
        if not is_public(method):
            raise ValidationError('Method is not public')

        args = dict(request.args)
        json_data = request.get_json({})
        if json_data:
            args = json_data.get('meta',{}).get('args',{})

        log.debug('method {} args {}'.format(self.method_name, args))
        
        result = method(**args)

        response = { 'meta' :
                     { 'result' : result }
                   }

        return jsonify( response ) # 200 : default


class SAFRSRelationshipObject(object):

    __tablename__ = 'tabname'
    __name__ = 'name'

    @classmethod
    def get_swagger_doc(cls, http_method):
        '''
            Create a swagger api model based on the sqlalchemy schema 
            if an instance exists in the DB, the first entry is used as example
        '''

        body = {}
        responses = {}
        object_name = cls.__name__

        object_model = {}
        responses = { '200': {  
                                'description' : '{} object'.format(object_name),
                                'schema': object_model
                             }
                    }

        if http_method == 'post':
            responses = { '200' : {
                                    'description' : 'Success',
                                  }
                        }

        if http_method == 'get':
            responses = { '200' : {
                                    'description' : 'Success',
                                  }
                        }
            #responses['200']['schema'] = {'$ref': '#/definitions/{}'.format(object_model.__name__)}

        return body, responses


class SAFRSRestRelationshipAPI(Resource, object):
    '''
        Flask webservice wrapper for the underlying sqla db model (SAFRSBase subclass : cls.SAFRSObject)

        The endpoint url is of the form "/Parents/{ParentId}/children/{ChildId}" (cfr RELATIONSHIP_URL_FMT in API.expose_relationship)
        where "children" is the relationship attribute of the parent

        Following attributes are set on this class:
            - SAFRSObject: the sqla object which has been set with the type constructor in expose_relationship
            - parent_class: class of the parent ( e.g. Parent , __tablename__ : Parents )
            - child_class : class of the child 
            - rel_name : name of the relationship ( e.g. children )
            - parent_object_id : url parameter name of the parent ( e.g. {ParentId} )
            - child_object_id : url parameter name of the child ( e.g. {ChildId} )

        
        http://jsonapi.org/format/#crud-updating-relationships

        Updating To-Many Relationships
        A server MUST respond to PATCH, POST, and DELETE requests to a URL from a to-many relationship link as described below.

        For all request types, the body MUST contain a data member whose value is an empty array or an array of resource identifier objects.

        If a client makes a PATCH request to a URL from a to-many relationship link, the server MUST either completely replace every member of the relationship, 
        return an appropriate error response if some resources can not be found or accessed, or return a 403 Forbidden response if complete replacement is not allowed by the server.
    '''

    SAFRSObject = None

    def __init__(self, *args, **kwargs):
        
        self.parent_class = self.SAFRSObject.relationship.parent.class_
        self.child_class = self.SAFRSObject.relationship.mapper.class_
        self.rel_name = self.SAFRSObject.relationship.key
        # The object_ids are the ids in the swagger path e.g {FileId}
        self.parent_object_id = self.parent_class.object_id
        self.child_object_id = self.child_class.object_id

        if self.parent_object_id == self.child_object_id:
            # see expose_relationship: if a relationship consists of 
            # two same objects, the object_id should be different (i.e. append "2")
            self.child_object_id += '2'

    def get(self, **kwargs):
        '''
            Retrieve a relationship or list of relationship member ids
        '''

        parent, relation = self.parse_args(**kwargs)

        child_id = kwargs.get(self.child_object_id)
        if child_id:
            child = self.child_class.get_instance(child_id)
            # If {ChildId} is passed in the url, return the child object
            if child in relation:
                # item is in relationship, return the child
                result = [ child ]
            else:
                return 'Not Found', 404
        elif type(relation) == self.child_class: # MANYTOONE
            result = [ relation ]
        else:
            # No {ChildId} given: 
            # return a list of all relationship items
            result = [ item for item in relation ]

        return jsonify(result)
        

    def patch(self, **kwargs):
        '''
            Update or create a relationship child item

            to be used to create or update one-to-many mappings but also works for many-to-many etc.
        '''
        parent, relation = self.parse_args(**kwargs)
        
        json  = request.get_json()
        if type(json) != dict:
            raise ValidationError('Invalid Object Type')
        data = json.get('data')
        relation = getattr(parent, self.rel_name )

        obj_args = { self.parent_object_id : parent.id }
        
        if type(data) == dict:
            child = self.child_class.get_instance(data.get('id', None))   
            if not child in relation:
                relation.append(child)
            obj_args[self.child_object_id] = child.id
        elif type(data) == list:
            if list == []: # => remove all items
                for item in relation:
                    relation.remove(item)
            else:
                for child in data:
                    child = self.child_class.get_instance(data.get('id', None))   
                    relation.append(child)
        else:
            raise ValidationError('Invalid Data Object Type')
        
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

        log.info(kwargs)
        errors = []
        kwargs['require_child'] = True
        parent, relation = self.parse_args(**kwargs)
        
        json  = request.get_json()
        if type(json) != dict:
            raise ValidationError('Invalid Object Type')
        data = json.get('data')
        for item in data:
            if type(item) != dict:
                raise ValidationError('Invalid data type')
            child_id = item.get('id', None)
            if child_id == None:
                errors.append('no child id {}'.format(data))
                log.error(errors)
                continue
            child = self.child_class.get_instance(child_id)
            if not child:
                errors.append('invalid child id {}'.format(child_id))
                log.error(errors)
                continue
            if not child in relation:
                relation.append(child)

        return jsonify(child), 201
        

    def delete(self, **kwargs):
        '''
            Delete a relationship
        '''

        kwargs['require_child'] = True
        parent, relation = self.parse_args(**kwargs)
        child_id =  kwargs.get(self.child_object_id,None)
        child = self.child_class.get_instance(child_id)
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

        relation = getattr(parent, self.rel_name)

        return parent, relation


class SAFRSJSONEncoder(JSONEncoder, object):
    '''
        Encodes safrsmail objects (SAFRSBase subclasses)
    '''

    def default(self,object):
        if isinstance(object, SAFRSBase):
            rel_limit_count = 100
            limit  = request.args.get('limit', rel_limit_count)
            result = self.jsonapi_encode(object)
            return result
        if isinstance(object, datetime.datetime) or isinstance(object, datetime.date):
            return object.isoformat()

        return result


    def jsonapi_encode(self, object):
        '''
            Encode object according to the jsonapi specification
        '''
    
        relationships = dict()
        for relationship in object.__mapper__.relationships:
            '''
                http://jsonapi.org/format/#document-resource-object-relationships:

                The value of the relationships key MUST be an object (a “relationships object”). 
                Members of the relationships object (“relationships”) represent references from the resource object in which it’s defined to other resource objects.

                Relationships may be to-one or to-many.

                A “relationship object” MUST contain at least one of the following:

                - links: a links object containing at least one of the following:
                    - self: a link for the relationship itself (a “relationship link”). This link allows the client to directly manipulate the relationship.       
                    - related: a related resource link
                - data: resource linkage
                - meta: a meta object that contains non-standard meta-information about the relationship.
                A relationship object that represents a to-many relationship MAY also contain pagination links under the links member, as described below.

                SAFRS currently implements links with self
            '''
            
            try:
                #params = { self.object_id : self.id }
                #obj_url = url_for(self.get_endpoint(), **params) # Doesn't work :(, todo : why?
                obj_url = url_for(object.get_endpoint())
                if not obj_url.endswith('/'):
                    obj_url += '/'
            except:
                # app not initialized
                obj_url = ''
            
            rel_name = relationship.key
            if relationship.direction in (ONETOMANY, MANYTOMANY):
                # Data is optional, it's also really slow for large sets: 
                rel_query = getattr(object, rel_name)
                #limit = object.query_limit
                #if rel_query.lazy:
                #items = list(getattr(object, rel_name, []))
                #data  = [{ 'id' : i.id , 'type' : i.__tablename__ } for i in items]
                #else:
                data =[{}]
            else:
                data = None
            
            self_link = '{}{}/{}'.format( obj_url,
                                          object.id,
                                          rel_name)
            links  = dict( self = self_link, 
                           related = '' )
            
            relationships[rel_name] = dict( links = links, 
                                            data = data, 
                                            meta = {} )

        attributes  = object._s_to_dict()
        # extract the required fieldnames from the request args, eg. Users/?Users[name] => [name]
        fields = request.args.get('fields[{}]'.format(object._s_type), None)
        if fields:
            fields = fields.split(',')
            try:
                attributes = { field: getattr(object, field) for field in fields }
            except AttributeError as e:
                raise ValidationError ('Invalid Field {}'.format(e))

        data = dict( attributes = attributes,
                     id = object.id,
                     type = object._s_type,
                     relationships = relationships
                    )
        
        return data
