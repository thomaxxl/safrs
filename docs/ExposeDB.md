# Expose an Existing Database as a JSON API

## Introduction
This document describes how to expose a database as a [JSON:API](http://jsonapi.org/) REST api. 
This approach can be used for most databases with SQLAlchemy support (such as mysql, postges, sqlite etc.)
Here we use the MySQL [employee sample database](https://github.com/datacharmer/test_db) as an example.
A live version of this API can be found [here](http://www.blackbirdbits.com/).

## Configuration

After installing the employee database as described in the github [readme](https://github.com/datacharmer/test_db), the database contains the following tables:
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
PYTHONPATH=sqlacodegen/ python3 sqlacodegen/sqlacodegen/main.py mysql+pymysql://root:password@localhost/mysql > examples/m
odels.py
```

The above command will create a python script containing the SQLAlchemy models: [employees.py](https://github.com/thomaxxl/safrs/blob/master/examples/employees.py)

To create a webservice exposing these models as a JSON API, we create another script where we configure a Flask webservice and import the SQLAlchemy models.
The complete script can be found [here](https://github.com/thomaxxl/safrs/blob/master/examples/expose_models.py).

After creating the webservice script, we can start the service:
```
PYTHONPATH=$PWD python3 ./expose_employees.py localhost 5000
```

This will start the flask webserver at http://localhost:5000 . Here we can see the exposed tables:

!(images/employees1.PNG)

## API Usage

At this point we are able to query the database objects and relationships over HTTP:

!(images/employees2.PNG)

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
