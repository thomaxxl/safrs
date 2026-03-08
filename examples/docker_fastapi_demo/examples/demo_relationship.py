#!/usr/bin/env python3
from __future__ import annotations

import os
from typing import Any

from safrs import SAFRSBase
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base, relationship

from _shared_fastapi import create_example_app, run_example


Base = declarative_base()

EXAMPLE_PREFIX = "/api_demo_relationship"
DESCRIPTION = """
Basic SAFRS FastAPI relationship example.

This example exposes two resources with a simple one-to-many relationship:

- `Users`
- `Books`

Browse the collections, inspect individual records, and use `include=books` or
`include=user` to inspect relationship serialization.
""".strip()


class User(SAFRSBase, Base):
    __tablename__ = "Users"

    id = Column(Integer, primary_key=True)
    name = Column(String, default="")
    email = Column(String, default="")
    books = relationship("Book", back_populates="user", lazy="dynamic")


class Book(SAFRSBase, Base):
    __tablename__ = "Books"

    id = Column(Integer, primary_key=True)
    name = Column(String, default="")
    user_id = Column(Integer, ForeignKey("Users.id"))
    user = relationship("User", back_populates="books")


def seed_data(session: Any) -> None:
    if session.query(User).count() > 0:
        return

    for index in range(25):
        user = User(name=f"user{index}", email=f"email{index}@example.com")
        user.books.append(Book(name=f"test book {index}"))
        session.add(user)
    session.commit()


def expose(api: Any) -> None:
    api.expose_object(User)
    api.expose_object(Book)


def create_app() -> Any:
    database_uri = os.getenv("DEMO_RELATIONSHIP_DB_URI", "sqlite:////tmp/demo_relationship.sqlite")
    return create_example_app(
        title="SAFRS FastAPI Basic Relationship Example",
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
        host_env="DEMO_RELATIONSHIP_HOST",
        port_env="DEMO_RELATIONSHIP_PORT",
        default_port=5005,
    )


if __name__ == "__main__":
    main()
