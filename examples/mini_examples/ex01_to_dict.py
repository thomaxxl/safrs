#!/usr/bin/env python
#
# `to_dict` example
#
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from safrs import SAFRSBase, SafrsApi

db = SQLAlchemy()


class User(SAFRSBase, db.Model):
    """
    description: User description
    """

    __tablename__ = "Users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    email = db.Column(db.String)

    def to_dict(self):
        result = super().to_dict()
        result[1] = 2
        return {1: 2}


def create_api(app, HOST="localhost", PORT=5000, API_PREFIX=""):
    api = SafrsApi(app, host=HOST, port=PORT, prefix=API_PREFIX)
    api.expose_object(User)
    user = User(name="test", email="email@x.org")
    print(f"Starting API: http://{HOST}:{PORT}/{API_PREFIX}")


def create_app(config_filename=None, host="localhost"):
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
