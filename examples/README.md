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



