#!/usr/bin/env python
from typing import Any
#
# Example using logicbank database constraints
#
# run:
# $ FLASK_APP=ex7_logicbank flask run
from flask import Flask, g
from flask_sqlalchemy import SQLAlchemy
from safrs import SAFRSBase, SafrsApi, DB, jsonapi_rpc

db = SQLAlchemy()


class Order(SAFRSBase, db.Model):
    """
    description: User description
    """

    __tablename__ = "Orders"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    _s_auto_commit = False

    @classmethod
    @jsonapi_rpc(http_methods=["POST"])
    def add_order(self: Any, *args: Any, **kwargs: Any) -> Any:
        """
        args :
            product_id : 1
        """
        print("adding ")
        print(kwargs)
        # ... add the order
        return {}


class OrderDetail(SAFRSBase, db.Model):
    __tablename__ = "OrderDetail"

    id = db.Column(db.Integer, primary_key=True)
    OrderId = db.Column(db.ForeignKey("Orders.id"), nullable=False)
    Quantity = db.Column(db.Integer, nullable=False)
    order = db.relationship("Order", backref="OrderDetailList")


def create_api(app: Any, HOST: Any='localhost', PORT: Any=5000, API_PREFIX: Any='') -> Any:
    api = SafrsApi(app, host=HOST, port=PORT, prefix=API_PREFIX)
    api.expose_object(Order)

    Order(id=0, name="admin", email="admin@safrs.biz")
    print(f"Starting API: http://{HOST}:{PORT}/{API_PREFIX}")


def create_app(config_filename: Any=None, host: Any='localhost') -> Any:
    app = Flask("demo_app")
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://")
    db.init_app(app)
    with app.app_context():
        db.create_all()
        create_api(app, host)
        # User the safrs.DB, not db!
    return app


host = "127.0.0.1"
app = create_app(host=host)


if __name__ == "__main__":
    app.run(host=host)
