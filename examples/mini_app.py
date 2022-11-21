#!/usr/bin/env python
# run:
# $ FLASK_APP=mini_app flask run
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from safrs import SAFRSBase, SAFRSAPI

db = SQLAlchemy()


class User(SAFRSBase, db.Model):
    """
    description: My User description
    """

    __tablename__ = "Users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    email = db.Column(db.String)


def create_api(app, host="127.0.0.1", port=5000, prefix=""):
    api = SAFRSAPI(app, host=host, port=port, prefix=prefix)
    api.expose_object(User)
    #User(name="test", email="email@x.org") # this will automatically commit the user!
    print(f"Starting API: http://{host}:{port}/{prefix}")


def create_app(host="127.0.0.1"):
    app = Flask("demo_app")
    app.config.update(SQLALCHEMY_DATABASE_URI=f"sqlite:///demo.db")
    db.init_app(app)
    with app.app_context():
        db.create_all()
        create_api(app, host)
    return app


app = create_app()

if __name__ == "__main__":
    app.run()
