#!/usr/bin/env python3

import sys
import os
import logging
from functools import wraps
from flask import Flask, redirect, jsonify, make_response
from flask import abort, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String
from safrs import SAFRSBase, SAFRSAPI, jsonapi_rpc
from flask_sqlalchemy import SQLAlchemy
from flask_httpauth import HTTPBasicAuth
from flask import request


db = SQLAlchemy()
auth = HTTPBasicAuth()

# Example sqla database object
class Item(SAFRSBase, db.Model):
    """
        description: Item description
    """

    __tablename__ = "items"
    id = Column(String, primary_key=True)
    name = Column(String, default="")


def post_login_required(func):
    def post_decorator(*args, **kwargs):
        print("post_decorator ", func, *args, **kwargs)
        return auth.login_required(func)(*args, **kwargs)

    if func.__name__ in ("post", "patch", "delete"):
        return post_decorator

    return func


class User(SAFRSBase, db.Model):
    """
        description: User description
    """

    __tablename__ = "users"
    id = db.Column(db.String(32), primary_key=True)
    username = db.Column(db.String(32))
    custom_decorators = [post_login_required]


def start_app(app):

    OAS_PREFIX = "/api"  # swagger location
    api = SAFRSAPI(app, host=HOST, schemes=["http"], prefix=OAS_PREFIX, api_spec_url=OAS_PREFIX + "/swagger")

    api.expose_object(Item)
    api.expose_object(User)

    item = Item(name="test", email="em@il")
    # user = User(username='admin')
    # user.hash_password('password')

    print("Starting API: http://{}:{}/api".format(HOST, PORT))
    app.run(host=HOST, port=PORT)


#
# APP Initialization
#

app = Flask("demo_app")
app.config.update(
    SQLALCHEMY_DATABASE_URI="sqlite:////tmp/test.sqlite", SQLALCHEMY_TRACK_MODIFICATIONS=False, SECRET_KEY=b"changeme", DEBUG=True
)
HOST = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
PORT = 5000
db.init_app(app)


#
# Authentication and custom routes
#
@auth.verify_password
def verify_password(username_or_token, password):

    if username_or_token == "user" and password == "passwd":
        return True

    return False


# Start the application
with app.app_context():
    db.create_all()
    start_app(app)
