[![Latest Version](https://img.shields.io/pypi/v/safrs.svg)](https://pypi.python.org/pypi/safrs/)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/safrs.svg)](https://pypi.python.org/pypi/safrs/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
![Python application](https://github.com/thomaxxl/safrs/workflows/Python%20application/badge.svg)
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/de12c50717e8487db5dcc31907e627f7)](https://www.codacy.com/gh/thomaxxl/safrs/dashboard?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=thomaxxl/safrs)
[![Downloads](https://pepy.tech/badge/safrs)](https://pepy.tech/project/safrs)

# SAFRS: Python OpenAPI & JSON:API Framework

![demo](docs/images/safrs.gif)

<a class="mk-toclify" id="table-of-contents"></a>

- [Introduction](#overview)
- [Installation](#installation)
- [JSON:API Interface](#http-methods)
- [Resource Objects](#resource-objects)
- [Relationships](#relationships)
- [Methods](#methods)
    - [Custom Methods](#custom-methods)
    - [Class Methods](#class-methods)
- [Initialization](#initialization)
- [Endpoint Naming](#endpoint-naming)
- [Configuration](#configuration)
- [Exposing Existing Databases](#expose-existing)
- [More Examples and Use Cases](#more-examples-and-use-cases)
- [Advanced Functionality](#advanced-usage)
    - [Filtering](#filtering)
- [Customization](#customization)
    - [Custom Serialization](#custom-serialization)
    - [Excluding Attributes and Relationships](#excluding-attrs-rels)
    - [HTTP Decorators](#http-decorators)
    - [API Methods](#api-methods)
    - [Custom Swagger](#custom-swagger)
    - [Classes Without SQLAlchemy Models](#Classes-Without-Models)

<a class="mk-toclify" id="overview"></a>
## Introduction

SAFRS exposes SQLAlchemy database models as a [JSON:API](https://jsonapi.org) webservice and generates the corresponding [swagger/OpenAPI](https://swagger.io/).

Documentation can be found in the [wiki](https://github.com/thomaxxl/safrs/wiki).

__We created a service to generate APIs using GenAI__, check it out [HERE](https://apifabric.ai)!

__A [LIVE DEMO](https://thomaxxl.pythonanywhere.com) is available__, where much of the basic functionality is implemented using a simple [example](examples/demo_pythonanywhere_com.py).


<a class="mk-toclify" id="installation"></a>
## Installation

SAFRS can be installed as a [pip package](https://pypi.python.org/pypi/safrs/) or by downloading the latest version from github, for example:

```bash
git clone https://github.com/thomaxxl/safrs
cd safrs
pip install .
```

Once the dependencies are installed, the [examples](examples) can be started, for example
```
python examples/demo_relationship.py "your-interface-ip"
```

<a class="mk-toclify" id="http-methods"></a>
## JSON:API Interface

Exposed resource objects can be queried using the [JSON:API format](http://jsonapi.org/format/). The API supports following HTTP operations:

- GET : Retrieve an object or a list of objects
- PATCH : Update an object.
- DELETE: Delete an object.
- POST : Create an object. 

Please check the [JSON:API spec](http://jsonapi.org/format/) for more implementation details. 
You can also try out the interface in the [live demo](http://thomaxxl.pythonanywhere.com/api).

<a class="mk-toclify" id="resource-objects"></a>
## Resource Objects

Database objects are implemented as subclasses of the SAFRSBase and SQLAlchemy model classes. The SQLAlchemy columns are serialized to JSON when the corresponding REST API is invoked. 

Following example [app](examples/demo_relationship.py) illustrates how the API is built and documented:

```python
class User(SAFRSBase, db.Model):
    """
        description: User description
    """

    __tablename__ = "Users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    email = db.Column(db.String)

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

The relationship API endpoints work similarly for one-to-many relationships.

Relationship members can also be included in the response when querying an instance, by specifying the relationship names as a comma separated list in the `include` query argument.

![relationship include swagger](docs/images/rel_include.PNG)

For example, to retrieve all items in the `books_read` relationship from the People endpoint, you may add the `include=books_read` url parameter


http://thomaxxl.pythonanywhere.com/api/People/?include=books_read

To retrieve nested relationship items, you can specify the nested relationship name after the '.', to retrieve the authors of the books_read instances for instance, you can use

http://thomaxxl.pythonanywhere.com/api/People/?include=books_read.author

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
api = SafrsApi(app, host=HOST, port=PORT, prefix=API_PREFIX)
```
Then you can expose objects with `expose_object`
```python
api.expose_object(User)    
```

An example that uses the flask app factory pattern is implement in [examples/mini_app.py](examples/mini_app.py)

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

More details [here](docs/ExposeDB.md). This approach is used by the [ApiLogicServer](https://github.com/valhuber/ApiLogicServer) project.

<a class="mk-toclify" id="more-examples-and-use-cases"></a>
## More Examples and Use Cases
The [examples](examples) folder contains more example scripts:
- Using a sha hash as primary key (id)
- CORS usage
- Flask-Admin integration example, eg.:
![demo](docs/images/flask-admin.png)

A docker image can be found here:
[https://github.com/thomaxxl/safrs-example](https://github.com/thomaxxl/safrs-example)

<a class="mk-toclify" id="advanced-usage"></a>
## Advanced Functionality

<a class="mk-toclify" id="filtering"></a>
### Filtering
The swagger shows the jsonapi filters that can be used in the url query arguments. Items with an exact match of the specified attribute value can be fetched by specifying the corresponding key-value query parameter. For example, suppose the `User` class, exposed at `/Users` has a `name` attribute, to retrieve all instances with the name "John", you can use a `GET` request to 
`/Users?filter[name]=John`.

It is also possible to use more generic filters by specifiying a JSON string, for example `filter=[{"name":"timestamp","op":"gt","val":"2020-08-01"},{"name":"timestamp","op":"lt","val":"2020-08-02"}]`.

More info can be found in the [wiki](https://github.com/thomaxxl/safrs/wiki/API-Functionality#filtering).

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

<a class="mk-toclify" id="customization"></a>
## Customization

<a class="mk-toclify" id="excluding-attrs-rels"></a>
### Excluding Attributes and Relationships
It is possible to specify attributes and relationships that should not be serialized by specifying the respective `exclude_attrs` and èxclude_rels` class attributes in your SAFRSBase instances.
Examples can be found [here](examples/demo_pythonanywhere_com.py#L81) and [here](examples/demo_http_get.py#L21)

<a class="mk-toclify" id="limit-http-verbs"></a>
### Limiting HTTP Methods
It is possible to limit the HTTP methods that are allowed by overriding the `http_methods` class attribute. An example can be found [here](examples/demo_http_get.py#L20)

<a class="mk-toclify" id="HTTP-decorators"></a>
### HTTP Decorators
The `decorators` class attribute list can be used to add custom decorators to the HTTP endpoints. An example of this functionality is implemented
in the [authentication examples](examples/authentication).


<a class="mk-toclify" id="api-methods"></a>
### API Methods
Some additional API RPC methods are implemented in [api_methods.py](safrs/api_methods.py), e.g. mysql regex search. 

<a class="mk-toclify" id="custom-swagger"></a>
### Custom swagger
The swagger schema can be merged with a modified schema dictionary by supplying the to-be-merged dictionary as the `custom_swagger` argument to `SafrsApi`, e.g.
```python
custom_swagger = {"info": {"title" : "New Title" }} # Customized swagger title will be merged
api = SafrsApi(app, host=swagger_host, port=PORT, prefix=OAS_PREFIX, api_spec_url=OAS_PREFIX+'/swagger',
               custom_swagger=custom_swagger, schemes=['http', 'https'], description=description)
```

<a class="mk-toclify" id="Classes-Without-Models"></a>
### Classes Without SQLAlchemy Models
You can implement a serializable class without a model but this requires some extra work because safrs needs to know which attributes and relationships to serialize. An example is implemented [here](examples/demo_stateless.py)

### More Customization
The documentation is being moved to the [wiki](https://github.com/thomaxxl/safrs/wiki)

<details>
<summary>About</summary>
SAFRS is an acronym for **S**ql**A**lchemy **F**lask-**R**estful **S**wagger. The purpose of this framework is to help python developers create a self-documenting JSON API for sqlalchemy database objects and relationships. These objects can be serialized to JSON and can be created, retrieved, updated and deleted through the JSON API. 
Optionally, custom resource object methods can be exposed and invoked using JSON.
Class and method descriptions and examples can be provided in yaml syntax in the code comments. The description is parsed and shown in the swagger web interface. 

The result is an easy-to-use [swagger/OpenAPI](https://swagger.io/) and [JSON:API](https://jsonapi.org) compliant API implementation.
</details>

<details>
<summary>limitations & Todos</summary>
This code was developed for a specific use-case and may not be flexible enough for everyone's needs. A lot of the functionality is available but not documented for the sake of brevity.
Performance is reasonable for regular databases, but once you start exposing really big tables you may run into problems, for example: the `count()` for mysql innodb is slow on large(1M rows) tables, a workaround can be implemented by querying the `sys` tables or using werkzeug caching. 
Feel free to open an issue or drop [me](mailto:thomas.pollet+no+spam+@gmail.com) an email if you run into problems or something isn't clear!
</details>

<details>
<summary>References</summary>

- [JSON:API specification](http://jsonapi.org/format/)
- [OpenApi (Swagger)](https://www.openapis.org/)
- [Flask](http://flask.pocoo.org/)
- [SQLAlchemy](https://www.sqlalchemy.org/)
</details>

<details>
<summary>Thanks</summary>
I developed this code when I worked at [Excellium Services](https://www.excellium-services.com/). They allowed me to open source it when I stopped working there.
</details>
