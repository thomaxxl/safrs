#!/usr/bin/env python3
from __future__ import annotations

from typing import Any, Sequence
import sys

from flask import Flask
from flask_httpauth import HTTPBasicAuth
from flask_sqlalchemy import SQLAlchemy
from safrs import SAFRSAPI, SAFRSBase
from sqlalchemy import Column, String

from _shared.cli import parse_host_port

db = SQLAlchemy()
auth = HTTPBasicAuth()


class Item(SAFRSBase, db.Model):
    """
    description: Item description
    """

    __tablename__ = "items"
    id = Column(String, primary_key=True)
    name = Column(String, default="")


def post_login_required(func: Any) -> Any:
    def post_decorator(*args: Any, **kwargs: Any) -> Any:
        print("post_decorator ", func, *args, **kwargs)
        return auth.login_required(func)(*args, **kwargs)

    if func.__name__ in ("post", "patch", "delete"):
        return post_decorator
    return func


class User(SAFRSBase, db.Model):
    """
    description: User description
    """

    __tablename__ = "users"
    id = db.Column(db.String(32), primary_key=True)
    username = db.Column(db.String(32))
    custom_decorators = [post_login_required]


@auth.verify_password
def verify_password(username_or_token: Any, password: Any) -> Any:
    if username_or_token == "user" and password == "passwd":
        return True
    return False


def create_app(host: str = "0.0.0.0", port: int = 5000) -> Flask:
    app = Flask("demo_app")
    app.config.update(
        SQLALCHEMY_DATABASE_URI="sqlite:////tmp/test.sqlite",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY=b"changeme",
        DEBUG=True,
    )
    db.init_app(app)

    with app.app_context():
        db.create_all()
        api_prefix = "/api"
        api = SAFRSAPI(app, host=host, schemes=["http"], prefix=api_prefix, api_spec_url=api_prefix + "/swagger")
        api.expose_object(Item)
        api.expose_object(User)
        Item(name="test")

    return app


def main(argv: Sequence[str] | None = None) -> None:
    host, port = parse_host_port(argv or sys.argv[1:], default_host="0.0.0.0", default_port=5000)
    app = create_app(host=host, port=port)
    print(f"Starting API: http://{host}:{port}/api")
    app.run(host=host, port=port)


if __name__ == "__main__":
    main()
