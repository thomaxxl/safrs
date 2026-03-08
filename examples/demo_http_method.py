#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Sequence

from flask import Flask, g
from flask_sqlalchemy import SQLAlchemy
from jsonschema import validate
from safrs import SAFRSBase, SafrsApi, jsonapi_rpc

from _shared.cli import parse_host_port

db = SQLAlchemy()


class User(SAFRSBase, db.Model):
    """
    description: User description
    """

    __tablename__ = "users"
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, default="")
    email = db.Column(db.String, default="")

    @jsonapi_rpc(http_methods=["POST", "GET"])
    def send_mail(self: Any, email: Any) -> Any:
        """
        description : Send an email
        args:
            email:
                type : string
                example : test email
        """
        content = f"Mail to {self.name} : {email}\n"
        with open("/tmp/mail.txt", "a+", encoding="utf-8") as mailfile:
            mailfile.write(content)
        return {"result": f"sent {content}"}

    def get(self: Any, *args: Any, **kwargs: Any) -> Any:
        """
        description: Get something
        summary : User get summary
        responses :
            429 :
                description : Too many requests
        """
        return self.http_methods["get"](self, *args, **kwargs)


def _load_jsonapi_schema() -> dict[str, Any]:
    candidate_paths = (
        Path(__file__).with_name("jsonapi-schema.json"),
        Path(__file__).resolve().parents[1] / "tests" / "jsonapi-schema.json",
    )
    for schema_path in candidate_paths:
        if schema_path.exists():
            return json.loads(schema_path.read_text(encoding="utf-8"))
    return {}


def create_app(host: str = "0.0.0.0", port: int = 5000, api_prefix: str = "") -> Flask:
    app = Flask("SAFRS Demo Application")
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", DEBUG=True, SQLALCHEMY_TRACK_MODIFICATIONS=False)
    db.init_app(app)
    schema = _load_jsonapi_schema()

    with app.app_context():
        db.create_all()
        api = SafrsApi(app, host=host, port=port, prefix=api_prefix)
        User(name="thomas", email="em@il")
        api.expose_object(User)

    @app.after_request
    def per_request_callbacks(response: Any) -> Any:
        if response.headers.get("Content-Type") != "application/json":
            return response
        try:
            data = json.loads(response.data.decode("utf8"))
            if schema:
                validate(data, schema)
                data["meta"] = data.get("meta", {})
                data["meta"]["validation"] = "ok"
                response.data = json.dumps(data, indent=4).encode("utf-8")
        except Exception as exc:
            print(exc)
            response.data = b'{"result" : "validation failed"}'

        for func in getattr(g, "call_after_request", ()):
            response = func(response)
        return response

    return app


def main(argv: Sequence[str] | None = None) -> None:
    host, port = parse_host_port(argv or sys.argv[1:], default_host="0.0.0.0", default_port=5000)
    app = create_app(host=host, port=port)
    print(f"Starting API: http://{host}:{port}")
    app.run(host=host, port=port)


if __name__ == "__main__":
    main()

