#!/usr/bin/env python
#
# This is a demo application to demonstrate the functionality of the safrs_rest REST API
#
# It can be ran standalone like this:
# python demo.py [Listener-IP]
#
# This will run the example on http://Listener-Ip:5000
#
# - A database is created and a user is added
# - A rest api is available
# - swagger2 documentation is generated
#
import sys

from flask import Flask, redirect
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String
from safrs.db import SAFRSBase, documented_api_method
from safrs.jsonapi import SAFRSRestAPI, SAFRSJSONEncoder, Api
from flask_swagger_ui import get_swaggerui_blueprint
from flask_marshmallow import Marshmallow
from safrs.safrs_types import JSONType


app = Flask("demo_app")
app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", SQLALCHEMY_TRACK_MODIFICATIONS=False, DEBUG=True)
db = SQLAlchemy(app)

# Example sqla database object
class User(SAFRSBase, db.Model):
    """
        description: User description
    """

    __tablename__ = "users"
    id = Column(String, primary_key=True)
    name = Column(String, default="")
    email = Column(String, default="")
    json = Column(JSONType, default={})

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


def create_api(app):

    api = Api(app, api_spec_url="/api/swagger", host="{}:{}".format(HOST, PORT), schemes=["http"])
    # Expose the User object
    api.expose_object(User)
    user = User(name="test", email="em@il", json={"test": "data"})

    # Set the JSON encoder used for object to json marshalling
    app.json_encoder = SAFRSJSONEncoder
    # Register the API at /api/docs
    swaggerui_blueprint = get_swaggerui_blueprint("/api", "/api/swagger.json")
    app.register_blueprint(swaggerui_blueprint, url_prefix="/api")

    print("Starting API: http://{}:{}/api".format(HOST, PORT))
    app.run(host=HOST, port=PORT)


@app.route("/")
def goto_api():
    return redirect("/api")


@app.teardown_appcontext
def shutdown_session(exception=None):
    """cfr. http://flask.pocoo.org/docs/0.12/patterns/sqlalchemy/"""
    db.session.remove()


# Start the application
HOST = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
PORT = 5000

db.init_app(app)
# Create the database
db.create_all()
# bind marshmallow
ma = Marshmallow(app)
ma.init_app(app)

with app.app_context():
    create_api(app)
