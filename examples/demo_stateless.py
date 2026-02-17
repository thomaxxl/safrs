#!/usr/bin/env python3
from typing import Any
#
# This example shows how you can implement a SAFRSBase object (the Test class)
# without a SQLAlchemy model
# It does require you to implement some attributes and methods yourself
#
import sys
import logging
from flask import Flask, redirect, request
from flask_sqlalchemy import SQLAlchemy
from flask_swagger_ui import get_swaggerui_blueprint
from safrs import SAFRSBase, SafrsApi, jsonapi_rpc, jsonapi_attr
from safrs.safrs_types import SAFRSID
from safrs.util import classproperty
from collections import namedtuple
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm.interfaces import ONETOMANY, MANYTOMANY  # , MANYTOONE
import pdb

db = SQLAlchemy()


class User(SAFRSBase, db.Model):
    """
    description: User description
    """

    __tablename__ = "Users"
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, default="")
    email = db.Column(db.String, default="")
    books = db.relationship("Book", back_populates="user", lazy="dynamic")


class Book(SAFRSBase, db.Model):
    """
    description: Book description
    """

    __tablename__ = "Books"
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, default="")
    user_id = db.Column(db.String, db.ForeignKey("Users.id"))
    user = db.relationship("User", back_populates="books")


#
#
#


class TestQuery:
    """
    The safrs sqla serialization calls some sqlalchemy methods
    We emulate them here
    """

    def first(cls: Any) -> Any:
        return Test(name="name 0")

    def filter_by(cls: Any, *args: Any, **kwargs: Any) -> Any:
        return cls

    def count(cls: Any, *args: Any, **kwargs: Any) -> Any:
        return 100

    def offset(cls: Any, offset: Any) -> Any:
        return cls

    def limit(cls: Any, limit: Any) -> Any:
        return cls

    def all(cls: Any) -> Any:
        return [Test(name="name")]

    def order_by(cls: Any, attr_name: Any) -> Any:
        return cls


class Mapper:
    class_ = Book


class TestBookRelationship:
    key = "books"
    direction = ONETOMANY
    mapper = Mapper
    _target = [Book]

    def __init__(self: Any, parent: Any) -> None:
        self.parent = parent

    def __iter__(self: Any) -> Any:
        """
        yield items from the collection that should be in the relationship
        """
        for book in Book.query.all():
            yield book


class Test(SAFRSBase):
    """
    description: Book description
    """

    id = 1
    id_type = SAFRSID
    ja_type = "TestType"
    my_custom_field = ""
    books = TestBookRelationship

    def __new__(cls: Any, *args: Any, **kwargs: Any) -> Any:
        """
        override SAFRSBase.__new__
        """
        return object.__new__(cls)

    def __init__(self: Any, *args: Any, **kwargs: Any) -> None:
        """
        Constructor
        """
        self.books = TestBookRelationship(self)
        self.name = kwargs.get("name")

    @classproperty
    def _s_type(cls: Any) -> Any:
        """
        json:api type
        """
        return cls.ja_type

    @classproperty
    def _s_query(cls: Any) -> Any:
        """
        query placeholder
        """
        return TestQuery()

    @classproperty
    def _s_relationships(cls: Any) -> Any:
        """
        return the included relationships
        """
        return {"books": cls.books}

    @jsonapi_attr
    def name(self: Any) -> Any:
        return "My Name"

    @jsonapi_attr
    def my_custom_field(self: Any) -> Any:
        return -1

    @classproperty
    def _s_url(self: Any) -> Any:
        """
        The URL to return in the jsonapi "links" parameter
        """
        return "http://safrs-example.com/api/Test"

    @classmethod
    def get_instance(cls: Any, id: Any, failsafe: Any=False) -> Any:
        """
        return the instance specified by id
        """
        result = Test()
        return result

    @classproperty
    def class_(cls: Any) -> Any:
        return cls


TestBookRelationship.parent = Test

HOST = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
PORT = 5000
app = Flask("SAFRS Demo Application")
app.config.update(SQLALCHEMY_DATABASE_URI="sqlite:///", DEBUG=True)

from flask import jsonify


@app.route("/tt")
def test() -> Any:
    data = [{k: v} for k, v in zip(["key1", "key2"], ["a", "b"])]
    return jsonify({"data": data})


if __name__ == "__main__":
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
        api = SafrsApi(app, host=f"{HOST}", port=PORT, prefix=API_PREFIX)
        # Expose the database objects as REST API endpoints
        api.expose_object(User)
        api.expose_object(Book)
        api.expose_object(Test)
        # Register the API at /api/docs
        print(f"Starting API: http://{HOST}:{PORT}{API_PREFIX}")
        app.run(host=HOST, port=PORT)
