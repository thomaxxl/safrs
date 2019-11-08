#!/usr/bin/env python
"""
  This demo application demonstrates the functionality of the safrs documented REST API
  After installing safrs with pip and modifying the connection uri SQLALCHEMY_DATABASE_URI you can run this app standalone:

  $ python3 demo_relationship.py [Listener-IP]

  This will run the example on http://Listener-Ip:5000
  - users and books are created in the database
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
from safrs.db import SAFRSBase, jsonapi_rpc
from safrs.jsonapi import SAFRSJSONEncoder, Api, paginate, jsonapi_format_response, SAFRSFormattedResponse
from safrs.errors import ValidationError, GenericError
from safrs.api_methods import search, startswith
from safrs.safrs_types import SAFRSID, get_id_type

DB_NAME = "test"
SQLALCHEMY_DATABASE_PREFIX = "mysql+pymysql://root:password@localhost"

#
# Create the test db
#
import sqlalchemy

engine = sqlalchemy.create_engine(SQLALCHEMY_DATABASE_PREFIX)
engine.execute("CREATE DATABASE IF NOT EXISTS {}".format(DB_NAME))

#
#
#

db = SQLAlchemy()
myString = db.String(300)
SQLALCHEMY_DATABASE_URI = "{}/{}".format(SQLALCHEMY_DATABASE_PREFIX, DB_NAME)


def next_val(db_name, table_name):
    """
        Retrieve the next mysql autoincrement id
    """
    sql = '''SELECT AUTO_INCREMENT
             FROM information_schema.TABLES
             WHERE TABLE_SCHEMA = "{}"
             AND TABLE_NAME = "{}"'''.format(
        db_name, table_name
    )
    result = db.engine.execute(sql)
    for row in result:
        return row[0]


def get_id_type_mysql(db_name, table_name, cls):
    """
        Create the id_type class which generates the autoincrement id for our table
    """

    class SAFRSAutoIncrementId(SAFRSID):
        @staticmethod
        def gen_id():
            id = next_val(db_name, table_name)
            return id

        @staticmethod
        def validate_id(id):
            return int(id)

    return get_id_type(cls, SAFRSAutoIncrementId)


# Example sqla database object
class User(SAFRSBase, db.Model):
    """
        description: User description
    """

    __tablename__ = "Users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(myString, default="")
    email = db.Column(myString, default="")
    books = db.relationship("Book", back_populates="user", lazy="dynamic")

    # Following method is exposed through the REST API
    # This means it can be invoked with a HTTP POST
    @classmethod
    @jsonapi_rpc(http_methods=["POST", "GET"])
    def send_mail(self, **args):
        """
        description : Send an email
        args:
            email:
                type : string
                example : test email
        """
        return {"result": args}

    startswith = startswith
    search = search


User.id_type = get_id_type_mysql(DB_NAME, "Users", User)


class Book(SAFRSBase, db.Model):
    """
        description: Book description
    """

    __tablename__ = "Books"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(myString, default="")
    user_id = db.Column(db.Integer, db.ForeignKey("Users.id"))
    user = db.relationship("User", back_populates="books")


Book.id_type = get_id_type_mysql(DB_NAME, "Books", Book)


if __name__ == "__main__":
    HOST = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
    PORT = 5000
    app = Flask("SAFRS Demo Application")
    CORS(app, origins="*", allow_headers=["Content-Type", "Authorization", "Access-Control-Allow-Credentials"], supports_credentials=True)
    app.config.update(SQLALCHEMY_DATABASE_URI=SQLALCHEMY_DATABASE_URI, DEBUG=True)
    db.init_app(app)
    db.app = app
    # Create the database
    db.create_all()
    API_PREFIX = "/api"
    log = logging.getLogger()
    log.setLevel(logging.DEBUG)
    logging.getLogger(__name__).setLevel(logging.DEBUG)
    builtins.log = log
    # prevent redirects when a trailing slash isn't present
    app.url_map.strict_slashes = False

    with app.app_context():
        # Create a user and a book and add the book to the user.books relationship

        user = User(name="thomas", email="em@il")
        book = Book(name="test_book")

        for i in range(100):
            user = User(name="test_name_" + str(i))
            user.books.append(book)

        api = Api(app, api_spec_url=API_PREFIX + "/swagger", host="{}:{}".format(HOST, PORT))
        # Expose the database objects as REST API endpoints
        api.expose_object(User)
        api.expose_object(Book)
        # Set the JSON encoder used for object to json marshalling
        app.json_encoder = SAFRSJSONEncoder

        @app.route("/")
        def goto_api():
            """Create a redirect from / to /api"""
            return redirect(API_PREFIX)

        # Register the API at /api/docs
        swaggerui_blueprint = get_swaggerui_blueprint(API_PREFIX, API_PREFIX + "/swagger.json")
        app.register_blueprint(swaggerui_blueprint, url_prefix=API_PREFIX)
        print("Starting API: http://{}:{}{}".format(HOST, PORT, API_PREFIX))
        app.run(host=HOST, port=PORT)
