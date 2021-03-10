#!/usr/bin/env python3
#
# This example shows how you can implement a SAFRS endpoint without a SQLAlchemy model
#
import sys
import logging
from flask import Flask, redirect, request
from flask_sqlalchemy import SQLAlchemy
from flask_swagger_ui import get_swaggerui_blueprint
from safrs import SAFRSBase, SAFRSAPI, jsonapi_rpc, jsonapi_attr
from safrs.safrs_types import SAFRSID
from safrs.util import classproperty
from collections import namedtuple
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm.interfaces import ONETOMANY, MANYTOMANY  # , MANYTOONE

db = SQLAlchemy()


class Test(SAFRSBase):
    """
        description: Stateless class example
    """

    instances = []

    _s_type = "TestType"
    _s_url = "http://safrs-example.com/api/Test"
    _s_relationships = {}
    _s_query = None

    def __new__(cls, *args, **kwargs):
        """
            override SAFRSBase.__new__
        """
        result = object.__new__(cls)
        cls.instances.append(result)
        return result

    def __init__(self, *args, **kwargs):
        """
            Constructor
        """
        self.id = kwargs.get("id")
        self.name = kwargs.get("name")

    @classmethod
    def _s_post(cls, *args, **kwargs):
        """
            Called for a HTTP POST
        """
        print(f"Post with {kwargs}")
        result = cls(**kwargs, id=len(cls.instances))
        return result

    def _s_patch(self, *args, **kwargs):
        """
            Called for a HTTP PATCH
        """
        print(f"Patch with {kwargs}")
        return self

    @classmethod
    def jsonapi_filter(cls):
        """
            Called for a HTTP GET (collection)
        """
        return cls.instances

    @classmethod
    def _s_count(cls):
        return 1

    @jsonapi_attr
    def name(self):
        return "My Name"

    @jsonapi_attr
    def my_custom_field(self):
        return -1

    @property
    def jsonapi_id(self):
        return self.id

    @classmethod
    def get_instance(cls, id, failsafe=False):
        """
            return the instance specified by id
        """
        for instance in cls.instances:
            if instance.id == id:
                return instance
        return None

    @classproperty
    def class_(cls):
        return cls


HOST = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
PORT = 5000
app = Flask("SAFRS Demo Application")
app.config.update(SQLALCHEMY_DATABASE_URI="sqlite:///", DEBUG=True)


if __name__ == "__main__":
    db.init_app(app)
    db.app = app
    # Create the database
    db.create_all()
    API_PREFIX = ""

    with app.app_context():
        test_obj = Test(id=1)
        api = SAFRSAPI(app, host="{}".format(HOST), port=PORT, prefix=API_PREFIX)
        # Expose the database objects as REST API endpoints
        api.expose_object(Test)
        # Register the API at /api/docs
        print("Starting API: http://{}:{}{}".format(HOST, PORT, API_PREFIX))
        app.run(host=HOST, port=PORT)
