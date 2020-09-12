#!/usr/bin/env python3
#
# This application demonstrates how access control can be implemented for
# flask-restful API endpoints
# see also https://flask-restful.readthedocs.io/en/latest/extending.html#resource-method-decorators
#
import sys
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from safrs import SAFRSBase, SAFRSAPI, jsonapi_rpc
from flask_sqlalchemy import SQLAlchemy
from flask_httpauth import HTTPBasicAuth

db = SQLAlchemy()

# Authentication with flask-httpauth
# https://flask-httpauth.readthedocs.io/en/latest/
auth = HTTPBasicAuth()


@auth.verify_password
def verify_password(username_or_token, password):
    # Implement your authentication here
    if username_or_token == "user" and password == "pass":
        return True

    return False


class User(SAFRSBase, db.Model):
    """
        description: Protected user resource
    """

    __tablename__ = "users"
    id = db.Column(db.String(32), primary_key=True)
    username = db.Column(db.String(32))
    

def start_app(app):

    api = SAFRSAPI(app, host=HOST)
    # The method_decorators will be applied to all API endpoints
    api.expose_object(User, method_decorators = [auth.login_required])
    user = User(username="admin2")
    print("Starting API: http://{}:{}/api".format(HOST, PORT))
    app.run(host=HOST, port=PORT)


#
# APP Initialization
#

app = Flask("demo_app")
app.config.update(
    SQLALCHEMY_DATABASE_URI="sqlite:////tmp/demo.sqlite",
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SECRET_KEY=b"sdqfjqsdfqizroqnxwc",
    DEBUG=True,
)

HOST = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
PORT = 5000
db.init_app(app)


# Start the application
with app.app_context():
    db.create_all()
    start_app(app)
