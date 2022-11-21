#!/usr/bin/env python3
"""
  This demo application demonstrates the functionality of the safrs documented REST API
  When safrs is installed, you can run this app:
  $ python3 demo_relationship.py [Listener-IP]

  This will run the example on http://Listener-Ip:5000

  - An sqlite database is created and populated
  - A jsonapi rest API is created
  - Swagger documentation is generated

"""
import sys
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from safrs import SAFRSBase, SAFRSAPI

db = SQLAlchemy()


# Example sqla database objects
class User(SAFRSBase, db.Model):
    """
    description: User description
    """
    allow_client_generated_ids = True
    db_commit = False
    __tablename__ = "Users"
    name = db.Column(db.String, default="", primary_key=True)
    email = db.Column(db.String, default="")
    books = db.relationship("Book", back_populates="user", lazy="dynamic")


class Book(SAFRSBase, db.Model):
    """
    description: Book description
    """

    __tablename__ = "Books"
    name = db.Column(db.String, primary_key=True)
    user_name = db.Column(db.String, db.ForeignKey("Users.name"))
    user = db.relationship("User", back_populates="books")


# create the api endpoints
def create_api(app, host="127.0.0.1", port=5000, api_prefix=""):
    api = SAFRSAPI(app, host=host, port=port, prefix=api_prefix)
    api.expose_object(User)
    api.expose_object(Book)
    print(f"Created API: http://{host}:{port}/{api_prefix}")


def create_app(host="localhost"):
    app = Flask("demo_app")
    app.config.update(SQLALCHEMY_DATABASE_URI=f"sqlite:///demo.db")
    db.init_app(app)

    with app.app_context():
        db.drop_all()
        db.create_all()
        # Populate the db with users and a books and add the book to the user.books relationship
        for i in range(200):
            user = User(name=f"user{i}", email=f"email{i}@email.com")
            book = Book(name=f"test book {i}")
            user.books.append(book)

        create_api(app, host)

    return app


# address where the api will be hosted, change this if you're not running the app on localhost!
host = sys.argv[1] if sys.argv[1:] else "127.0.0.1"
app = create_app(host=host)

if __name__ == "__main__":
    app.run(host=host)
