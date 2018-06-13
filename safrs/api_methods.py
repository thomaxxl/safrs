from .jsonapi import SAFRSFormattedResponse, paginate, jsonapi_format_response
from .swagger_doc import documented_api_method, jsonapi_rpc
from .errors import GenericError, NotFoundError
from .safrs_types import SAFRSID
from sqlalchemy import or_

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

@documented_api_method
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

@documented_api_method
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
@jsonapi_rpc(http_methods = ['POST'])
def re_search(cls, **kwargs):
    '''
        pageable: True
        description : lookup column names
        args:
            query: search.*all
    '''
    query = kwargs.get('query','')
    response = SAFRSFormattedResponse()
    result = cls.query.filter(or_(column.op('regexp')(query) for column in cls._s_columns))
    
    instances = result
    links, instances, count = paginate(instances)
    data = [ item for item in instances ]
    meta = {}
    errors = None
    response.response = jsonapi_format_response(data, meta, links, errors, count)

    return response


@classmethod
@jsonapi_rpc(http_methods = ['POST'])
def search(cls, **kwargs):
    '''
        pageable: True
        description : lookup column names
        args:
            query: keyword
    '''
    query = kwargs.get('query','')
    response = SAFRSFormattedResponse()
    result = cls.query.filter(or_(column.like('%' + query + '%') for column in cls._s_columns))
    
    instances = result
    links, instances, count = paginate(instances)
    data = [ item for item in instances ]
    meta = {}
    errors = None
    response.response = jsonapi_format_response(data, meta, links, errors, count)

    return response
