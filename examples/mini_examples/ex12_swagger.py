#!/usr/bin/env python3
"""
Some of the OAS/swagger can be customized by editing the docstrings. The swagger can also be customized by loading
an external specification. This example shows how to modify swagger doc by loading an external json.

1) Create the swagger.json, for ex:
curl http://localhost:5000/swagger.json > examples/mini_examples/custom_swagger.json

2) Load and merge the swagger using the `custom_swagger` argument to SAFRSAPI

run: python ex12_swagger.py

"""
import sys
import json
from pathlib import Path
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from safrs import SAFRSBase, SAFRSAPI

db = SQLAlchemy()


# Example sqla database objects
class User(SAFRSBase, db.Model):
    """
        description: My User description
    """

    __tablename__ = "Users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, default="")
    email = db.Column(db.String, default="")
    books = db.relationship("Book", back_populates="user", lazy="dynamic")


class Book(SAFRSBase, db.Model):
    """
        description: My Book description
    """

    __tablename__ = "Books"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, default="")
    user_id = db.Column(db.String, db.ForeignKey("Users.id"))
    user = db.relationship("User", back_populates="books")

def create_api(app, host="localhost", port=5000, api_prefix="", custom_swagger={}):
    """
        The custom_swagger dictionary will be merged
    """
    api = SAFRSAPI(app, host=host, port=port, prefix=api_prefix, custom_swagger=custom_swagger)
    api.expose_object(User)
    api.expose_object(Book)
    print("Created API: http://{}:{}/{}".format(host, port, api_prefix))

def create_app(config_filename=None, host="localhost"):
    app = Flask("demo_app")
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://")
    db.init_app(app)

    with open(Path(__file__).parent / "custom_swagger.json") as j_fp:
        custom_swagger = json.load(j_fp)
    
    with app.app_context():
        db.create_all()
        # Populate the db with users and a books and add the book to the user.books relationship
        for i in range(4):
            user = User(name=f"user{i}", email=f"email{i}@email.com")
            book = Book(name=f"test book {i}")
            user.books.append(book)

        create_api(app, host, custom_swagger=custom_swagger)
    
    return app

# address where the api will be hosted, change this if you're not running the app on localhost!
host = sys.argv[1] if sys.argv[1:] else "127.0.0.1"
app = create_app(host=host)


if __name__ == "__main__":
    app.run(host=host)
