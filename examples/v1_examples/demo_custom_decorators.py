#!/usr/bin/env python
#
# This is a demo application to demonstrate the functionality custom decorators
#
import sys
import os
import logging
import builtins
from functools import wraps
from flask import Flask, redirect, jsonify, make_response
from flask import abort, request, g, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String
from safrs import SAFRSBase, SAFRSJSONEncoder, Api, jsonapi_rpc
from flask_swagger_ui import get_swaggerui_blueprint
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def test_decorator(fun):
    print("Wrapping:", fun.SAFRSObject.__name__, fun.__name__, fun)

    @wraps(fun)
    def wrapped_fun(*args, **kwargs):
        print("IN HERE:", fun.SAFRSObject.__name__, fun.__name__)
        print("Args:", kwargs)
        result = fun(*args, **kwargs)
        print("Result:", result)
        return result

    return wrapped_fun


class Item(SAFRSBase, db.Model):
    """
        description: Item description
    """

    __tablename__ = "Items"
    custom_decorators = [test_decorator]
    id = Column(String, primary_key=True)
    name = Column(String, default="")
    user_id = db.Column(db.String, db.ForeignKey("Users.id"))
    user = db.relationship("User", back_populates="items_rel")


class User(SAFRSBase, db.Model):
    """
        description: User description (With test_decorator)
    """

    __tablename__ = "Users"
    #
    # Add the test_decorator decorator to the exposed methods
    #
    custom_decorators = [test_decorator]

    id = db.Column(String, primary_key=True)
    username = db.Column(db.String(32), index=True)
    items_rel = db.relationship("Item", back_populates="user", lazy="dynamic")


def start_app(app):

    api = Api(app, api_spec_url="/api/swagger", host="{}:{}".format(HOST, PORT), schemes=["http"])

    item = Item(name="test", email="em@il")
    user = User(username="admin")

    api.expose_object(Item)
    api.expose_object(User)

    # Set the JSON encoder used for object to json marshalling
    app.json_encoder = SAFRSJSONEncoder
    # Register the API at /api/docs
    swaggerui_blueprint = get_swaggerui_blueprint("/api", "/api/swagger.json")
    app.register_blueprint(swaggerui_blueprint, url_prefix="/api")

    print("Starting API: http://{}:{}/api".format(HOST, PORT))
    app.run(host=HOST, port=PORT)


#
# APP Initialization
#

app = Flask("demo_app")
app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", SQLALCHEMY_TRACK_MODIFICATIONS=False, DEBUG=True)
HOST = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
PORT = 5000
db.init_app(app)


@app.route("/")
def goto_api():
    return redirect("/api")


@app.teardown_appcontext
def shutdown_session(exception=None):
    """cfr. http://flask.pocoo.org/docs/0.12/patterns/sqlalchemy/"""
    db.session.remove()


# Start the application
with app.app_context():
    db.create_all()
    start_app(app)
