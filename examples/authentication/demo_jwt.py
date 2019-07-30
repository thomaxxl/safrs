#!/usr/bin/env python
#
# This is a demo application to demonstrate the functionality of the safrs_rest REST API with JWT auth
#
# It can be ran standalone like this:
# python demo.py [Listener-IP]
#
# This will run the example on http://Listener-Ip:5000
#
# - A database is created and a item is added
# - A rest api is available
# - swagger2 documentation is generated
#
"""
Example invocation: 

t@TEMP:~$ token=$(curl -X POST localhost:5000/login -d '{ "username" : "test", "password" : "test" }' --header "Content-Type: application/json" | jq .access_token -r)
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100   344  100   300  100    44  19197   2815 --:--:-- --:--:-- --:--:-- 18750
t@TEMP:~$ curl localhost:5000/users/ -H "Authorization: Bearer $token"
{
  "data": [
    {
      "attributes": {
        "password_hash": null,
        "username": "admin"
      },
      "id": "ac608ebb-1b67-48d3-a9a0-1fba75a78227",
      "relationships": {},
      "type": "users"
    }
  ],
  "jsonapi": {
    "version": "1.0"
  },
  "links": {
    "self": "http://localhost:5000/users/?page[offset]=0&page[limit]=250"
  },
  "meta": {
    "count": 1,
    "limit": 250
  }
}
"""
import sys
import os
import logging
import builtins
from functools import wraps
from flask import Flask, redirect, jsonify, make_response
from flask import abort, request, g, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String
from safrs import SAFRSBase, SAFRS, Api, jsonapi_rpc
from flask_sqlalchemy import SQLAlchemy
from flask_httpauth import HTTPBasicAuth
from passlib.apps import custom_app_context as pwd_context
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer, BadSignature, SignatureExpired
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity

db = SQLAlchemy()
auth = HTTPBasicAuth()


def test_dec(f):
    print(f, f.__name__)
    return f


class Item(SAFRSBase, db.Model):
    """
        description: Item description
    """

    __tablename__ = "Items"
    id = Column(String, primary_key=True)
    name = Column(String, default="")
    user_id = db.Column(db.String, db.ForeignKey("Users.id"))
    user = db.relationship("User", back_populates="items")


class User(SAFRSBase, db.Model):
    """
        description: User description (With JWT Authentication)
    """

    __tablename__ = "Users"
    #
    # Add the jwt_required decorator to the exposed methods
    #
    custom_decorators = [jwt_required, test_dec]

    id = db.Column(String, primary_key=True)
    username = db.Column(db.String(32), index=True)
    items = db.relationship("Item", back_populates="user", lazy="dynamic")


def start_app(app):

    SAFRS(app)
    api = Api(app, api_spec_url="/api/swagger", host="{}:{}".format(HOST, PORT), schemes=["http"])

    username = "admin"

    item = Item(name="test", email="em@il")
    user = User(username=username)

    api.expose_object(Item)
    api.expose_object(User)

    print("Starting API: http://{}:{}/api".format(HOST, PORT))

    # Identity can be any data that is json serializable
    access_token = create_access_token(identity=username)
    print("Test Authorization header access_token: Bearer", access_token)
    api._swagger_object["securityDefinitions"] = {"Bearer": {"type": "apiKey", "name": "Authorization", "in": "header"}}

    app.run(host=HOST, port=PORT)


#
# APP Initialization
#

app = Flask("demo_app")
jwt = JWTManager(app)
app.config.update(
    SQLALCHEMY_DATABASE_URI="sqlite://",
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SECRET_KEY=b"sdqfjqsdfqizroqnxwc",
    JWT_SECRET_KEY="ik,ncbxh",
    DEBUG=True,
)
HOST = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
PORT = 5000
db.init_app(app)


@app.route("/login", methods=["POST"])
def login():
    if not request.is_json:
        return jsonify({"msg": "Missing JSON in request"}), 400

    # Identity can be any data that is json serializable
    access_token = create_access_token(identity=username)

    username = request.json.get("username", None)
    password = request.json.get("password", None)
    if not username:
        return jsonify({"msg": "Missing username parameter"}), 400
    if not password:
        return jsonify({"msg": "Missing password parameter"}), 400

    if username != "test" or password != "test":
        return jsonify({"msg": "Bad username or password"}), 401

    return jsonify(access_token=access_token), 200


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
