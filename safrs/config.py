OBJECT_ID_SUFFIX = 'Id'

# URL
INSTANCE_URL_FMT = '{}{}/<string:{}' + OBJECT_ID_SUFFIX + '>/'
CLASSMETHOD_URL_FMT = '{}{}/{}'
INSTANCEMETHOD_URL_FMT = '{}{}/<string:{}>/{}'
RELATIONSHIP_URL_FMT = '{}{}'

# endpoint naming
INSTANCE_ENDPOINT_FMT = '{}api.{}Id'
ENDPOINT_FMT = '{}-api.{}'
