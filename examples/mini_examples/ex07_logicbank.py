#!/usr/bin/env python
from typing import Any
#
# Example using logicbank database constraints
#
# run:
# $ FLASK_APP=ex7_logicbank flask run
from flask import Flask, g
from flask_sqlalchemy import SQLAlchemy
from safrs import SAFRSBase, SafrsApi, DB
from logic_bank.logic_bank import LogicBank, Rule

db = SQLAlchemy()


class User(SAFRSBase, db.Model):
    """
    description: User description
    """

    __tablename__ = "Users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    email = db.Column(db.String)


def create_api(app: Any, HOST: Any='localhost', PORT: Any=5000, API_PREFIX: Any='') -> Any:
    api = SafrsApi(app, host=HOST, port=PORT, prefix=API_PREFIX)
    api.expose_object(User)
    # Create some users
    User(id=0, name="admin", email="admin@safrs.biz")
    User(id=1, name="test_user", email="test@safrs.biz")
    print(f"Starting API: http://{HOST}:{PORT}/{API_PREFIX}")


def create_app(config_filename: Any=None, host: Any='localhost') -> Any:
    app = Flask("demo_app")
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://")
    db.init_app(app)
    with app.app_context():
        db.create_all()
        create_api(app, host)
        # User the safrs.DB, not db!
        LogicBank.activate(session=DB.session, activator=declare_logic)
    return app


def declare_logic() -> Any:
    def requires_admin(row: Any) -> Any:
        if g.user.id == 0:
            return True
        return False

    Rule.constraint(validate=User, error_msg="Can't change User", as_condition=requires_admin)


host = "localhost"
app = create_app(host=host)


@app.before_request
def set_user() -> Any:
    # id=1 => commit fails in declare_logic
    # id=0 => commit succeeds
    g.user = User.query.filter_by(id=0).first()
    print(f"Using User {g.user} , id: {g.user.id}")


if __name__ == "__main__":
    app.run(host=host)
