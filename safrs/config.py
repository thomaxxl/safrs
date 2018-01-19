# The suffix of the url path parameter shown in the swagger UI, eg Id => /Users/{UserId}
OBJECT_ID_SUFFIX = 'Id'

#
# The following URL fromatters determine the urls of the API resource objects
#
# first argument will be is the url prefix (eg. /api/v1/ )
# second argument will be object tablename (ie resource, eg. Users)
# Third parameter will be the "Object id" (eg. UserId)
# => /api/v1/Users/{UserId}
RESOURCE_URL_FMT = '{}/{}/'
INSTANCE_URL_FMT = RESOURCE_URL_FMT + '<string:{}' + OBJECT_ID_SUFFIX + '>/'
# last parameter for the "method" urls below will be the method name
INSTANCEMETHOD_URL_FMT = RESOURCE_URL_FMT + '<string:{}>/{}'
# (eg. /Users/get_list)
CLASSMETHOD_URL_FMT = RESOURCE_URL_FMT + '{}'

# Parent-> Child relationship, (eg. /Users/{UserId}/books)
RELATIONSHIP_URL_FMT = '{}{}'

''' 
# Alternative configuration with more explicit urls:
INSTANCE_URL_FMT = '{}{}/instances/<string:{}' + OBJECT_ID_SUFFIX + '>/'
RELATIONSHIP_URL_FMT = '{}relationships/{}'
# last parameter for the "method" urls below will be the method name
INSTANCEMETHOD_URL_FMT = '{}{}/instances/<string:{}>/methods/{}'
CLASSMETHOD_URL_FMT = '{}{}/methods/{}'
'''

# endpoint naming
INSTANCE_ENDPOINT_FMT = '{}api.{}Id'
ENDPOINT_FMT = '{}-api.{}'

# This is the default query limit
UNLIMITED = 1<<32 # used as default sqla "limit" parameter. -1 works for sqlite but not for mysql

USE_API_METHODS = True