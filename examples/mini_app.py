#!/usr/bin/env python
# run:
# $ FLASK_APP=mini_app flask run
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from safrs import SAFRSBase, SAFRSAPI
from safrs.util import classproperty

db = SQLAlchemy()


class User(SAFRSBase, db.Model):
    """
    description: My User description
    """

    __tablename__ = "Users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    email = db.Column(db.String)
    
    @classproperty
    def _s_collection_name(cls):
        """
        :return: the name of the collection, this will be used to construct the endpoint
        """
        return getattr(cls, "__tablename__", cls.__name__) +'__XX__'
    

def create_api(app, host="127.0.0.1", port=5000, prefix="/my_api"):
    api = SAFRSAPI(app, host=host, port=port, prefix=prefix)
    api.expose_object(User)
    User(name="test", email="email@x.org") # this will automatically commit the user!
    print(f"Starting API: http://{host}:{port}/{prefix}")


def create_app(host="127.0.0.1"):
    app = Flask("demo_app")
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite:///mini_app.sqlitedb")
    db.init_app(app)
    with app.app_context():
        db.create_all()
        create_api(app, host)
    return app


app = create_app()

if __name__ == "__main__":
    app.run()
