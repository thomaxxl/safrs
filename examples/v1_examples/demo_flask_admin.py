#!/usr/bin/env python
"""
  This demo application demonstrates the functionality of the safrs documented REST API
  After installing safrs with pip, you can run this app standalone:
  $ python3 demo_relationship.py [Listener-IP]

  This will run the example on http://Listener-Ip:5000

  - A database is created and a user is added
  - A rest api is available
  - swagger documentation is generated
"""
import sys
import logging
import builtins
from flask import Flask, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_swagger_ui import get_swaggerui_blueprint
from flask_cors import CORS
from sqlalchemy import Column, String, ForeignKey
from safrs.db import SAFRSBase, documented_api_method
from safrs.jsonapi import SAFRSJSONEncoder, Api

from flask_admin import Admin
from flask_admin import BaseView
from flask_admin.contrib import sqla

db = SQLAlchemy()
# Needed because we don't want to implicitly commit when using flask-admin
SAFRSBase.db_commit = False

# Example sqla database object
class User(SAFRSBase, db.Model):
    """
        description: User description
    """

    __tablename__ = "Users"
    id = Column(String, primary_key=True)
    name = Column(String, default="")
    email = Column(String, default="")
    books = db.relationship("Book", back_populates="user", lazy="dynamic")

    # Following method is exposed through the REST API
    # This means it can be invoked with a HTTP POST
    @documented_api_method
    def send_mail(self, email):
        """
            description : Send an email
            args:
                email:
                    type : string
                    example : test email
        """
        content = "Mail to {} : {}\n".format(self.name, email)
        with open("/tmp/mail.txt", "a+") as mailfile:
            mailfile.write(content)
        return {"result": "sent {}".format(content)}


class Book(SAFRSBase, db.Model):
    """
        description: Book description
    """

    __tablename__ = "Books"
    id = Column(String, primary_key=True)
    name = Column(String, default="")
    user_id = Column(String, ForeignKey("Users.id"))
    user = db.relationship("User", back_populates="books")


class UserView(sqla.ModelView):
    pass


class BookView(sqla.ModelView):
    pass


if __name__ == "__main__":
    HOST = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
    PORT = 5000
    app = Flask("SAFRS Demo Application")
    CORS(app, origins="*", allow_headers=["Content-Type", "Authorization", "Access-Control-Allow-Credentials"], supports_credentials=True)
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", DEBUG=True, SECRET_KEY="secret")
    db.init_app(app)
    db.app = app
    # Create the database
    db.create_all()
    admin = Admin(app, url="/admin")
    admin.add_view(UserView(User, db.session))
    admin.add_view(BookView(Book, db.session))
    SAFRSBase.db_commit

    API_PREFIX = "/api"
    log = logging.getLogger()
    log.setLevel(logging.DEBUG)
    logging.getLogger(__name__).setLevel(logging.DEBUG)
    builtins.log = log

    with app.app_context():
        # Create a user and a book and add the book to the user.books relationship
        user = User(name="thomas", email="em@il")
        book = Book(name="test_book")
        user.books.append(book)
        db.session.add(user)
        db.session.add(book)
        db.session.commit()  # COMMIT because SAFRSBase.db_commit = False

        api = Api(app, api_spec_url=API_PREFIX + "/swagger", host="{}:{}".format(HOST, PORT))
        # Expose the database objects as REST API endpoints
        api.expose_object(User)
        api.expose_object(Book)
        # Set the JSON encoder used for object to json marshalling
        app.json_encoder = SAFRSJSONEncoder

        @app.route("/")
        def index():
            """Create a redirect from / to /api"""
            return """<ul><li><a href=admin>admin</a></li><li><a href=api>api</a></li>"""

        # Register the API at /api/docs
        swaggerui_blueprint = get_swaggerui_blueprint(API_PREFIX, API_PREFIX + "/swagger.json")
        app.register_blueprint(swaggerui_blueprint, url_prefix=API_PREFIX)
        print("Starting API: http://{}:{}{}".format(HOST, PORT, API_PREFIX))
        app.run(host=HOST, port=PORT)
