#!/usr/bin/env python3
"""
  This demo application demonstrates the functionality of the safrs documented JSON API
  After installing safrs with pip, you can run this app standalone:
  $ python3 demo_devto.py [Listener-IP]

  This will run the example on http://Listener-Ip:5000

  - A database is created and items are added
  - A json api is available
  - swagger documentation is generated

"""
from __future__ import annotations

from typing import Any, Sequence
import sys
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from safrs import SAFRSBase, SafrsApi
from _shared.cli import parse_host

db = SQLAlchemy()


# Example sqla database object
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
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, default="")
    user_id = db.Column(db.String, db.ForeignKey("Users.id"))
    user = db.relationship("User", back_populates="books")


def create_api(app: Flask, host: str = "localhost", port: int = 5000, api_prefix: str = "") -> None:
    api = SafrsApi(app, host=host, port=port, prefix=api_prefix)
    api.expose_object(User)
    api.expose_object(Book)
    print(f"Starting API: http://{host}:{port}/{api_prefix}")


def create_app(config_filename: str | None = None, host: str = "localhost") -> Flask:
    app = Flask("demo_app")
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://")
    db.init_app(app)

    with app.app_context():
        db.create_all()
        # Populate the db with users and a books and add the book to the user.books relationship
        for i in range(200):
            user = User(name=f"user{i}", email=f"email{i}@dev.to")
            book = Book(name="test_book")
            user.books.append(book)

        create_api(app, host)
    return app


def main(argv: Sequence[str] | None = None) -> None:
    host = parse_host(argv or sys.argv[1:], default_host="127.0.0.1")
    app = create_app(host=host)
    app.run(host=host)


if __name__ == "__main__":
    main()
