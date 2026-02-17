#!/usr/bin/env python
from typing import Any
#
# `jsonapi_attr` example
#
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from safrs import SAFRSBase, SafrsApi, jsonapi_attr

db = SQLAlchemy()


class User(SAFRSBase, db.Model):
    """
    description: User description
    """

    __tablename__ = "Users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    email = db.Column(db.String)

    @jsonapi_attr
    def some_attr(self: Any) -> Any:
        return "some_value"

    @some_attr.setter
    def some_attr(self: Any, val: Any) -> Any:
        print("some_attr setter value:", val)


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


@app.before_request
def req_start() -> Any:
    print("start")


@app.before_request
def req_end() -> Any:
    print("end")


if __name__ == "__main__":
    app.run(host=host)
