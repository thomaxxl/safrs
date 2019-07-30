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
import sys, datetime
from flask import Flask, redirect
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, DateTime, func
from safrs import SAFRSBase, jsonapi_rpc, SAFRS, Api, SAFRSJSONEncoder
from flask_swagger_ui import get_swaggerui_blueprint

db = SQLAlchemy()

# Example sqla database object
class User(SAFRSBase, db.Model):
    """
        description: User description
    """

    __tablename__ = "users"
    id = Column(String, primary_key=True)
    name = Column(String, default="")
    email = Column(String, default="")


class Category(SAFRSBase, db.Model):
    __tablename__ = "category"

    id = Column(Integer, primary_key=True)
    name = Column(String(250), nullable=False)
    user_id = Column(Integer, db.ForeignKey("users.id"))
    user = db.relationship(User)


class Item(SAFRSBase, db.Model):
    __tablename__ = "item"

    title = Column(String(80), nullable=False)
    id = Column(Integer, primary_key=True)
    description = Column(String(250))
    category_id = Column(Integer, db.ForeignKey("category.id"))
    category = db.relationship(Category)
    user_id = Column(Integer, db.ForeignKey("users.id"))
    user = db.relationship(User)
    last_updated = Column(DateTime, default=datetime.datetime.now())
    create_date = Column(DateTime, default=datetime.datetime.now())


def create_api(app):
    API_PREFIX = ""
    api = Api(app, api_spec_url=API_PREFIX + "/swagger", host="{}:{}".format(HOST, PORT))
    # Expose the User object
    app.json_encoder = SAFRSJSONEncoder
    swaggerui_blueprint = get_swaggerui_blueprint(API_PREFIX, API_PREFIX + "/swagger.json")
    app.register_blueprint(swaggerui_blueprint, url_prefix=API_PREFIX)

    api.expose_object(User)
    api.expose_object(Item)
    api.expose_object(Category)
    user = User(name="test", email="em@il")

    print("Starting API: http://{}:{}".format(HOST, PORT))


if __name__ == "__main__":
    app = Flask("demo_app")
    db.init_app(app)

    # SAFRS(app, db, swaggerui_blueprint= swaggerui_blueprint)
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", DEBUG=True)

    # Start the application
    HOST = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
    PORT = 5500

    db.init_app(app)
    # Create the database

    with app.app_context():
        db.create_all()
        create_api(app)
        app.run(host=HOST, port=PORT)
