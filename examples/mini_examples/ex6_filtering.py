#!/usr/bin/env python3
"""

Custom Filtering Example:

* Like:
http://server:5000/People/?filter[name][like]=user1%
* In:
http://server:5000/People/?filter[id][in]=[1,2]

"""

import sys
import json
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from safrs import SAFRSBase, SAFRSAPI, ValidationError
import re
import operator
from flask import request


db = SQLAlchemy()


@classmethod
def jsonapi_filter_achim(cls):

    filters = []
    expressions = []
    for req_arg, val in request.args.items():
        filter_attr = re.search(r"filter\[(\w+)\]\[(\w+)\]", req_arg)
        if filter_attr:
            name = filter_attr.group(1)
            op = filter_attr.group(2)
            if op in ["in", "notin"]:
                val = json.loads(val)
            filters.append({"name": name, "op": op, "val": val})
            continue

        filter_attr = re.search(r"filter\[(\w+)\]", req_arg)
        if filter_attr:
            name = filter_attr.group(1)
            op = "eq"
            filters.append({"name": name, "op": op, "val": val})

    query = cls._s_query

    for filt in filters:
        attr_name = filt.get("name")
        attr_val = filt.get("val")
        if attr_name != "id" and attr_name not in cls._s_jsonapi_attrs:
            raise ValidationError('Invalid filter "{}", unknown attribute "{}"'.format(filt, attr_name))

        op_name = filt.get("op", "").strip("_")
        attr = cls._s_jsonapi_attrs[attr_name] if attr_name != "id" else cls.id
        if op_name in ["in", "notin"]:
            op = getattr(attr, op_name + "_")
            query = query.filter(op(attr_val))
        elif op_name in ["like", "ilike", "match", "notilike"] and hasattr(attr, "like"):
            # => attr is Column or InstrumentedAttribute
            like = getattr(attr, op_name)
            query = query.filter(like(attr_val))
        elif not hasattr(operator, op_name):
            raise ValidationError('Invalid filter "{}", unknown operator "{}"'.format(filt, op_name))
        else:
            op = getattr(operator, op_name)
            expressions.append(op(attr, attr_val))

    return query.filter(*expressions)


class BaseModel(SAFRSBase, db.Model):
    __abstract__ = True
    jsonapi_filter = jsonapi_filter_achim


class Person(BaseModel):
    """
    description: My person description
    """

    __tablename__ = "People"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, default="John Doe")


def create_app(config_filename=None, host="localhost"):
    app = Flask("demo_app")
    app.secret_key = "not so secret"
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://")
    db.init_app(app)

    with app.app_context():
        db.create_all()
        api = SAFRSAPI(app, host=host, port=5000)
        api.expose_object(Person)

        # Populate the db with users and a books and add the book to the user.books relationship
        for i in range(20):
            user = Person(name=f"user{i}", email=f"email{i}@email.com")

    return app


# address where the api will be hosted, change this if you're not running the app on localhost!
host = sys.argv[1] if sys.argv[1:] else "127.0.0.1"
app = create_app(host=host)

if __name__ == "__main__":
    app.run(host=host)
