#!/usr/bin/env python3
from __future__ import annotations

import os
from typing import Any

from safrs import SAFRSBase
from safrs.api_methods import search
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

from _shared_fastapi import create_example_app, run_example


Base = declarative_base()

EXAMPLE_PREFIX = "/api_ex11_search"
DESCRIPTION = """
Search helper example for SAFRS FastAPI.

This example exposes the built-in `search` RPC method on `Users`.

Example:

- `POST /api_ex11_search/api/Users/search?page[offset]=0&page[limit]=10`

Request body:

```json
{
  "meta": {
    "method": "search",
    "args": {
      "query": "J"
    }
  }
}
```
""".strip()


class User(SAFRSBase, Base):
    __tablename__ = "Users"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String)

    search = search


def seed_data(session: Any) -> None:
    if session.query(User).count() > 0:
        return

    session.add_all(
        [
            User(name="John", email="john@example.com"),
            User(name="Jane", email="jane@example.com"),
            User(name="Marie", email="marie@example.com"),
            User(name="Julia", email="julia@example.com"),
        ]
    )
    session.commit()


def expose(api: Any) -> None:
    api.expose_object(User)


def create_app() -> Any:
    database_uri = os.getenv("EX11_SEARCH_DB_URI", "sqlite:////tmp/ex11_search.sqlite")
    return create_example_app(
        title="SAFRS FastAPI Search Example",
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
        host_env="EX11_SEARCH_HOST",
        port_env="EX11_SEARCH_PORT",
        default_port=5004,
    )


if __name__ == "__main__":
    main()
