## Basic Use Case
[demo.py](demo.py) : a small sample application
example use:
```bash
PYTHONPATH=$PWD python3 examples/demo.py 10.0.0.9
```

## Relationships
[demo_relationship.py](demo_relationship.py) : an extension of the demo.py to demonstrate relationship functionality

## Expose Existing Databases:

It is possible to expose existing databases, as an example I implemented the [employees](https://github.com/datacharmer/test_db) and [sakila](https://github.com/datacharmer/test_db/sakila) test databases with safrs.

For this to work, I used a modified [sqlacodegen](https://github.com/thomaxxl/safrs/tree/master/sqlacodegen) to generate the sqlalchemy models [sakila.py](sakila.py) and [mysql_test_db.py](mysql_test_db.py) .

The Flask webservices are created with [expose_sakila.py](expose_sakila.py) and [expose_employees.py](expose_employees.py). They can be started as usual:

```bash
$ python3 examples/expose_employees.py 172.1.1.2 5000
```

Exposed sakila database:

![Skype Swagger](../docs/images/sakila.png)


Unfortunatley, the code generated with sqlacodegen needed some manual changes before it was usable. For example, the declarative column types for INTEGER and SMALLINT didn't work so I had to create small wrappers to fix this:
```python
def SMALLINT(_):
    return db.SMALLINT

def INTEGER(_):
    return db.INTEGER
```

You may run into similar problems trying to expose other schemas. These problems may be hard to solve if you're unfamiliar with SQLAlchemy. 
Feel free to open a github issue and I'll try to help you out.