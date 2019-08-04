#!/usr/bin/env python3
import sys
import logging
import builtins
from flask import Flask, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_swagger_ui import get_swaggerui_blueprint
from flask_cors import CORS
from safrs import SAFRSBase, SAFRSAPI, jsonapi_rpc

db = SQLAlchemy()

# Example sqla database object
class User(SAFRSBase, db.Model):
    """
        description: User description
    """

    __tablename__ = "Users"
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, default="")
    email = db.Column(db.String, default="")
    books = db.relationship("Book", back_populates="user", lazy="dynamic")

    # Following method is exposed through the REST API
    # This means it can be invoked with a HTTP POST
    @classmethod
    @jsonapi_rpc(http_methods=["POST"])
    def send_mail(self, **args):
        """
        description : Send an email
        args:
            email:
                type : string
                example : test email
        """
        return {"result": args}


class Book(SAFRSBase, db.Model):
    """
        description: Book description
    """

    __tablename__ = "Books"
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, default="")
    user_id = db.Column(db.String, db.ForeignKey("Users.id"))
    user = db.relationship("User", back_populates="books")


from safrs.util import classproperty
from collections import namedtuple

class TestID:

    @classmethod
    def get_pks(self, *args):
        return {"PK" : "pk_val"}

    @classproperty
    def column_names(cls):
        return ["id"]

    def get_id(self):
        return "tmpid"


class TestQuery:

    def first(cls):
        return Test(name = "name 0")

    def filter_by(cls, *args, **kwargs):
        return cls

    def count(cls, *args, **kwargs):
        return 100

    def offset(cls, offset):
        return cls

    def limit(cls, limit):
        return cls

    def all(cls):
        return [Test(name = "name")]
    


class Test(SAFRSBase):
    """
        description: Book description
    """
    id_type = TestID
    ja_type = "TestType"
    
    def __new__(cls, *args, **kwargs):
        return object.__new__(cls)

    def __init__(self, *args, **kwargs):
        self.name = kwargs.get("name")

    @classproperty
    def _s_type(cls):
        return cls.ja_type

    @classproperty
    def _s_query(cls):
        print(cls)
        return TestQuery()

    @classmethod
    def _s_get_jsonapi_rpc_methods(cls):
        return []

    @classproperty
    def _s_relationship_names(cls):
        return []

    @classproperty
    def _s_relationships(cls):
        return {}

    @classproperty
    def _s_jsonapi_attrs(cls):
        return ["my_custom_field"]

    @classproperty
    def _s_column_names(cls):
        return []
    
    @classproperty
    def _s_columns(cls):
        return []

    @classproperty
    def _s_url(self):
        return "http://tmp"
    
    @classmethod
    def get_instance(cls, id, failsafe=False):
        result = Test()
        return result

    @classmethod
    def _s_sample_id(cls):
        return 1

    def to_dict(self):
        result = { "name" : self.name , "my_custom_field" : "extra info" }
        return result



if __name__ == "__main__":
    HOST = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
    PORT = 5000
    app = Flask("SAFRS Demo Application")
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", DEBUG=True)
    db.init_app(app)
    db.app = app
    # Create the database
    db.create_all()
    API_PREFIX = ""

    with app.app_context():
        # Create a user and a book and add the book to the user.books relationship
        
        user = User(name="thomas", email="em@il")
        book = Book(name="test_book")
        user.books.append(book)
        api = SAFRSAPI(app, host="{}".format(HOST), port=PORT, prefix=API_PREFIX)
        # Expose the database objects as REST API endpoints
        api.expose_object(User)
        api.expose_object(Book)
        api.expose_object(Test)
        # Register the API at /api/docs
        print("Starting API: http://{}:{}{}".format(HOST, PORT, API_PREFIX))
        app.run(host=HOST, port=PORT)
