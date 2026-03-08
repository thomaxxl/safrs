#!/usr/bin/env python3
from __future__ import annotations

import os
from typing import Any

from safrs import SAFRSBase, jsonapi_rpc
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base, relationship

from _shared_fastapi import create_example_app, run_example


Base = declarative_base()

EXAMPLE_PREFIX = "/api_ex08_rpc"
DESCRIPTION = """
JSON:API RPC example for SAFRS FastAPI.

This example exposes a class-level RPC method on `Orders`.

Example:

- `POST /api_ex08_rpc/api/Orders/add_order`

Request body:

```json
{
  "meta": {
    "args": {
      "product_id": 1,
      "quantity": 2
    }
  }
}
```
""".strip()


class Order(SAFRSBase, Base):
    __tablename__ = "Orders"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    _s_auto_commit = False

    @classmethod
    @jsonapi_rpc(http_methods=["POST"])
    def add_order(cls, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {
            "meta": {
                "message": "RPC call received",
                "args": list(args),
                "kwargs": kwargs,
            }
        }


class OrderDetail(SAFRSBase, Base):
    __tablename__ = "OrderDetail"

    id = Column(Integer, primary_key=True)
    OrderId = Column(ForeignKey("Orders.id"), nullable=False)
    Quantity = Column(Integer, nullable=False)
    order = relationship("Order", backref="OrderDetailList")


def seed_data(session: Any) -> None:
    if session.query(Order).count() > 0:
        return

    order = Order(id=1, name="seed order")
    detail = OrderDetail(id=1, OrderId=1, Quantity=3, order=order)
    session.add(order)
    session.add(detail)
    session.commit()


def expose(api: Any) -> None:
    api.expose_object(Order)


def create_app() -> Any:
    database_uri = os.getenv("EX08_RPC_DB_URI", "sqlite:////tmp/ex08_rpc.sqlite")
    return create_example_app(
        title="SAFRS FastAPI RPC Example",
        description=DESCRIPTION,
        example_prefix=EXAMPLE_PREFIX,
        base_model=Base,
        database_uri=database_uri,
        seed_data=seed_data,
        expose=expose,
    )


app = create_app()


def main() -> None:
    run_example(
        create_app,
        host_env="EX08_RPC_HOST",
        port_env="EX08_RPC_PORT",
        default_port=5003,
    )


if __name__ == "__main__":
    main()
