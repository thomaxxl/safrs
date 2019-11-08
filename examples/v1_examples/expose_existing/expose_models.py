#
# This script exposes a mysql database as a webservice.
# The db models are described in employees.py
#
import sys, logging, inspect, builtins
from sqlalchemy import CHAR, Column, DateTime, Float, ForeignKey, Index, Integer, String, TIMESTAMP, Table, Text, UniqueConstraint, text
from sqlalchemy.sql.sqltypes import NullType
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, redirect
from flask_swagger_ui import get_swaggerui_blueprint
from safrs import SAFRSBase, jsonapi_rpc, SAFRSJSONEncoder, Api
from safrs import search, startswith

# Database URI, change this to fit your configuration
DB_URI = "mysql+pymysql://root:password@localhost/employees"

app = Flask("SAFRS Demo App")
app.config.update(SQLALCHEMY_DATABASE_URI=DB_URI, DEBUG=True)
app.url_map.strict_slashes = False
SAFRSBase.db_commit = False
builtins.db = SQLAlchemy(app)  # set db as a global variable to be used in employees.py
import models


def start_api(HOST="0.0.0.0", PORT=80):

    with app.app_context():
        api = Api(app, api_spec_url="/api/swagger", host="{}:{}".format(HOST, PORT), schemes=["http"], description="")

        # Get the SAFRSBase models from employees
        for name, model in inspect.getmembers(models):
            bases = getattr(model, "__bases__", [])
            if SAFRSBase in bases:
                # Create an API endpoint
                api.expose_object(model)

        # Set the JSON encoder used for object to json marshalling
        app.json_encoder = SAFRSJSONEncoder
        # Register the API at /api
        swaggerui_blueprint = get_swaggerui_blueprint("/api", "/api/swagger.json")
        app.register_blueprint(swaggerui_blueprint, url_prefix="/api")

        @app.route("/")
        def goto_api():
            return redirect("/api")


if __name__ == "__main__":
    HOST = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
    PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    start_api(HOST, PORT)
    app.run(host=HOST, port=PORT)
