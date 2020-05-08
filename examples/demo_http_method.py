#!/usr/bin/env python
#
# Demonstrate:
#   - override http method
#   - validate jsonapi
#
import sys, pprint
from flask import Flask, redirect, g
from flask_sqlalchemy import SQLAlchemy
from safrs import SAFRSBase, SAFRSAPI, jsonapi_rpc
import json
from jsonschema import validate

db = SQLAlchemy()

# Example sqla database object
class User(SAFRSBase, db.Model):
    """
        description: User description
    """

    __tablename__ = "users"
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, default="")
    email = db.Column(db.String, default="")

    # Following method is exposed through the REST API
    # This means it can be invoked with the argument http_methods
    @jsonapi_rpc(http_methods=["POST", "GET"])
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

    def get(self, *args, **kwargs):
        """
            description: Get something
            summary : User get summary
            responses :
                429 :
                    description : Too many requests
        """
        return self.http_methods["get"](self, *args, **kwargs)


# Server configuration variables:
HOST = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
PORT = 5000
API_PREFIX = ""

# App initialization
app = Flask("SAFRS Demo Application")
app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", DEBUG=True)
db.init_app(app)
# Create the database

with app.app_context():
    db.create_all()
    # Create a user
    api = SAFRSAPI(app, host=HOST, port=PORT, prefix=API_PREFIX)
    # Create a user, data from this user will be used to fill the swagger example
    user = User(name="thomas", email="em@il")
    # Expose the database objects as REST API endpoints
    api.expose_object(User)

with open("examples/jsonapi-schema.json") as sf:
    schema = json.load(sf)


@app.after_request
def per_request_callbacks(response):
    if response.headers["Content-Type"] != "application/json":
        return response
    try:
        data = json.loads(response.data.decode("utf8"))
        validate(data, schema)
        data["meta"] = data.get("meta", {})
        data["meta"]["validation"] = "ok"
        response.data = json.dumps(data, indent=4)
    except Exception as exc:
        print(exc)
        response.data = b'{"result" : "validation failed"}'

    for func in getattr(g, "call_after_request", ()):
        response = func(response)
    return response


print("Starting API: http://{}:{}{}".format(HOST, PORT, API_PREFIX))
app.run(host=HOST, port=PORT)
