from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.orm.interfaces import ONETOMANY, MANYTOONE, MANYTOMANY
from flask.json import JSONEncoder
from flask import request
from .db import SAFRSBase
from .config import get_config

import safrs
import datetime
import logging


class SAFRSFormattedResponse:
    '''
        Custom response object
    '''

    data = None
    meta = None
    errors = None
    result = None
    response = None

    def to_dict(self):

        if not self.response is None:
            return self.response

        if not self.meta is None:
            return self.meta

        if not self.result is None:
            return {'meta' : {'result' : self.result}}



class SAFRSJSONEncoder(JSONEncoder):
    '''
        Encodes safrs objects (SAFRSBase subclasses)
    '''

    def default(self, object):

        if isinstance(object, SAFRSBase):
            result = self.jsonapi_encode(object)
            return result
        if isinstance(object, datetime.datetime):
            return object.isoformat(' ')
        if isinstance(object, datetime.date):
            return object.isoformat()
        # We shouldn't get here in a normal setup
        # getting here means we already abused safrs... and we're no longer jsonapi compliant
        if isinstance(object, set):
            return list(object)
        if isinstance(object, DeclarativeMeta):
            return self.sqla_encode(object)
        if isinstance(object, SAFRSFormattedResponse):
            return object.to_dict()
        if isinstance(object, SAFRSFormattedResponse):
            return object.to_dict()
        if isinstance(object, decimal.Decimal):
            return str(object)
        if isinstance(object, bytes):
            safrs.LOGGER.warning('bytes object, TODO')

        else:
            safrs.LOGGER.warning('Unknown object type "{}" for {}'.format(type(object), object))
        return self.ghetto_encode(object)

    def ghetto_encode(self, object):
        '''
            ghetto_encode : if everything else failed, try to encode the public object attributes
            i.e. those attributes without a _ prefix
        '''
        try:
            result = {}
            for k, v in vars(object).items():
                if not k.startswith('_'):
                    if isinstance(v, (int, float, )) or v is None:
                        result[k] = v
                    else:
                        result[k] = str(v)
        except TypeError:
            result = str(object)
        return result

    def sqla_encode(self, obj):
        '''
        sqla_encode
        '''
        fields = {}
        for field in [x for x in dir(obj) if not x.startswith('_') and x != 'metadata']:
            data = obj.__getattribute__(field)
            try:
                # this will raise an exception if the data can't be serialized
                fields[field] = json.dumps(data)
            except TypeError:
                fields[field] = str(data)

        # a json-encodable dict
        return fields


    def jsonapi_encode(self, object):
        '''
            Encode object according to the jsonapi specification
        '''

        relationships = dict()
        excluded_csv = request.args.get('exclude', '')
        excluded_list = excluded_csv.split(',')
        included_csv = request.args.get('include', '')
        included_list = included_csv.split(',')

        # In order to request resources related to other resources,
        # a dot-separated path for each relationship name can be specified
        nested_included_list = []
        for inc in included_list:
            if '.' in inc:
                nested_included_list += inc.split('.')
        included_list += nested_included_list

        for relationship in object.__mapper__.relationships:
            '''
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

            meta = {}
            rel_name = relationship.key
            if rel_name in excluded_list:
                # TODO: document this
                #continue
                pass
            data = None
            if rel_name in included_list:
                if relationship.direction == MANYTOONE:
                    meta['direction'] = 'MANYTOONE'
                    rel_item = getattr(object, rel_name)
                    if rel_item:
                        data = {'id' : rel_item.jsonapi_id, 'type' : rel_item.__tablename__}

                elif relationship.direction in (ONETOMANY, MANYTOMANY):
                    if safrs.LOGGER.getEffectiveLevel() < logging.INFO:
                        if relationship.direction == ONETOMANY:
                            meta['direction'] = 'ONETOMANY'
                        else:
                            meta['direction'] = 'MANYTOMANY'
                    # Data is optional, it's also really slow for large sets!!!!!
                    rel_query = getattr(object, rel_name)
                    limit = request.args.get('page[limit]', get_config('MAX_QUERY_THRESHOLD'))
                    if not get_config('ENABLE_RELATIONSHIPS'):
                        meta['warning'] = 'ENABLE_RELATIONSHIPS set to false in config.py'
                    elif rel_query:
                        # todo: chekc if lazy=dynamic
                        # In order to work with the relationship as with Query,\
                        # you need to configure it with lazy='dynamic'
                        # "limit" may not be possible !
                        if getattr(rel_query, 'limit', False):
                            count = rel_query.count()
                            rel_query = rel_query.limit(limit)
                            if rel_query.count() >= get_config('BIG_QUERY_THRESHOLD'):
                                warning = 'Truncated result for relationship "{}",\
                                 consider paginating this request'.format(rel_name)
                                safrs.LOGGER.warning(warning)
                                meta['warning'] = warning
                            items = rel_query.all()
                        else:
                            items = list(rel_query)
                            count = len(items)
                        meta['count'] = count
                        meta['limit'] = limit
                        data = [{'id' : i.jsonapi_id,\
                                  'type' : i.__tablename__} for i in items]
                else: # shouldn't happen!!
                    raise GenericError('\
                    Unknown relationship direction for relationship {}: {}'.\
                    format(rel_name, relationship.direction))

            self_link = '{}{}/{}'.format(obj_url,\
                                         object.jsonapi_id,\
                                         rel_name)
            links = dict(self=self_link)
            rel_data = dict(links=links)

            if data:
                rel_data['data'] = data
            if meta:
                rel_data['meta'] = meta
            relationships[rel_name] = rel_data

        attributes = object._s_to_dict()
        # extract the required fieldnames from the request args, eg. Users/?Users[name] => [name]
        fields = request.args.get('fields[{}]'.format(object._s_type), None)
        if fields:
            fields = fields.split(',')
            try:
                attributes = {field: getattr(object, field) for field in fields}
            except AttributeError as exc:
                raise ValidationError('Invalid Field {}'.format(exc))

        data = dict(attributes=attributes,\
                    id=object.jsonapi_id,\
                    type=object._s_type,\
                    relationships=relationships
                    )

        return data
