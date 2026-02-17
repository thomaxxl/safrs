#!/usr/bin/env python
from typing import Any
# run:
# $ FLASK_APP=mini_app flask run
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from safrs import SAFRSBase, SafrsApi

db = SQLAlchemy()


class User(SAFRSBase, db.Model):
    """
    description: My User description
    """

    __tablename__ = "Users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    email = db.Column(db.String)
    
    @classmethod
    def _s_post(cls: Any, *args: Any, **kwargs: Any) -> Any:
        print(kwargs)
        result = cls(*args, **kwargs)
        print(result)
        return result


def create_api(app: Any, host: Any='localhost', port: Any=5000, prefix: Any='') -> Any:
    api = SafrsApi(app, host=host, port=port, prefix=prefix)
    api.expose_object(User)
    user = User(name="test", email="email@x.org")
    print(f"Starting API: http://{host}:{port}/{prefix}")


def create_app(host: Any='localhost') -> Any:
    app = Flask("demo_app")
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://")
    db.init_app(app)
    with app.app_context():
        db.create_all()
        create_api(app, host)
    return app


app = create_app()

if __name__ == "__main__":
    app.run()
