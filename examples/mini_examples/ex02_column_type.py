#!/usr/bin/env python
from typing import Any
#
# column type example: declare a column type for input validation and serialization
#
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from safrs import SAFRSBase, SafrsApi, ValidationError
from sqlalchemy.types import TypeDecorator

db = SQLAlchemy()


class EmailType(TypeDecorator):
    """
    example class to perform email validation
    DB Email Type class: validates email address when bound
    """

    impl = db.String(767)

    def __init__(self: Any, *args: Any, **kwargs: Any) -> None:
        super(*args, **kwargs)

    def process_bind_param(self: Any, value: Any, dialect: Any) -> Any:
        if "@" not in value:
            raise ValidationError(f"Email Validation Error {value}")

        return value


class User(SAFRSBase, db.Model):
    """
    description: User description
    """

    __tablename__ = "Users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    email = db.Column(EmailType)


def create_api(app: Any, HOST: Any='localhost', PORT: Any=5000, API_PREFIX: Any='') -> Any:
    api = SafrsApi(app, host=HOST, port=PORT, prefix=API_PREFIX)
    api.expose_object(User)
    user = User(name="test", email="email@x.org")
    print(f"Starting API: http://{HOST}:{PORT}/{API_PREFIX}")


def create_app(config_filename: Any=None, host: Any='localhost') -> Any:
    app = Flask("demo_app")
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://")
    db.init_app(app)
    with app.app_context():
        db.create_all()
        create_api(app, host)
    return app


host = "127.0.0.1"
app = create_app(host=host)

if __name__ == "__main__":
    app.run(host=host)
