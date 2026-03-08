#!/usr/bin/env python3
from __future__ import annotations

from typing import Any, Sequence
import sys

from flask import Flask
from flask_httpauth import HTTPBasicAuth
from flask_sqlalchemy import SQLAlchemy
from safrs import SAFRSAPI, SAFRSBase

from _shared.cli import parse_host_port

db = SQLAlchemy()
auth = HTTPBasicAuth()


@auth.verify_password
def verify_password(username_or_token: Any, password: Any) -> Any:
    if username_or_token == "user" and password == "pass":
        return True
    return False


class User(SAFRSBase, db.Model):
    """
    description: Protected user resource
    """

    __tablename__ = "users"
    id = db.Column(db.String(32), primary_key=True)
    username = db.Column(db.String(32))


def create_app(host: str = "0.0.0.0", port: int = 5000) -> Flask:
    app = Flask("demo_app")
    app.config.update(
        SQLALCHEMY_DATABASE_URI="sqlite:////tmp/demo2.sqlite",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY=b"sdqfjqsdfqizroqnxwc",
        DEBUG=True,
    )
    db.init_app(app)

    with app.app_context():
        db.create_all()
        api = SAFRSAPI(app, host=host, port=port)
        api.expose_object(User, method_decorators=[auth.login_required])
        User(username="admin2")

    return app


def main(argv: Sequence[str] | None = None) -> None:
    host, port = parse_host_port(argv or sys.argv[1:], default_host="0.0.0.0", default_port=5000)
    app = create_app(host=host, port=port)
    print(f"Starting API: http://{host}:{port}/api")
    app.run(host=host, port=port)


if __name__ == "__main__":
    main()

