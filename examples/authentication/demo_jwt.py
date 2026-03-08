#!/usr/bin/env python3
from __future__ import annotations

from typing import Any, Sequence
import sys

from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
from flask_sqlalchemy import SQLAlchemy
from safrs import SAFRSAPI, SAFRSBase
from sqlalchemy import Column, String, orm

from _shared.cli import parse_host_port

db = SQLAlchemy()


def test_dec(f: Any) -> Any:
    print(f, f.__name__)
    return f


class Item(SAFRSBase, db.Model):
    """
    description: Item description
    """

    __tablename__ = "Items"
    id = Column(String, primary_key=True)
    name = Column(String, default="")
    user_id = db.Column(db.String, db.ForeignKey("Users.id"))
    user = db.relationship("User", back_populates="items")


class User(SAFRSBase, db.Model):
    """
    description: User description (With Authorization Header)
    """

    __tablename__ = "Users"
    custom_decorators = [jwt_required, test_dec]

    id = Column(String, primary_key=True)
    username = db.Column(db.String(32), index=True)
    items = db.relationship("Item", back_populates="user", lazy="dynamic")

    def __init__(self: Any, *args: Any, **kwargs: Any) -> None:
        print("xx " * 30)
        print(args, kwargs)
        super().__init__(*args, **kwargs)

    @orm.reconstructor
    def reconstruct(self: Any) -> Any:
        print(f"reconstruct {self.username}" * 3)

    @classmethod
    def filter(cls: Any, *args: Any, **kwargs: Any) -> Any:
        print(args, kwargs)
        return cls.query.filter_by(username=args[0])


def create_app(host: str = "0.0.0.0", port: int = 5000) -> Flask:
    app = Flask("demo_app")
    jwt = JWTManager(app)
    _ = jwt
    app.config.update(
        SQLALCHEMY_DATABASE_URI="sqlite:////tmp/jwt_demo.sqlite",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY=b"sdqfjqsdfqizroqnxwc",
        JWT_SECRET_KEY="ik,ncbxh",
        DEBUG=True,
    )
    db.init_app(app)

    @app.route("/login", methods=["POST"])
    def login() -> Any:
        if not request.is_json:
            return jsonify({"msg": "Missing JSON in request"}), 400

        username = request.json.get("username", None)
        password = request.json.get("password", None)
        if not username:
            return jsonify({"msg": "Missing username parameter"}), 400
        if not password:
            return jsonify({"msg": "Missing password parameter"}), 400
        if username != "test" or password != "test":
            return jsonify({"msg": "Bad username or password"}), 401

        access_token = create_access_token(identity=username)
        return jsonify(access_token=access_token), 200

    @app.teardown_appcontext
    def shutdown_session(exception: Any = None) -> Any:
        _ = exception
        db.session.remove()

    with app.app_context():
        db.create_all()
        custom_swagger = {
            "securityDefinitions": {"Bearer": {"type": "apiKey", "in": "header", "name": "Authorization"}},
            "security": [{"Bearer": []}],
        }
        api = SAFRSAPI(
            app,
            api_spec_url="/api/swagger",
            host=host,
            port=port,
            schemes=["http"],
            custom_swagger=custom_swagger,
        )
        username = "user2"
        item = Item(name="item test")
        User(username=username, items=[item])
        api.expose_object(Item)
        api.expose_object(User)

        seeded_user = User.query.filter_by(username="user2").first()
        if seeded_user is not None:
            access_token = create_access_token(identity=seeded_user.username)
            print("Test Authorization header access_token: Bearer", access_token)

    return app


def main(argv: Sequence[str] | None = None) -> None:
    host, port = parse_host_port(argv or sys.argv[1:], default_host="0.0.0.0", default_port=5000)
    app = create_app(host=host, port=port)
    print(f"Starting API: http://{host}:{port}/api")
    app.run(host=host, port=port)


if __name__ == "__main__":
    main()

