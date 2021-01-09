"""
  This demo application demonstrates the functionality of the safrs documented JSON APIs with Flask-Rest-JSONAPI library.
  After installing safrs and flask-rest-jsonapi with pip, you can run this app standalone:
  $ python3 demo_flaskrestjsonapi.py [Listener-IP]
  This will run the example on http://Listener-Ip:5010
  - A database is created and items are added
  - A Flask-rest-json api is available
  - swagger documentation is generated
"""


from flask import Flask
from safrs import SAFRSBase, SAFRSAPI
from flask_rest_jsonapi import Api, ResourceDetail, ResourceList, ResourceRelationship
from flask_rest_jsonapi.exceptions import ObjectNotFound
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm.exc import NoResultFound
from marshmallow_jsonapi.flask import Schema, Relationship
from marshmallow_jsonapi import fields

db = SQLAlchemy()


# Create data storage
class Person(db.Model, SAFRSBase):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    email = db.Column(db.String)
    birth_date = db.Column(db.Date)
    password = db.Column(db.String)


class Computer(db.Model, SAFRSBase):
    id = db.Column(db.Integer, primary_key=True)
    serial = db.Column(db.String)
    person_id = db.Column(db.Integer, db.ForeignKey("person.id"))
    person = db.relationship("Person", backref=db.backref("computers"))


# Create logical data abstraction (same as data storage for this first example)
class PersonSchema(Schema):
    class Meta:
        type_ = "person"
        self_view = "person_detail"
        self_view_kwargs = {"id": "<id>"}
        self_view_many = "person_list"

    id = fields.Integer(as_string=True, dump_only=True)
    name = fields.Str(required=True, load_only=True)
    email = fields.Email(load_only=True)
    birth_date = fields.Date()
    display_name = fields.Function(
        lambda obj: "{} <{}>".format(obj.name.upper(), obj.email)
    )
    computers = Relationship(
        self_view="person_computers",
        self_view_kwargs={"id": "<id>"},
        related_view="computer_list",
        related_view_kwargs={"id": "<id>"},
        many=True,
        schema="ComputerSchema",
        type_="computer",
    )


class ComputerSchema(Schema):
    class Meta:
        type_ = "computer"
        self_view = "computer_detail"
        self_view_kwargs = {"id": "<id>"}

    id = fields.Integer(as_string=True, dump_only=True)
    serial = fields.Str(required=True)
    owner = Relationship(
        attribute="person",
        self_view="computer_person",
        self_view_kwargs={"id": "<id>"},
        related_view="person_detail",
        related_view_kwargs={"id": "<id>"},
        schema="PersonSchema",
        type_="person",
    )


# Create resource managers
class PersonList(ResourceList):
    schema = PersonSchema
    data_layer = {"session": db.session, "model": Person}


class PersonDetail(ResourceDetail):

    schema = PersonSchema
    data_layer = {
        "session": db.session,
        "model": Person,
    }


class PersonRelationship(ResourceRelationship):
    schema = PersonSchema
    data_layer = {"session": db.session, "model": Person}


class ComputerList(ResourceList):

    schema = ComputerSchema
    data_layer = {
        "session": db.session,
        "model": Computer,
    }


class ComputerDetail(ResourceDetail):
    schema = ComputerSchema
    data_layer = {"session": db.session, "model": Computer}


class ComputerRelationship(ResourceRelationship):
    schema = ComputerSchema
    data_layer = {"session": db.session, "model": Computer}


# Create endpoints


def create_api(app, HOST="localhost", PORT=5010, API_PREFIX=""):
    api = SAFRSAPI(app, host=HOST, port=PORT, prefix=API_PREFIX)
    api.expose_object(Person)
    api.expose_object(Computer)
    print("Starting API: http://{}:{}/{}".format(HOST, PORT, API_PREFIX))


def create_app(config_filename=None, host="localhost"):
    app = Flask(__name__)
    # app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://")
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///test.db"
    db.init_app(app)
    api = Api(app)
    api.route(PersonList, "person_list", "/persons")
    api.route(
        PersonDetail, "person_detail", "/persons/<int:id>", "/computers/<int:id>/owner"
    )
    api.route(
        PersonRelationship,
        "person_computers",
        "/persons/<int:id>/relationships/computers",
    )
    api.route(
        ComputerList,
        "computer_list",
        "/computers",
        "/persons/<int:person_id>/computers",
    )
    api.route(ComputerDetail, "computer_detail", "/computers/<int:id>")
    api.route(
        ComputerRelationship,
        "computer_person",
        "/computers/<int:id>/relationships/owner",
    )
    with app.app_context():
        db.create_all()
        create_api(app, host)
        return app


app = create_app(host="localhost")


if __name__ == "__main__":
    # Start application
    app.run(port=5010)
