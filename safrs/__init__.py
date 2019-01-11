'''
__init__.py
'''
import logging
import os, builtins, sys
import copy
from flask_swagger_ui import get_swaggerui_blueprint
from flask import Flask, redirect, url_for
from flask.json import JSONEncoder
from flask_sqlalchemy import SQLAlchemy
from flask_restful_swagger_2 import Resource, Api as FRSApiBase

db = SQLAlchemy()

def SAFRSAPI(app, host = 'localhost', port = 5000, prefix = '', description= 'SAFRSAPI', **kwargs):
    '''
        APi factory method:
        - configure SAFRS
        - create API
    '''
    SAFRS(app, host=host, port=port, prefix=prefix)
    api = Api(app, api_spec_url='/swagger', host='{}:{}'.format(host, port), description = description)
    return api


class SAFRS(object):
    '''This class configures the Flask application to serve SAFRSBase instances

    :param app: a Flask application.
    :param prefix: URL prefix where the swagger should be hosted. Default is '/api'
    :param LOGLEVEL: loglevel configuration variable, values from logging module (0: trace, .. 50: critical)

    '''

    # Config settings
    SAFRS_UNLIMITED = 250
    ENABLE_RELATIONSHIPS = None
    LOGLEVEL = logging.WARNING
    OBJECT_ID_SUFFIX = None
    DEFAULT_INCLUDED = '' # change to +all to include eeverything (slower because relationships will be fetched)
    config = {}

    def __new__(cls, app, app_db = db, prefix = '', **kwargs):
        if not isinstance(app, Flask):
            raise TypeError("'app' should be Flask.")

        cls.app = app
        db = cls.db = app_db

        if app.config.get('DEBUG', False):
            LOGGER.setLevel(logging.DEBUG)

        app.url_map.strict_slashes = False
        app.json_encoder = SAFRSJSONEncoder

        # Register the API blueprint
        swaggerui_blueprint = kwargs.get('swaggerui_blueprint', None)
        if swaggerui_blueprint is None:
            swaggerui_blueprint = get_swaggerui_blueprint(prefix, '/swagger.json')
            app.register_blueprint(swaggerui_blueprint, url_prefix = prefix)
            swaggerui_blueprint.json_encoder = JSONEncoder
        
        @app.teardown_appcontext
        def shutdown_session(exception=None):
            '''cfr. http://flask.pocoo.org/docs/0.12/patterns/sqlalchemy/'''
            cls.db.session.remove()        

        for k, v in kwargs.items():
            setattr(cls, k, v)

        for k, v in app.config.items():
            setattr(cls, k, v)

        cls.config.update(app.config)        

        return object.__new__(object)

    @classmethod
    def init_logging(cls, loglevel = logging.WARNING):
        '''
            Specify the log format used in the webserver logs
            The webserver will catch stdout so we redirect eveything to sys.stdout
        '''
        log = logging.getLogger(__name__)
        if log.level == logging.NOTSET:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter('[%(asctime)s] %(module)s:%(lineno)d %(levelname)s: %(message)s')
            handler.setFormatter(formatter)
            log.setLevel(loglevel)
            log.addHandler(handler)
        return log

from .swagger_doc import swagger_doc, swagger_method_doc, default_paging_parameters
from .swagger_doc import parse_object_doc, swagger_relationship_doc, get_http_methods
from .errors import ValidationError
from .config import OBJECT_ID_SUFFIX, INSTANCE_URL_FMT, CLASSMETHOD_URL_FMT
from .config import RELATIONSHIP_URL_FMT, INSTANCEMETHOD_URL_FMT
from .config import ENDPOINT_FMT, INSTANCE_ENDPOINT_FMT, RESOURCE_URL_FMT
from .jsonapi import api_decorator, SAFRSRestAPI, SAFRSRestMethodAPI, SAFRSRelationshipObject, SAFRSRestRelationshipAPI

SAFRS_INSTANCE_SUFFIX = OBJECT_ID_SUFFIX + '}'

class Api(FRSApiBase):
    '''
        Subclass of the flask_restful_swagger API class where we add the expose_object method
        this method creates an API endpoint for the SAFRSBase object and corresponding swagger
        documentation
    '''
    _operation_ids = {}

    def expose_object(self, safrs_object, url_prefix='', **properties):
        '''
            This methods creates the API url endpoints for the SAFRObjects
            :param safrs_object: SAFSBase subclass that we would like to expose
        '''
        
        '''
            creates a class of the form

            @api_decorator
            class Class_API(SAFRSRestAPI):
                SAFRSObject = safrs_object

            add the class as an api resource to /SAFRSObject and /SAFRSObject/{id}

            tablename: safrs_object.__tablename__, e.g. "Users"
            classname: safrs_object.__name__, e.g. "User"

        '''

        '''
        if getattr(safrs_object,'create_test', None) and not safrs_object.query.first():
          try:
              # Used to 
              LOGGER.info('Instantiating test object for {}'.format(safrs_object))
              tmp_obj = safrs_object()
              del tmp_obj
          except:
              LOGGER.warning('Failed to create test object for {}'.format(safrs_object))
        '''
        self.safrs_object = safrs_object
        api_class_name = '{}_API'.format(safrs_object._s_type)

        # tags indicate where in the swagger hierarchy the endpoint will be shown
        tags = [safrs_object._s_type]

        url = RESOURCE_URL_FMT.format(url_prefix, safrs_object._s_type)

        endpoint = safrs_object.get_endpoint(url_prefix)

        properties['SAFRSObject'] = safrs_object
        swagger_decorator = swagger_doc(safrs_object)

        # Create the class and decorate it
        api_class = api_decorator(type(api_class_name,\
                                       (SAFRSRestAPI,),\
                                       properties),\
                                  swagger_decorator)

        # Expose the collection
        LOGGER.info('Exposing %s on %s, endpoint: %s', safrs_object._s_type, url, endpoint)
        resource = self.add_resource(api_class,
                          url,
                          endpoint=endpoint,
                          methods=['GET', 'POST'])

        url = INSTANCE_URL_FMT.format(url_prefix, safrs_object._s_type, safrs_object.__name__)
        endpoint = INSTANCE_ENDPOINT_FMT.format(url_prefix, safrs_object._s_type)
        # Expose the instances
        self.add_resource(api_class,
                          url,
                          endpoint=endpoint)
        LOGGER.info('Exposing {} instances on {}, endpoint: {}'\
                 .format(safrs_object._s_type, url, endpoint))

        object_doc = parse_object_doc(safrs_object)
        object_doc['name'] = safrs_object._s_type
        self._swagger_object['tags'].append(object_doc)

        relationships = safrs_object.__mapper__.relationships
        for relationship in relationships:
            self.expose_relationship(relationship, url, tags=tags)

        self.expose_methods(url_prefix, tags=tags)


    def expose_methods(self, url_prefix, tags):
        '''
            Expose the safrs "documented_api_method" decorated methods
        '''

        safrs_object = self.safrs_object
        api_methods = safrs_object.get_documented_api_methods()
        for api_method in api_methods:
            method_name = api_method.__name__
            api_method_class_name = 'method_{}_{}'.format(safrs_object.__tablename__, method_name)
            if getattr(api_method, '__self__', None) is safrs_object:
                # method is a classmethod, make it available at the class level
                url = CLASSMETHOD_URL_FMT.format(url_prefix,
                                                 safrs_object.__tablename__,
                                                 method_name)
            else:
                url = INSTANCEMETHOD_URL_FMT.format(url_prefix,
                                                    safrs_object.__tablename__,
                                                    safrs_object.object_id,
                                                    method_name)

            endpoint = ENDPOINT_FMT.format(url_prefix, \
                                           safrs_object.__tablename__ + '.' + method_name)
            swagger_decorator = swagger_method_doc(safrs_object, method_name, tags)
            properties = {'SAFRSObject' : safrs_object,
                          'method_name' : method_name}
            api_class = api_decorator(type(api_method_class_name,\
                                           (SAFRSRestMethodAPI,),\
                                           properties),\
                                      swagger_decorator)
            LOGGER.info('Exposing method {} on {}, endpoint: {}'.\
                     format(safrs_object.__tablename__ + '.' + api_method.__name__, url, endpoint))
            self.add_resource(api_class,\
                              url,\
                              endpoint=endpoint,\
                              methods=get_http_methods(api_method))


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
        parent_name = parent_class.__name__

        # Name of the endpoint class
        api_class_name = API_CLASSNAME_FMT.format(parent_name, rel_name)
        url = RELATIONSHIP_URL_FMT.format(url_prefix, rel_name)
        endpoint = ENDPOINT_FMT.format(url_prefix, rel_name)

        # Relationship object
        rel_object = type(rel_name, (SAFRSRelationshipObject,), {'relationship' : relationship, 
                                                                # Merge the relationship decorators from the classes
                                                                # This makes things really complicated!!!
                                                                # TODO: simplify this by creating a proper superclass
                                                                'custom_decorators' : getattr(parent_class, 'custom_decorators', []) + getattr(parent_class, 'custom_decorators', []) })

        properties['SAFRSObject'] = rel_object
        swagger_decorator = swagger_relationship_doc(rel_object, tags)

        api_class = api_decorator(type(api_class_name,\
                                       (SAFRSRestRelationshipAPI,),\
                                       properties),\
                                  swagger_decorator)

        # Expose the relationship for the parent class:
        # GET requests to this endpoint retrieve all item ids
        LOGGER.info('Exposing relationship {} on {}, endpoint: {}'.format(rel_name, url, endpoint))
        self.add_resource(api_class,\
                          url,\
                          endpoint=endpoint,\
                          methods=['GET', 'POST', 'PATCH'])

        #
        try:
            child_object_id = safrs_object.object_id
        except Exception as exc:
            LOGGER.error('No object id for {}'.format(safrs_object))
            child_object_id = safrs_object.__name__

        if safrs_object == parent_class:
            # Avoid having duplicate argument ids in the url:
            # append a 2 in case of a self-referencing relationship
            # todo : test again
            child_object_id += '2'

        # Expose the relationship for <string:ChildId>, this lets us
        # query and delete the class relationship properties for a given
        # child id
        url = (RELATIONSHIP_URL_FMT + '/<string:{}>').format(url_prefix, \
                                                             rel_name, child_object_id)
        endpoint = "{}api.{}Id".format(url_prefix, rel_name)

        LOGGER.info('Exposing {} relationship {} on {}, endpoint: {}'.format(parent_name, \
                                                                          rel_name, url, endpoint))

        self.add_resource(api_class,\
                          url,\
                          endpoint=endpoint,\
                          methods=['GET', 'DELETE'])


    def add_resource(self, resource, *urls, **kwargs):
        '''
            This method is partly copied from flask_restful_swagger_2/__init__.py

            I changed it because we don't need path id examples when
            there's no {id} in the path. We filter out the unwanted parameters

        '''
        from flask_restful_swagger_2 import validate_definitions_object, parse_method_doc
        from flask_restful_swagger_2 import validate_path_item_object
        from flask_restful_swagger_2 import extract_swagger_path, Extractor
        path_item = {}
        definitions = {}
        resource_methods = kwargs.get('methods', ['GET', 'PUT', 'POST', 'DELETE', 'PATCH'])
        safrs_object = kwargs.get('safrs_object', None)
        if safrs_object:
            del kwargs['safrs_object']
        for method in [m.lower() for m in resource.methods]:
            if not method.upper() in resource_methods:
                continue
            f = getattr(resource, method, None)
            if not f:
                continue

            operation = getattr(f, '__swagger_operation_object', None)
            if operation:
                #operation, definitions_ = self._extract_schemas(operation)
                operation, definitions_ = Extractor.extract(operation)
                path_item[method] = operation
                definitions.update(definitions_)
                summary = parse_method_doc(f, operation)

                if summary:
                    operation['summary'] = summary.split('<br/>')[0]


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
                    for parameter in method_doc.get('parameters', []):
                        object_id = '{%s}'%parameter.get('name')

                        if method == 'get' and not swagger_url.endswith(SAFRS_INSTANCE_SUFFIX):
                            # limit parameter specifies the number of items to return

                            for param in default_paging_parameters():
                                if param not in filtered_parameters:
                                    filtered_parameters.append(param)

                            param = {\
                                     'default': ','.join([rel.key for rel in self.safrs_object.__mapper__.relationships]),\
                                     'type': 'string',\
                                     'name': 'include',\
                                     'in': 'query',\
                                     'format' : 'string',\
                                     'required' : False,\
                                     'description' : 'Related relationships to include (csv)'\
                                    }
                            if param not in filtered_parameters:
                                filtered_parameters.append(param)

                            param = {'default': "",\
                                     'type': 'string',\
                                     'name': 'fields[{}]'.format(self.safrs_object._s_type),\
                                     'in': 'query',\
                                     'format' : 'int64',\
                                     'required' : False,\
                                     'description' : 'Fields to be selected (csv)'}
                            if param not in filtered_parameters:
                                filtered_parameters.append(param)

                            param = {'default': ','.join(self.safrs_object._s_jsonapi_attrs),\
                                     'type': 'string',\
                                     'name': 'sort',\
                                     'in': 'query',\
                                     'format' : 'string',\
                                     'required' : False,\
                                     'description' : 'Sort order'}
                            if param not in filtered_parameters:
                                filtered_parameters.append(param)

                            for column_name in self.safrs_object._s_column_names:
                                param = {'default': "",\
                                         'type': 'string',\
                                         'name': 'filter[{}]'.format(column_name),\
                                         'in': 'query',\
                                         'format' : 'string',\
                                         'required' : False,\
                                         'description' : '{} attribute filter (csv)'.format(column_name)}
                                if param not in filtered_parameters:
                                    filtered_parameters.append(param)

                        if not (parameter.get('in') == 'path' and not object_id in swagger_url):
                            # Only if a path param is in path url then we add the param
                            filtered_parameters.append(parameter)

                    method_doc['parameters'] = filtered_parameters
                    method_doc['operationId'] = self.get_operation_id(path_item.get(method).get('summary'))
                    path_item[method] = method_doc

                    if method == 'get' and not swagger_url.endswith(SAFRS_INSTANCE_SUFFIX):
                        # If no {id} was provided, we return a list of all the objects
                        try:
                            method_doc['description'] += ' list (See GET /{{} for details)'.\
                                                            format(SAFRS_INSTANCE_SUFFIX)
                            method_doc['responses']['200']['schema'] = ''
                        except:
                            pass

                self._swagger_object['paths'][swagger_url] = path_item

        super(FRSApiBase, self).add_resource(resource, *urls, **kwargs)

    @classmethod
    def get_operation_id(cls, summary):
        '''
        get_operation_id
        '''
        summary = ''.join(c for c in summary if c.isalnum())
        if summary not in cls._operation_ids:
            cls._operation_ids[summary] = 0
        else:
            cls._operation_ids[summary] += 1
        return '{}_{}'.format(summary, cls._operation_ids[summary])


loglevel = logging.WARNING
try:
    debug = os.getenv('DEBUG',logging.WARNING)
    loglevel=int(debug)
except:
    print('Invalid LogLevel in DEBUG Environment Variable! "{}"'.format(debug) )
    loglevel = logging.WARNING

LOGGER = SAFRS.init_logging(loglevel)

#
# Following objects will be exported by safrs
#
# We put them at the bottom to avoid cicular dependencies
#
from .db import SAFRSBase, jsonapi_rpc
from .jsonapi import SAFRSJSONEncoder, paginate
from .jsonapi import jsonapi_format_response, SAFRSFormattedResponse
from .errors import ValidationError, GenericError
from .api_methods import search, startswith


