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
from __future__ import annotations

from typing import Any, Sequence
import sys
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy
from safrs import SAFRSBase, SafrsApi
from _shared.cli import parse_host

db = SQLAlchemy()

# Example sqla database objects
class User(SAFRSBase, db.Model):
    """
    description: User description
    """

    __tablename__ = "Users"
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, default="")
    email = db.Column(db.String, default="")
    books = db.relationship("Book", back_populates="user", lazy="dynamic")


class Book(SAFRSBase, db.Model):
    """
    description: Book description
    """

    __tablename__ = "Books"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, default="")
    user_id = db.Column(db.String, db.ForeignKey("Users.id"))
    user = db.relationship("User", back_populates="books")


# Create the api endpoints
def create_api(app: Flask, host: str = "localhost", port: int = 5000, api_prefix: str = "") -> None:
    api = SafrsApi(app, host=host, port=port, prefix=api_prefix)
    api.expose_object(User)
    api.expose_object(Book)
    print(f"Created API: http://{host}:{port}/{api_prefix}")


def create_app(config_filename: str | None = None, host: str = "localhost") -> Flask:
    app = Flask("demo_app")
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://")
    db.init_app(app)

    with app.app_context():
        db.create_all()
        create_api(app, host)
        # Populate the db with users and a books and add the book to the user.books relationship
        for i in range(200):
            user = User(name=f"user{i}", email=f"email{i}@email.com")
            book = Book(name=f"test book {i}")
            user.books.append(book)
            
    return app


def main(argv: Sequence[str] | None = None) -> None:
    host = parse_host(argv or sys.argv[1:], default_host="127.0.0.1")
    app = create_app(host=host)
    app.run(host=host)


if __name__ == "__main__":
    main()
