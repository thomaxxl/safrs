#!/usr/bin/env python3
"""
  This demo application demonstrates how the generated swagger can be customized

"""
import sys
import logging
import builtins
from flask import Flask, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_swagger_ui import get_swaggerui_blueprint
from safrs import SAFRSBase, SAFRSAPI, jsonapi_rpc

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
    swagger_host = HOST

    with app.app_context():
        # Create a user and a book and add the book to the user.books relationship
        user = User(name="thomas", email="em@il")
        book = Book(name="test_book")
        user.books.append(book)
        custom_swagger = {
            "info": {"title": "New Title", "description": "new description"},
            "securityDefinitions": {"ApiKeyAuth": {"type": "apiKey", "in": "header", "name": "My-ApiKey"}},
        }  # Customized swagger will be merged

        api = SAFRSAPI(
            app,
            host=swagger_host,
            port=PORT,
            prefix=API_PREFIX,
            api_spec_url=API_PREFIX + "/swagger",
            custom_swagger=custom_swagger,
            schemes=["http", "https"],
        )

        # Expose the database objects as REST API endpoints
        api.expose_object(User)
        api.expose_object(Book)
        # Register the API at /api/docs
        print("Starting API: http://{}:{}{}".format(HOST, PORT, API_PREFIX))
        app.run(host=HOST, port=PORT)
