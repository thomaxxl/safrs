#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import datetime
import hashlib
import sys
import uuid
from pathlib import Path
from typing import Any, cast

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from safrs import SAFRSBase, jsonapi_attr, jsonapi_rpc
from safrs.api_methods import search, startswith
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Table, Text, Time, create_engine
from sqlalchemy.orm import DeclarativeBase, relationship, scoped_session, sessionmaker

DESCRIPTION = """
<a href=http://jsonapi.org>Json:API</a> compliant API built with SAFRS<br/>
- shared models for Flask and FastAPI demo apps in tmp/
"""

API_PREFIX = "/api"
TMP_DIR = Path(__file__).resolve().parent
MAILBOX_PATH = TMP_DIR / "mail.txt"

class Base(DeclarativeBase):
    pass


class SAFRSDBWrapper:
    def __init__(self, session: Any, model: Any) -> None:
        self.session = session
        self.Model = model


class BaseModel(SAFRSBase, Base):
    __abstract__ = True
    db_commit = False
    setattr(SAFRSBase, "search", search)


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
    setattr(rel, "expose", False)
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

    @password.setter  # type: ignore[no-redef]
    def password(self, val: str) -> None:
        self._password = hashlib.sha256(val.encode("utf-8")).hexdigest()

    @jsonapi_rpc(http_methods=["POST"])
    def send_mail(self, email: str = "") -> dict[str, str]:
        content = f"Mail to {self.name} : {email}\n"
        with MAILBOX_PATH.open("a+", encoding="utf-8") as mailfile:
            mailfile.write(content)
        return {"output": f"sent {content}"}

    @classmethod
    @jsonapi_rpc(http_methods=["GET", "POST"])
    def my_rpc(cls, *args: Any, **kwargs: Any) -> dict[str, Any]:
        o1 = cls.query.first()
        o2 = cls.query.first()
        data: list[Any] = []
        if o1 is not None and o2 is not None:
            o1.friends.append(o2)
            data = [o1, o2]
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
    def filter(cls, arg: Any) -> Any:
        # Keep the custom filter hook but return a query-compatible result so
        # collection responses remain JSON:API-conformant (`data` as an array).
        return cls._s_filter(arg)

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


EXPOSED_MODELS = [Person, Book, Review, Publisher]


def create_session(db_path: Path) -> Any:
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Session = scoped_session(session_factory)
    Base.metadata.create_all(engine)
    return Session


def seed_data(session: Any, nr_instances: int = 50) -> None:
    if session.query(Person).count() > 0:
        return

    for i in range(nr_instances):
        reader = Person(name=f"Reader {i}", email=f"reader@email{i}", password=str(i))
        author = Person(name=f"Author {i}", email=f"author@email{i}", password=str(i))
        book = Book(id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"book-{i}")), title=f"book_title{i}")
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
            setattr(reader, "comment", cast(Any, ""))

        for obj in [reader, author, book, publisher, review]:
            session.add(obj)

    session.commit()


def build_seed_payload(session: Any) -> dict[str, Any]:
    person = session.query(Person).order_by(Person.id).first()
    friend = None
    if person is not None:
        friend = session.query(Person).filter(Person.id != person.id).order_by(Person.id).first()
    book = session.query(Book).order_by(Book.id).first()
    publisher = session.query(Publisher).order_by(Publisher.id).first()
    review = session.query(Review).order_by(Review.book_id, Review.reader_id).first()

    def _review_jsonapi_id(item: Any) -> str:
        return f"{item.book_id}_{item.reader_id}"

    payload: dict[str, Any] = {"relationships": {}}
    if person is not None:
        payload["PersonId"] = str(person.id)
    if friend is not None:
        payload["FriendId"] = str(friend.id)
    if book is not None:
        payload["BookId"] = str(book.id)
    if publisher is not None:
        payload["PublisherId"] = str(publisher.id)
    if review is not None:
        payload["ReviewId"] = _review_jsonapi_id(review)

    if friend is not None:
        payload["relationships"]["People.friends"] = {"data": [{"type": "Person", "id": str(friend.id)}]}

    if book is not None:
        payload["relationships"]["People.books_read"] = {"data": [{"type": "Book", "id": str(book.id)}]}

    if person is not None:
        authored_book = session.query(Book).filter(Book.author_id == person.id).order_by(Book.id).first()
        if authored_book is not None:
            payload["relationships"]["People.books_written"] = {"data": [{"type": "Book", "id": str(authored_book.id)}]}
        elif book is not None:
            # Fallback to a real object id so relationship write endpoints still get
            # meaningful linkage values in verifier patching.
            payload["relationships"]["People.books_written"] = {"data": [{"type": "Book", "id": str(book.id)}]}

        person_review = session.query(Review).filter(Review.reader_id == person.id).order_by(Review.book_id, Review.reader_id).first()
        if person_review is not None:
            payload["relationships"]["People.reviews"] = {"data": [{"type": "Review", "id": _review_jsonapi_id(person_review)}]}
        elif review is not None:
            payload["relationships"]["People.reviews"] = {"data": [{"type": "Review", "id": _review_jsonapi_id(review)}]}

    if book is not None:
        reviews_for_book = session.query(Review).filter(Review.book_id == book.id).order_by(Review.book_id, Review.reader_id).all()
        if reviews_for_book:
            payload["relationships"]["Books.reviews"] = {
                "data": [{"type": "Review", "id": _review_jsonapi_id(item)} for item in reviews_for_book]
            }
        elif review is not None:
            payload["relationships"]["Books.reviews"] = {"data": [{"type": "Review", "id": _review_jsonapi_id(review)}]}

    author_id = None
    reader_id = None
    if book is not None:
        author_id = book.author_id
        reader_id = book.reader_id
    if author_id is None and friend is not None:
        author_id = friend.id
    if reader_id is None and person is not None:
        reader_id = person.id
    if author_id is not None:
        payload["relationships"]["Books.author"] = {"data": {"type": "Person", "id": str(author_id)}}
    if reader_id is not None:
        payload["relationships"]["Books.reader"] = {"data": {"type": "Person", "id": str(reader_id)}}
    if publisher is not None:
        payload["relationships"]["Books.publisher"] = {"data": {"type": "Publisher", "id": str(publisher.id)}}

    if book is not None and publisher is not None:
        payload["relationships"]["Publishers.books"] = {"data": [{"type": "Book", "id": str(book.id)}]}

    return payload
