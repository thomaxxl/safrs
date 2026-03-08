#!/usr/bin/env python3
from __future__ import annotations

import sys
from typing import Sequence
import logging
import builtins
from flask import Flask, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_swagger_ui import get_swaggerui_blueprint
from flask_cors import CORS
from safrs import SAFRSBase, SafrsApi, jsonapi_rpc
from _shared.cli import parse_host_port

db = SQLAlchemy()

# Example sqla database object
class User(SAFRSBase, db.Model):
    """
    description: User description
    """

    __tablename__ = "Users"
    http_methods = ["get"]
    exclude_rels = ["books"]
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


def create_app(host: str = "0.0.0.0", port: int = 5000) -> Flask:
    app = Flask("SAFRS Demo Application")
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", DEBUG=True, SQLALCHEMY_TRACK_MODIFICATIONS=False)
    db.init_app(app)
    db.app = app
    api_prefix = ""

    with app.app_context():
        # Create the database
        db.create_all()
        api = SafrsApi(app, host=host, port=port, prefix=api_prefix)
        # Create a user and a book and add the book to the user.books relationship
        user = User(name="thomas", email="em@il")
        book = Book(name="test_book")
        user.books.append(book)
        # Expose the database objects as REST API endpoints
        api.expose_object(User)
        api.expose_object(Book)
        # Register the API at /api/docs
        print(f"Starting API: http://{host}:{port}{api_prefix}")
    return app


def main(argv: Sequence[str] | None = None) -> None:
    host, port = parse_host_port(argv or sys.argv[1:], default_host="0.0.0.0", default_port=5000)
    app = create_app(host=host, port=port)
    app.run(host=host, port=port)


if __name__ == "__main__":
    main()
