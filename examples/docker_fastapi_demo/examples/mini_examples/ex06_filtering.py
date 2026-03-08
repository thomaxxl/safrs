#!/usr/bin/env python3
from __future__ import annotations

import json
import operator
import os
from typing import Any

from safrs import SAFRSBase, ValidationError
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

from _shared_fastapi import create_example_app, run_example


Base = declarative_base()

EXAMPLE_PREFIX = "/api_ex06_filtering"
DESCRIPTION = """
Custom filtering example for SAFRS FastAPI.

This example implements a model-level `filter()` override that accepts a JSON
`filter=` payload and applies custom operators.

Examples:

- `GET /api_ex06_filtering/api/People?filter={"name":{"like":"user1%"}}`
- `GET /api_ex06_filtering/api/People?filter={"id":{"in":[1,2]}}`

Use URL encoding when calling from curl or a browser.
""".strip()


class Person(SAFRSBase, Base):
    __tablename__ = "People"

    id = Column(Integer, primary_key=True)
    name = Column(String, default="John Doe")
    email = Column(String, default="")

    @classmethod
    def filter(cls, raw_filter: str) -> Any:
        try:
            payload = json.loads(raw_filter)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Invalid JSON filter: {exc.msg}") from exc

        if not isinstance(payload, dict) or not payload:
            raise ValidationError("Expected JSON object like {'name': {'like': 'user1%'}}")

        query = cls._s_query
        expressions = []

        for attr_name, clause in payload.items():
            if attr_name != "id" and attr_name not in cls._s_jsonapi_attrs:
                raise ValidationError(f'Unknown attribute "{attr_name}"')
            if not isinstance(clause, dict) or len(clause) != 1:
                raise ValidationError(f'Invalid clause for "{attr_name}"')

            op_name, attr_value = next(iter(clause.items()))
            attr = cls.id if attr_name == "id" else cls._s_jsonapi_attrs[attr_name]

            if op_name in {"in", "notin"}:
                if not isinstance(attr_value, list):
                    raise ValidationError(f'Operator "{op_name}" expects an array')
                query = query.filter(getattr(attr, op_name + "_")(attr_value))
                continue

            if op_name in {"like", "ilike", "match", "notilike"} and hasattr(attr, "like"):
                query = query.filter(getattr(attr, op_name)(attr_value))
                continue

            if not hasattr(operator, op_name):
                raise ValidationError(f'Unknown operator "{op_name}"')

            expressions.append(getattr(operator, op_name)(attr, attr_value))

        return query.filter(*expressions)


def seed_data(session: Any) -> None:
    if session.query(Person).count() > 0:
        return
    for index in range(20):
        session.add(Person(name=f"user{index}", email=f"email{index}@example.com"))
    session.commit()


def expose(api: Any) -> None:
    api.expose_object(Person)


def create_app() -> Any:
    database_uri = os.getenv("EX06_FILTERING_DB_URI", "sqlite:////tmp/ex06_filtering.sqlite")
    return create_example_app(
        title="SAFRS FastAPI Filtering Example",
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
        host_env="EX06_FILTERING_HOST",
        port_env="EX06_FILTERING_PORT",
        default_port=5002,
    )


if __name__ == "__main__":
    main()
