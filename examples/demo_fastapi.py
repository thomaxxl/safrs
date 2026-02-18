#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FastAPI port of examples/demo_pythonanywhere_com.py.

Run:
  pip install -e . "fastapi[standard]"
  python examples/demo_fastapi.py [HOST] [PORT]

Then open:
  http://HOST:PORT/docs
  http://HOST:PORT/swagger.json
"""

from __future__ import annotations

import datetime
import hashlib
import sys
import uuid
from pathlib import Path
from typing import Any

import safrs
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from safrs import SAFRSBase, jsonapi_attr, jsonapi_rpc
from safrs.api_methods import search, startswith
from safrs.fastapi.api import SafrsFastAPI
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Table, Text, Time, create_engine
from sqlalchemy.orm import declarative_base, relationship, scoped_session, sessionmaker

description = """
<a href=http://jsonapi.org>Json:API</a> compliant API built with https://github.com/thomaxxl/safrs <br/>
- <a href="https://github.com/thomaxxl/safrs/blob/master/examples/demo_fastapi.py">Source code of this page</a><br/>
- <a href="/ja/">reactjs+redux frontend</a>
"""

Base = declarative_base()
API_PREFIX = "/api"
DB_URL = "sqlite:///./demo_fastapi.db"


class _SAFRSDBWrapper:
    """Minimal DB wrapper used by SAFRS internals."""

    def __init__(self, session: Any, model: Any) -> None:
        self.session = session
        self.Model = model


class BaseModel(SAFRSBase, Base):
    __abstract__ = True
    db_commit = False
    SAFRSBase.search = search


class DocumentedColumn(Column):
    description = "My custom column description"
    swagger_type = "string"
    swagger_format = "string"
    name_format = "filter[{}]"
    required = False
    default_filter = ""
    sample = "my custom value"


def hidden_relationship(*args: Any, **kwargs: Any) -> Any:
    rel = relationship(*args, **kwargs)
    rel.expose = False
    return rel


friendship = Table(
    "friendships",
    Base.metadata,
    Column("friend_a_id", Integer, ForeignKey("People.id"), primary_key=True),
    Column("friend_b_id", Integer, ForeignKey("People.id"), primary_key=True),
)


class Book(BaseModel):
    __tablename__ = "Books"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, default="")
    reader_id = Column(Integer, ForeignKey("People.id"))
    author_id = Column(Integer, ForeignKey("People.id"))
    publisher_id = Column(Integer, ForeignKey("Publishers.id"))
    publisher = relationship("Publisher", back_populates="books", cascade="save-update, delete")
    reviews = relationship("Review", backref="book", cascade="save-update, delete")
    published = Column(Time)
    startswith = startswith


class Person(BaseModel):
    __tablename__ = "People"
    id = Column(Integer, primary_key=True)
    name = Column(String, default="John Doe")
    email = Column(String, default="")
    comment = DocumentedColumn(Text, default="my empty comment")
    dob = Column(Date)
    books_read = relationship("Book", backref="reader", foreign_keys=[Book.reader_id], cascade="save-update, merge")
    books_written = relationship("Book", backref="author", foreign_keys=[Book.author_id])
    reviews = relationship("Review", backref="reader", cascade="save-update, delete")
    employer_id = Column(Integer, ForeignKey("Publishers.id"))
    employer = hidden_relationship("Publisher", back_populates="employees", cascade="save-update, delete")
    _password = Column(String, default="")
    friends = relationship(
        "Person",
        secondary=friendship,
        primaryjoin=id == friendship.c.friend_a_id,
        secondaryjoin=id == friendship.c.friend_b_id,
    )

    @jsonapi_attr
    def password(self) -> str:
        return "hidden, check _password"

    @password.setter
    def password(self, val: str) -> None:
        self._password = hashlib.sha256(val.encode("utf-8")).hexdigest()

    @jsonapi_rpc(http_methods=["POST"])
    def send_mail(self, email: str = "") -> dict[str, str]:
        content = f"Mail to {self.name} : {email}\n"
        with open("/tmp/mail.txt", "a+", encoding="utf-8") as mailfile:
            mailfile.write(content)
        return {"output": f"sent {content}"}

    @classmethod
    @jsonapi_rpc(http_methods=["GET", "POST"])
    def my_rpc(cls, *args: Any, **kwargs: Any) -> dict[str, Any]:
        o1 = cls.query.first()
        o2 = cls.query.first()
        if o1 is not None and o2 is not None:
            o1.friends.append(o2)
            data: list[Any] = [o1, o2]
        else:
            data = []
        return {"data": data, "meta": {"args": args, "kwargs": kwargs}}


class Publisher(BaseModel):
    __tablename__ = "Publishers"
    id = Column(Integer, primary_key=True)
    name = Column(String, default="")
    books = relationship("Book", back_populates="publisher")
    employees = hidden_relationship(Person, back_populates="employer")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.pop("custom_field", None)
        super().__init__(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        result = SAFRSBase.to_dict(self)
        result["custom_field"] = "some customization"
        return result

    @classmethod
    def filter(cls, arg: Any) -> dict[str, Any]:
        return {"provided": arg}

    @jsonapi_attr
    def stock(self) -> int:
        return 100


class Review(BaseModel):
    __tablename__ = "Reviews"
    book_id = Column(String, ForeignKey("Books.id"), primary_key=True)
    reader_id = Column(Integer, ForeignKey("People.id", ondelete="CASCADE"), primary_key=True)
    review = Column(String, default="")
    created = Column(DateTime, default=datetime.datetime.now)
    http_methods = {"GET", "POST"}


def _mount_optional_static(app: FastAPI) -> None:
    repo_root = Path(__file__).resolve().parent.parent
    ja_dir = repo_root / "jsonapi-admin" / "build"
    swagger_editor_dir = repo_root / "swagger-editor"
    if ja_dir.exists():
        app.mount("/ja", StaticFiles(directory=str(ja_dir), html=True), name="jsonapi_admin")
    if swagger_editor_dir.exists():
        app.mount("/swagger_editor", StaticFiles(directory=str(swagger_editor_dir), html=True), name="swagger_editor")


def _seed_data(session: Any, nr_instances: int = 100) -> None:
    if session.query(Person).count() > 0:
        return

    for i in range(nr_instances):
        reader = Person(name=f"Reader {i}", email=f"reader@email{i}", password=str(i))
        author = Person(name=f"Author {i}", email=f"author@email{i}", password=str(i))
        book = Book(title=f"book_title{i}")
        review = Review(review=f"review {i}")
        publisher = Publisher(name=f"publisher{i}")

        review.reader = reader
        review.book = book
        publisher.books.append(book)
        reader.books_read.append(book)
        author.books_written.append(book)
        reader.friends.append(author)
        author.friends.append(reader)
        if i % 20 == 0:
            reader.comment = ""

        for obj in [reader, author, book, publisher, review]:
            session.add(obj)

    session.commit()


def create_app(host: str = "127.0.0.1", port: int = 5000) -> FastAPI:
    engine = create_engine(DB_URL, future=True)
    SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Session = scoped_session(SessionFactory)

    safrs.DB = _SAFRSDBWrapper(Session, Base)
    Base.metadata.create_all(engine)
    _seed_data(Session)

    app = FastAPI(
        title="SAFRS FastAPI Demo",
        description=description,
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/swagger.json",
    )
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

    @app.middleware("http")
    async def safrs_session_middleware(request: Any, call_next: Any) -> Any:
        try:
            return await call_next(request)
        finally:
            Session.remove()

    api = SafrsFastAPI(app, prefix=API_PREFIX)
    app.state.safrs_api = api

    for model in [Person, Book, Review, Publisher]:
        api.expose_object(model)

    _mount_optional_static(app)

    @app.get("/", include_in_schema=False)
    def root() -> Any:
        return RedirectResponse(url=API_PREFIX)

    @app.get("/health", include_in_schema=False)
    def health() -> dict[str, Any]:
        return {"ok": True, "host": host, "port": port, "api_prefix": API_PREFIX}

    return app


def main() -> None:
    host = "127.0.0.1"
    port = 5000
    if len(sys.argv) > 1:
        host = sys.argv[1]
    if len(sys.argv) > 2:
        port = int(sys.argv[2])
    uvicorn.run(create_app(host=host, port=port), host=host, port=port)


if __name__ == "__main__":
    main()
