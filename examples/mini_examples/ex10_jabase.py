#!/usr/bin/env python3
#
# This example shows how you can implement a SAFRS endpoint without a SQLAlchemy model
#
# Jsonapi serialization relies heavily on the idea that backend objects represent
# collections and relationships.
#
#
import sys
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from safrs import SafrsApi, jsonapi_rpc
from safrs import JABase

db = SQLAlchemy()


class MyService(JABase):
    """
    description: Example class without SQLa Model
    """

    @staticmethod
    @jsonapi_rpc(http_methods=["POST"], valid_jsonapi=False)
    def rpc(*args, a0=0, a1=1):
        """
        description: rpc example
        args:
            a0 : 0
            a1 : 1
        """

        return {"a0": a0, "a1": a1}


HOST = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
PORT = 5000
app = Flask("SAFRS Demo Application")
app.config.update(SQLALCHEMY_DATABASE_URI="sqlite:///", DEBUG=True)


if __name__ == "__main__":
    db.init_app(app)
    db.app = app
    API_PREFIX = ""

    with app.app_context():
        api = SafrsApi(app, host=f"{HOST}", port=PORT, prefix=API_PREFIX)
        # Expose the database objects as REST API endpoints
        api.expose_object(MyService)
        # Register the API at /api/docs
        print(f"Starting API: http://{HOST}:{PORT}{API_PREFIX}")
        app.run(host=HOST, port=PORT)
