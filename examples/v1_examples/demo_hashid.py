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
from sqlalchemy import Column, String
from safrs.db import SAFRSBase, documented_api_method, SAFRSSHA256HashID
from safrs.jsonapi import SAFRSRestAPI, SAFRSJSONEncoder, Api
from flask_swagger_ui import get_swaggerui_blueprint


app = Flask("demo_app")
app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", DEBUG=True)
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
    id_type = SAFRSSHA256HashID

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


HOST = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
PORT = 5000


# Create the database
db.create_all()

with app.app_context():
    # Create a user
    user = User(name="test", email="em@il")

    api = Api(app, api_spec_url="/api/swagger", host="{}:{}".format(HOST, PORT), schemes=["http"])
    # Expose the User object
    api.expose_object(User)
    # Set the JSON encoder used for object to json marshalling
    app.json_encoder = SAFRSJSONEncoder
    # Register the API at /api/docs
    swaggerui_blueprint = get_swaggerui_blueprint("/api", "/api/swagger.json")
    app.register_blueprint(swaggerui_blueprint, url_prefix="/api")

    @app.route("/")
    def goto_api():
        return redirect("/api")

    print("Starting API: http://{}:{}/api".format(HOST, PORT))
    # app.run(host=HOST, port = PORT)
