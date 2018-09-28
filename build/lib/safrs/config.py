'''
config.py
'''
# The suffix of the url path parameter shown in the swagger UI, eg Id => /Users/{UserId}
import os, logging, builtins, sys
from . import SAFRS

OBJECT_ID_SUFFIX = os.environ.get('OBJECT_ID_SUFFIX', SAFRS.OBJECT_ID_SUFFIX)
if not OBJECT_ID_SUFFIX:
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
INSTANCEMETHOD_URL_FMT = os.environ.get('INSTANCEMETHOD_URL_FMT', SAFRS.ENABLE_RELATIONSHIPS)
if not INSTANCEMETHOD_URL_FMT:
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
ENDPOINT_FMT = '{}api.{}'

#UNLIMITED = int(os.environ.get('SAFRS_UNLIMITED', 1<<32))
UNLIMITED = int(os.environ.get('SAFRS_UNLIMITED', SAFRS.SAFRS_UNLIMITED))
# This is the default query limit
# used as default sqla "limit" parameter. -1 works for sqlite but not for mysql
BIG_QUERY_THRESHOLD = 1000 # Warning level
MAX_QUERY_THRESHOLD = BIG_QUERY_THRESHOLD


USE_API_METHODS = True

# ENABLE_RELATIONSHIPS enables relationships to be included.
# This may slow down certain queries if the relationships are not properly configured!
ENABLE_RELATIONSHIPS = bool(os.environ.get('ENABLE_RELATIONSHIPS', SAFRS.ENABLE_RELATIONSHIPS))
if not ENABLE_RELATIONSHIPS:
    ENABLE_RELATIONSHIPS = True
