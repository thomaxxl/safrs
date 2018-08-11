# Expose an Existing Database as a JSON API

This document describes how to expose a database as a JSON:API rest api. 
This approach can be used for most databases with SQLAlchemy support (such as mysql, postges, sqlite etc.)
Here we use the MySQL [employee sample database](https://github.com/datacharmer/test_db) as an example.

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
PYTHONPATH=. python3 sqlacodegen/main.py mysql+pymysql://root:password@localhost/mysql > examples/employees.py
```

The above command will create a python script containing the SQLAlchemy models: [employees.py](https://github.com/thomaxxl/safrs/blob/master/examples/employees.py)

To create a webservice exposing these models as a JSON API, we create another script where we configure a Flask webservice and import the SQLAlchemy models.
The complete script can be found [here](https://github.com/thomaxxl/safrs/blob/master/examples/expose_employees.py).

Now that we create
```
PYTHONPATH=$PWD python3 ./expose_employees.py localhost
```

