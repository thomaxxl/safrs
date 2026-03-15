#!/usr/bin/env python
from typing import Any
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from safrs import SAFRSBase, SafrsApi, ValidationError, jsonapi_rpc

db = SQLAlchemy()


class Order(SAFRSBase, db.Model):
    """
    description: Order RPC examples
    """

    __tablename__ = "Orders"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    _s_auto_commit = False

    @classmethod
    @jsonapi_rpc(http_methods=["POST", "GET"])
    def lookup_by_name(cls: Any, name: str = "") -> Any:
        """
        description: Return an Order resource from query or meta.args input.
        args:
            name: demo
        """
        return cls.query.filter_by(name=name).one_or_none()

    @classmethod
    @jsonapi_rpc(http_methods=["POST"])
    def add_order(cls: Any, product_id: int = 0) -> Any:
        """
        description: Create a new order and return a scalar result through meta.result.
        args:
            product_id: 1
        """
        if not product_id:
            raise ValidationError("product_id is required")
        return {"created_product_id": product_id}

    @classmethod
    @jsonapi_rpc(http_methods=["POST"], valid_jsonapi=False)
    def echo_plain(cls: Any, message: str = "") -> Any:
        """
        description: Echo a plain JSON body when valid_jsonapi is disabled.
        args:
            message: hello
        """
        return {"message": message}

    @classmethod
    @jsonapi_rpc(http_methods=["GET"])
    def total_orders(cls: Any) -> Any:
        """
        description: Return a scalar count through meta.result.
        """
        return cls.query.count()


class OrderDetail(SAFRSBase, db.Model):
    __tablename__ = "OrderDetail"

    id = db.Column(db.Integer, primary_key=True)
    OrderId = db.Column(db.ForeignKey("Orders.id"), nullable=False)
    Quantity = db.Column(db.Integer, nullable=False)
    order = db.relationship("Order", backref="OrderDetailList")


def create_api(app: Any, HOST: Any='localhost', PORT: Any=5000, API_PREFIX: Any='') -> Any:
    api = SafrsApi(app, host=HOST, port=PORT, prefix=API_PREFIX)
    api.expose_object(Order)

    db.session.add(Order(id=1, name="demo"))
    db.session.commit()
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
