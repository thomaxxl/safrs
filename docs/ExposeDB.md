# Expose an Existing Database as a JSON API with Flask, SQLAlchemy and OpenApi

Update: I've updated the code and moved things to [safrs/expose_existing](https://github.com/thomaxxl/safrs/tree/master/expose_existing) , some links will no longer work. I will add updates to the readme there

## Introduction
This document describes how to expose a database as a [JSON:API](http://jsonapi.org/) REST api. 
This approach can be used for most databases with SQLAlchemy support (such as mysql, postges, sqlite etc.)
Here we use the MySQL [employee sample database](https://github.com/datacharmer/test_db) as an example.
A live version of this API can be found [here](http://www.blackbirdbits.com/).

## Configuration

After installing the employee database as described in the [readme](https://github.com/datacharmer/test_db), the database contains the following tables:
```
mysql> show tables;
+----------------------+
| Tables_in_employees  |
+----------------------+
| current_dept_emp     |
| departments          |
| dept_emp             |
| dept_emp_latest_date |
| dept_manager         |
| employees            |
| salaries             |
| titles               |
+----------------------+
```

In order to expose this database as a [JSON:API](http://jsonapi.org/) webservice, we need to complete two steps: 
1. create SQLAlchemy database models for the employee database tables
2. create a webservice exposing the models

The tools needed can be installed by cloning the safrs github repository and installing the requirements:

```
git clone https://github.com/thomaxxl/safrs/
cd safrs
pip install -r requirements.txt
```

We use sqlacodegen to create the database models. Sqlacodegen is a tool that reads the structure of an existing database and generates the appropriate SQLAlchemy model code.
I added some small modifications so it works together with Flask and Safrs. In the safrs directory, go to the sqlacodegen subdirectory and execute the sqlacodegen main.py script to generate the SQLAlchemy models:
(change the mysql username and password to work with your database first)
```
PYTHONPATH=sqlacodegen/ python3 sqlacodegen/sqlacodegen/main.py mysql+pymysql://root:password@localhost/mysql > examples/models.py
```

The above command will create a python script containing the SQLAlchemy models: [employees.py](https://github.com/thomaxxl/safrs/blob/master/examples/employees.py)

To create a webservice exposing these models as a JSON API, we create another script where we configure a Flask webservice and import the SQLAlchemy models.
The small script can be found [here](https://github.com/thomaxxl/safrs/blob/master/examples/expose_existing/expose_models.py).

After adopting the webservice script, we can start the service:

```
PYTHONPATH=$PWD python3 ./expose_employees.py localhost 5000
```

This will start the flask webserver at http://localhost:5000 . Here we can see the exposed tables:

![1](images/employees1.PNG)

## API Usage

At this point we are able to query the database objects and relationships over HTTP:

![2](images/employees2.PNG)

For example, to query the department information of an employee:

```bash
u@srv:~$ curl http://localhost:5000/dept_emp/10001_d005/department
{
  "data": {
    "attributes": {
      "dept_name": "Development",
      "dept_no": "d005"
    },
    "id": "d005",
    "relationships": {},
    "type": "departments"
  },
  "links": {
    "self": "http://localhost:5000/dept_emp/10001_d005/department"
  }
}
```

## Implementation

The [webservice script](https://github.com/thomaxxl/safrs/blob/master/examples/expose_existing/expose_models.py) has to be modified to reflect our configuration. First we have to set the database URI parameter `DB_URI`

```python
DB_URI = 'mysql+pymysql://root:password@localhost/employees'
app = Flask('SAFRS Demo App')
app.config.update( SQLALCHEMY_DATABASE_URI = DB_URI,
                   DEBUG = True)

```

We also have to make sure that the models.py module is in our path:

```python
import models 
```

models.py contains the SQLAlchemy models created by our modified sqlacodegen script. The models that will be exposed inherit both
from `SAFRSBase` and the SQLAlchemy `Base` model:

```python
class Department(SAFRSBase, Base):
    __tablename__ = 'departments'

    dept_no = Column(CHAR(4), primary_key=True)
    dept_name = Column(String(40), nullable=False, unique=True)
```

The [expose_models.py](https://github.com/thomaxxl/safrs/blob/master/examples/expose_existing/expose_model.spy) script will look in the imported models module for classes that will be exposed.
```python
        for name, model in inspect.getmembers(models):
            bases = getattr(model, '__bases__', [] )
            if SAFRSBase in bases:
                # Create an API endpoint
                api.expose_object(model)
```                

When the models are loaded, the openapi (fka swagger) schema will be generated and the app will be started.

