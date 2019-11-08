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
    http_methods = ["get"]
    exclude_rels = ["books"]
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
        # Register the API at /api/docs
        print("Starting API: http://{}:{}{}".format(HOST, PORT, API_PREFIX))
        app.run(host=HOST, port=PORT)
