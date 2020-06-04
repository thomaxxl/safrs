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

t@TEMP:~$ token=$(curl -X POST localhost:5000/login -d '{ "username" : "test", "password" : "test" }' \
          --header "Content-Type: application/json" | jq .access_token -r)
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
from flask import Flask, jsonify
from flask import request
from sqlalchemy import Column, String
from safrs import SAFRSBase, SAFRSAPI
from flask_sqlalchemy import SQLAlchemy
from flask_httpauth import HTTPBasicAuth
from flask_jwt_extended import (
    JWTManager,
    jwt_required,
    create_access_token
)
from sqlalchemy import orm

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
        description: User description (With Authorization Header)
    """

    __tablename__ = "Users"
    #
    # Add the jwt_required decorator to the exposed methods
    #
    custom_decorators = [jwt_required, test_dec]

    id = db.Column(String, primary_key=True)
    username = db.Column(db.String(32), index=True)
    items = db.relationship("Item", back_populates="user", lazy="dynamic")

    def __init__(self, *args, **kwargs):
        print("xx " * 30)
        print(args, kwargs)
        super().__init__(*args, **kwargs)

    @orm.reconstructor
    def reconstruct(self):
        print(f"reconstruct {self.username}" * 3)

    @classmethod
    def filter(cls, *args, **kwargs):
        print(
            args, kwargs
        )  # args[0] should contain the filter= url query parameter value
        return cls.query.filter_by(username=args[0])


def start_app(app):

    custom_swagger = {
        "securityDefinitions": {
            "Bearer": {"type": "apiKey", "in": "header", "name": "Authorization"}
        },
        "security": [{"Bearer": []}],
    }  # Customized swagger will be merged

    api = SAFRSAPI(
        app,
        api_spec_url="/api/swagger",
        host=HOST,
        port=PORT,
        schemes=["http"],
        custom_swagger=custom_swagger,
    )

    username = "user2"

    item = Item(name="item test")
    user = User(username=username, items=[item])

    api.expose_object(Item)
    api.expose_object(User)

    print("Starting API: http://{}:{}/api".format(HOST, PORT))

    # Identity can be any data that is json serializable
    user = User.query.filter_by(username="user2").first()
    access_token = create_access_token(identity=user.username)
    print("Test Authorization header access_token: Bearer", access_token)

    app.run(host=HOST, port=PORT)


#
# APP Initialization
#

app = Flask("demo_app")
jwt = JWTManager(app)
app.config.update(
    SQLALCHEMY_DATABASE_URI="sqlite:////tmp/jwt_demo.sqlite",
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

    username = request.json.get("username", None)
    password = request.json.get("password", None)
    if not username:
        return jsonify({"msg": "Missing username parameter"}), 400
    if not password:
        return jsonify({"msg": "Missing password parameter"}), 400

    if username != "test" or password != "test":
        return jsonify({"msg": "Bad username or password"}), 401

    # Identity can be any data that is json serializable
    access_token = create_access_token(identity=username)
    return jsonify(access_token=access_token), 200


@app.teardown_appcontext
def shutdown_session(exception=None):
    """cfr. http://flask.pocoo.org/docs/0.12/patterns/sqlalchemy/"""
    db.session.remove()


# Start the application
with app.app_context():
    db.create_all()
    start_app(app)
