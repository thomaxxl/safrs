[![Latest Version](https://img.shields.io/pypi/v/safrs.svg)](https://pypi.python.org/pypi/safrs/)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/safrs.svg)](https://pypi.python.org/pypi/safrs/)
[![License](https://img.shields.io/pypi/l/safrs.svg)](https://github.com/thomaxxl/safrs/blob/master/LICENSE)
[![Downloads](https://pepy.tech/badge/safrs)](https://pepy.tech/project/safrs)

# SAFRS: Python OpenAPI & JSON:API Framework

![demo](docs/images/safrs.gif)

<a class="mk-toclify" id="table-of-contents"></a>

- [Overview](#overview)
- [Installation](#installation)
- [JSON:API Interface](#http-methods)
- [Resource Objects](#resource-objects)
- [Relationships](#relationships)
- [Methods](#methods)
    - [Custom Methods](#custom-methods)
    - [Class Methods](#class-methods)
- [Initialization](#initialization)
- [HTTP Status Codes](#http-status-codes)
- [Security](security)
- [Endpoint Naming](#endpoint-naming)
- [Configuration](#configuration)
- [Exposing Existing Databases](#expose-existing)
- [More Examples and Use Cases](#more-examples-and-use-cases)
- [Advanced Usage](#advanced-usage)
    - [Custom Serialization](#custom-serialization)
    - [Custom Decorators](#custom-decorators)
    - [API Methods](#api-methods)
    - [Custom Swagger](#custom-swagger)
- [Limitations & TODOs](#limitations--todos)
- [References](#references)
- [Thanks](#thanks)


<a class="mk-toclify" id="overview"></a>
## Overview

SAFRS is an acronym for **S**ql**A**lchemy **F**lask-**R**estful **S**wagger. The purpose of this framework is to help python developers create a self-documenting JSON API for sqlalchemy database objects and relationships. These objects can be serialized to JSON and can be created, retrieved, updated and deleted through the JSON API. 
Optionally, custom resource object methods can be exposed and invoked using JSON.
Class and method descriptions and examples can be provided in yaml syntax in the code comments. The description is parsed and shown in the swagger web interface. 

The result is an easy-to-use [swagger/OpenAPI](https://swagger.io/) and [JSON:API](https://jsonapi.org) compliant API implementation.

A __[LIVE DEMO](http://thomaxxl.pythonanywhere.com) is available__, implementing the [relationship example](examples/demo_relationship.py).

<a class="mk-toclify" id="installation"></a>
## Installation

SAFRS can be installed as a [pip package](https://pypi.python.org/pypi/safrs/) or by downloading the latest version from github, for example:

```bash
git clone https://github.com/thomaxxl/safrs
cd safrs
pip3 install -r requirements.txt --user
python3 setup.py install --user
```

The examples can then be started with 
```
python3 examples/demo_relationship.py "your-interface-ip"
```

<a class="mk-toclify" id="http-methods"></a>
## JSON:API Interface

Exposed resource objects can be queried using the [JSON:API format](http://jsonapi.org/format/). The API supports following HTTP operations:

- GET : Retrieve an object or a list of objects
- PATCH : Update an object.
- DELETE: Delete an object.
- POST : Create an object. 

Please check the [JSON:API spec](http://jsonapi.org/format/) for more implementation details. 
You can also check the interface in the [live demo](http://thomaxxl.pythonanywhere.com/api).

<a class="mk-toclify" id="resource-objects"></a>
## Resource Objects

Database objects are implemented as subclasses of the SAFRSBase and SQLAlchemy model classes. The SQLAlchemy columns are serialized to JSON when the corresponding REST API is invoked. 

Following example from [demo.py](examples/demo.py) illustrates how the API is built and documented:

```python
class User(SAFRSBase, db.Model):
    '''
        description: User description
    '''
    __tablename__ = 'Users'
    id = Column(String, primary_key=True)
    name = Column(String, default='')
    email = Column(String, default='')

```

The User class is implemented as a subclass of 
- db.Model: SQLAlchemy base
- SAFRSBase: Implements JSON serialization for the object and generates (swagger) API documentation

This User object is then exposed through the web interface using the Api object

```python 
api.expose_object(User)
``` 

The User object REST methods are available on /User, the swagger schema is available on /api/swagger.json and the UI is available on /api/:
![User Swagger](docs/images/USER_swagger.png)


<a class="mk-toclify" id="relationships"></a>
## Relationships

Database object such as the User class from the demo.py example can be extended to include relationships with other objects. The demo_relationship.py contains following extension of the User class where a relationship with the Book class is implemented:

```python
class User(SAFRSBase, db.Model):
    '''
        description: User description
    '''
    __tablename__ = 'Users'
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, default='')
    email = db.Column(db.String, default='')
    books = db.relationship('Book', back_populates="user")
...
``` 

A many-to-one database association is declared by the back_populates relationship argument.
The Book class is simply another subclass of SAFRSBase and db.Model, similar to the previous User class:

```python
class Book(SAFRSBase, db.Model):
    '''
        description: Book description
    '''
    __tablename__ = 'Books'
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, default='')
    user_id = db.Column(db.String, db.ForeignKey('Users.id'))
    user = db.relationship('User', back_populates='books')
```

The User.book relationship can be queried in the API through the following endpoints:
![Relations Swagger](docs/images/Relations_swagger.png)

- POST adds an item to the relationship
- DELETE removes an item from the relationship
- GET retrieves a list of item ids

The relationship REST API works similarly for one-to-many relationships. 

<a class="mk-toclify" id="methods"></a>
## Methods

<a class="mk-toclify" id="custom-methods"></a>
### Custom Methods

Safrs allows the user to implement custom methods on the exposed objects. This methods can be invoked through the json API by sending an HTTP POST request to the method endpoint
The following example implements a "send_mail" method fro example:

```python
class User(SAFRSBase, db.Model):
    '''
        description: User description
    '''
    __tablename__ = 'Users'
    id = Column(String, primary_key=True)
    name = Column(String, default='')
    email = Column(String, default='')

    # Following method is exposed through the REST API 
    # This means it can be invoked with a HTTP POST
    @jsonapi_rpc(http_methods=['POST','GET'])
    def send_mail(self, email):
        '''
            description : Send an email
            args:
                email:
                    type : string 
                    example : test email
        '''
        content = 'Mail to {} : {}\n'.format(self.name, email)
        return { 'result' : 'sent {}'.format(content)}

```

This method shows up in the swagger interface:

![Method Swagger](docs/images/method_swagger.PNG)

The ```send_mail``` method is documented with the ```jsonapi_rpc``` decorator. 
This decorator generates a schema based on the function documentation. This documentation contains yaml specification of the API which is used by the swagger UI. 

[api_methods.py](safrs/api_methods.py) contains a couple of methods that can be used in your models.

The yaml specification has to be in the first part of the function and class comments. These parts are delimited by four dashes ("----") . The rest of the comment may contain additional documentation.

<a class="mk-toclify" id="class-methods"></a>
### Class Methods

Two class-level methods have been defined to facilitate object retrieval:

* **lookup** : retrieve a list of objects that match the argument list. For example, following HTTP POST request to a container will retrieve a list of itemswhere the name is "thomas"
```json
{
  "method": "lookup",
  "args": {
    "name": "thomas"
  }
}
```

* **get_list** : retrieve a list of the items with the specified ID's

<a class="mk-toclify" id="initialization"></a>
## Application Initialization
The API can be initialized like this:
```python
api = SAFRSAPI(app, host=HOST, port=PORT, prefix=API_PREFIX)
```
Then you can expose objects with
```python
api.expose_object(User)    
```

An example that uses the flask app factory pattern is implement in [examples/mini_app.py](examples/mini_app.py)

<a class="mk-toclify" id="http-status-codes"></a>
## HTTP Status Codes

HTTP status codes are used to signal success or failure of a REST operation: 
- 200 : OK 
- 201 : The request has been fulfilled and resulted in a new resource being created.
- 204 : No Content, DELETE operation was successful
- 400 : The services raised an exception, for example in case of invalid input
- 500 : Internal Server Error

In case of errors( status codes 400+ ), the log file contains a stacktrace. 
Two custom exceptions are defined in errors.py: ValidationError and GenericError. 
In case of errors, the webservice will return a default HTTP status code 500 and a customizable error message, for example

```
{
  "error": "Failed to execute query Entity '<class 'C2_server.Image'>' has no property 'namex'"
}
```

<a class="mk-toclify" id="security"></a>
## Security

### Authorization

Authorization can be implemented by applying decorators to the endpoints generated by the `expose_objects` method.
Examples for flask_login and flask_jwt_extended can be found in the [examples/authentication](examples/authentication) directory.

### Logging

The default logging is configured to not show verbose error messages, so not to reveal information of the backend to the user, which may also mitigate script injection attacks in case the log messages are reflected in the user output.
In case you do want verbose logging, you can set the log level to DEBUG:

```python
app.config.update(DEBUG=True)
```

<a class="mk-toclify" id="endpoint-naming"></a>
## Endpoint Naming
As can be seen in the swagger UI:
- the endpoint collection path names are the SQLAlchemy \_\_tablename\_\_ properties (e.g. /Users )
- the parameter names are derived from the SAFRSBase class names (e.g. {UserId} )
- the the relationship names are the SAFRSBase class relationship names (e.g /books )
The URL path format is [configurable](#configuration)

<a class="mk-toclify" id="configuration"></a>
## Configuration

Some configuration parameters can be set in [config.py](safrs/config.py):
- USE_API_METHODS: set this to false in case you want to disable the `jsonapi_rpc` functionality
- INSTANCE_URL_FMT: This parameter declares the instance url path format
- RELATIONSHIP_URL_FMT: This parameter declares the relationship endpoint path format

<a class="mk-toclify" id="expose-existing"></a>
## Exposing Existing Databases
Safrs allows you to Expose existing databases as jsona:api services with the [expose_existing.py](expose_existing/expose_existing.py) script, for example:

```bash
python3 expose_existing.py mysql+pymysql://root:password@localhost/sakila --host localhost
```

This script uses sqlacodegen to generate a source file containing the SQLAlchemy and `SAFRSBase` database models and starts the API webservice.

More details [here](docs/ExposeDB.md)

<a class="mk-toclify" id="more-examples-and-use-cases"></a>
## More Examples and Use Cases
The [examples](examples) folder contains more example scripts:
- Using a sha hash as primary key (id)
- CORS usage
- Flask-Admin integration example, eg.:
![demo](docs/images/flask-admin.png)

<a class="mk-toclify" id="advanced-usage"></a>
## Advanced Usage

<a class="mk-toclify" id="custom-serialization"></a>
### Custom Serialization
Serialization and deserialization are implemented by the SAFRSBase `to_dict` and `__init__` : you can extend these methods as usual.
For example, if you would like to add some attributes to the json payload of the User object, you can override the to_dict method:

```python
class User(SAFRSBase, db.Model):
    '''
        description: User description
    '''
    __tablename__ = 'Users'
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, default='')
    email = db.Column(db.String, default='')
    books = db.relationship('Book', back_populates="user")

    def to_dict(self):
        result = SAFRSBase.to_dict(self)
        result['custom_field'] = 'custom'
        return result
``` 

This will add the `custom_field` attribute to the result attributes:
```json
"attributes": {
    "custom_field": "custom",
    "email": "reader_email0",
    "name": "Reader 0"
}
```

<a class="mk-toclify" id="custom-decorators"></a>
### Custom Decorators
The `custom_decorators` class attribute list can be used to add custom decorators to the instance HTTP endpoint. An example of this functionality is implemented
in the [authentication examples](examples/authentication).

<a class="mk-toclify" id="api-methods"></a>
### API Methods
Some additional API RPC methods are implemented in [api_methods.py](safrs/api_methods.py), e.g. mysql regex search. 

<a class="mk-toclify" id="custom-swagger"></a>
### Custom swagger
The swagger schema can be merged with a modified schema dictionary by supplying the to-be-merged dictionary as the `custom_swagger` argument to `SAFRSAPI`, e.g.
```python
custom_swagger = {"info": {"title" : "New Title" }} # Customized swagger title will be merged
api = SAFRSAPI(app, host=swagger_host, port=PORT, prefix=OAS_PREFIX, api_spec_url=OAS_PREFIX+'/swagger',
               custom_swagger=custom_swagger, schemes=['http', 'https'], description=description)
```

<a class="mk-toclify" id="limitations--todos"></a>
## Limitations & TODOs

This code was developed for a specific use-case and may not be flexible enough for everyone's needs. A lot of the functionality is available but not documented for the sake of brevity.
Performance is reasonable for regular databases, but once you start exposing really big tables you may run into problems, for example: the `count()` for mysql innodb is slow on large(1M rows) tables, a workaround can be implemented by querying the `sys` tables or using werkzeug caching. 
Feel free to open an issue or drop [me](mailto:thomas.pollet+no+spam+@gmail.com) an email if you run into problems or something isn't clear!

<a class="mk-toclify" id="references"></a>
## References

- [JSON:API specification](http://jsonapi.org/format/)
- [OpenApi (Swagger)](https://www.openapis.org/)
- [Flask](http://flask.pocoo.org/)
- [SQLAlchemy](https://www.sqlalchemy.org/)

<a class="mk-toclify" id="thanks"></a>
## Thanks

I developed this code when I worked at [Excellium Services](https://www.excellium-services.com/). They allowed me to open source it when I stopped working there.
