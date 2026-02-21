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
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Table, Text, Time, create_engine, inspect as sa_inspect
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


def _resource_exists(model_cls: Any, jsonapi_id: Any) -> bool:
    try:
        return model_cls.get_instance(str(jsonapi_id)) is not None
    except Exception:
        return False


def _validate_relationship_identifier(identifier: Any, expected_type: str, target_model: Any, seed_key: str) -> None:
    if not isinstance(identifier, dict):
        raise RuntimeError(f"Seed relationship '{seed_key}' must contain resource identifier objects")
    if set(identifier.keys()) != {"type", "id"}:
        raise RuntimeError(f"Seed relationship '{seed_key}' resource identifiers must contain only 'type' and 'id'")

    rel_type = str(identifier.get("type", ""))
    rel_id = str(identifier.get("id", ""))
    if not rel_type or not rel_id:
        raise RuntimeError(f"Seed relationship '{seed_key}' resource identifiers must use non-empty 'type' and 'id'")
    if rel_type != expected_type:
        raise RuntimeError(f"Seed relationship '{seed_key}' type '{rel_type}' does not match expected '{expected_type}'")
    if not _resource_exists(target_model, rel_id):
        raise RuntimeError(f"Seed relationship '{seed_key}' references missing {expected_type} id '{rel_id}'")


def _validate_seed_relationship_doc(rel_doc: Any, rel_property: Any, seed_key: str) -> None:
    if not isinstance(rel_doc, dict) or set(rel_doc.keys()) != {"data"}:
        raise RuntimeError(f"Seed relationship '{seed_key}' must be a JSON:API linkage object with only 'data'")

    if getattr(rel_property, "expose", True) is False:
        raise RuntimeError(f"Seed relationship '{seed_key}' targets a hidden relationship")

    target_model = rel_property.mapper.class_
    expected_type = str(getattr(target_model, "_s_type", target_model.__name__))
    data = rel_doc.get("data")

    if bool(rel_property.uselist):
        if not isinstance(data, list) or not data:
            raise RuntimeError(f"Seed relationship '{seed_key}' must use non-empty list data for to-many relationship")
        for identifier in data:
            _validate_relationship_identifier(identifier, expected_type, target_model, seed_key)
        return

    if not isinstance(data, dict):
        raise RuntimeError(f"Seed relationship '{seed_key}' must use object data for to-one relationship")
    _validate_relationship_identifier(data, expected_type, target_model, seed_key)


def _instance_jsonapi_id(instance: Any) -> str:
    if isinstance(instance, Review):
        return f"{instance.book_id}_{instance.reader_id}"
    value = getattr(instance, "jsonapi_id", None)
    if value in (None, ""):
        value = getattr(instance, "id", None)
    return str(value)


def _instance_identifier(instance: Any) -> dict[str, str]:
    return {"type": str(getattr(instance, "_s_type", type(instance).__name__)), "id": _instance_jsonapi_id(instance)}


def _relationship_items(value: Any) -> list[Any]:
    if value is None:
        return []
    if hasattr(value, "all") and callable(value.all):
        return list(value.all())
    if isinstance(value, list):
        return list(value)
    try:
        return list(value)
    except Exception:
        return []


def _first_sorted_related(value: Any) -> Any:
    items = _relationship_items(value)
    if not items:
        return None
    return sorted(items, key=lambda item: _instance_jsonapi_id(item))[0]


def _relationship_linkage_matches_parent(parent: Any, rel_name: str, rel_doc: Any, rel_property: Any, seed_key: str) -> None:
    data = rel_doc.get("data")
    if bool(rel_property.uselist):
        parent_pairs = {
            (str(getattr(item, "_s_type", type(item).__name__)), _instance_jsonapi_id(item))
            for item in _relationship_items(getattr(parent, rel_name))
        }
        for identifier in data:
            pair = (str(identifier.get("type")), str(identifier.get("id")))
            if pair not in parent_pairs:
                raise RuntimeError(
                    f"Seed relationship '{seed_key}' linkage {pair} is not present on parent {_instance_jsonapi_id(parent)}"
                )
        return

    parent_item = getattr(parent, rel_name)
    if parent_item is None:
        raise RuntimeError(f"Seed relationship '{seed_key}' expects a to-one target on parent {_instance_jsonapi_id(parent)}")
    parent_pair = (str(getattr(parent_item, "_s_type", type(parent_item).__name__)), _instance_jsonapi_id(parent_item))
    seed_pair = (str(data.get("type")), str(data.get("id")))
    if seed_pair != parent_pair:
        raise RuntimeError(
            f"Seed relationship '{seed_key}' linkage {seed_pair} does not match parent linkage {parent_pair}"
        )


def _validate_seed_payload(payload: dict[str, Any]) -> None:
    required_ids = {
        "PersonId": Person,
        "FriendId": Person,
        "BookId": Book,
        "PublisherId": Publisher,
        "ReviewId": Review,
    }
    for key, model_cls in required_ids.items():
        value = payload.get(key)
        if not isinstance(value, str) or not value:
            raise RuntimeError(f"Seed payload is missing required non-empty '{key}'")
        if not _resource_exists(model_cls, value):
            raise RuntimeError(f"Seed payload '{key}' references missing {model_cls.__name__} row '{value}'")

    if payload["PersonId"] == payload["FriendId"]:
        raise RuntimeError("Seed payload must use distinct values for PersonId and FriendId")

    relationships = payload.get("relationships")
    if not isinstance(relationships, dict) or not relationships:
        raise RuntimeError("Seed payload must include a non-empty 'relationships' object")

    relationship_path_params = payload.get("relationship_path_params")
    if not isinstance(relationship_path_params, dict) or not relationship_path_params:
        raise RuntimeError("Seed payload must include a non-empty 'relationship_path_params' object")

    required_relationship_keys = {
        "People.friends",
        "People.books_read",
        "People.books_written",
        "People.reviews",
        "Books.author",
        "Books.reader",
        "Books.publisher",
        "Books.reviews",
        "Publishers.books",
    }
    missing_keys = sorted(required_relationship_keys - set(relationships.keys()))
    if missing_keys:
        raise RuntimeError(f"Seed payload missing required relationship entries: {missing_keys}")
    missing_param_keys = sorted(required_relationship_keys - set(relationship_path_params.keys()))
    if missing_param_keys:
        raise RuntimeError(f"Seed payload missing required relationship path params: {missing_param_keys}")

    collection_model_map = {str(getattr(model_cls, "__tablename__", "")): model_cls for model_cls in EXPOSED_MODELS}
    path_param_key_map = {"People": "PersonId", "Books": "BookId", "Publishers": "PublisherId"}
    for seed_key, rel_doc in relationships.items():
        if not isinstance(seed_key, str) or "." not in seed_key:
            raise RuntimeError(f"Invalid seed relationship key '{seed_key}'")
        collection, rel_name = seed_key.split(".", 1)
        source_model = collection_model_map.get(collection)
        if source_model is None:
            raise RuntimeError(f"Seed relationship '{seed_key}' uses unknown source collection '{collection}'")
        mapper = sa_inspect(source_model)
        if rel_name not in mapper.relationships:
            raise RuntimeError(f"Seed relationship '{seed_key}' uses unknown relationship '{rel_name}'")
        rel_property = mapper.relationships[rel_name]
        _validate_seed_relationship_doc(rel_doc, rel_property, seed_key)

        expected_path_key = path_param_key_map.get(collection)
        if not expected_path_key:
            raise RuntimeError(f"Seed relationship '{seed_key}' has unsupported source collection '{collection}'")
        path_params = relationship_path_params.get(seed_key)
        if not isinstance(path_params, dict) or set(path_params.keys()) != {expected_path_key}:
            raise RuntimeError(
                f"Seed relationship '{seed_key}' must define exactly '{expected_path_key}' in relationship_path_params"
            )
        parent_id = path_params.get(expected_path_key)
        if not isinstance(parent_id, str) or not parent_id:
            raise RuntimeError(f"Seed relationship '{seed_key}' must use a non-empty '{expected_path_key}' path value")
        parent = source_model.get_instance(parent_id)
        if parent is None:
            raise RuntimeError(
                f"Seed relationship '{seed_key}' relationship_path_params references missing {source_model.__name__} id '{parent_id}'"
            )
        _relationship_linkage_matches_parent(parent, rel_name, rel_doc, rel_property, seed_key)


def build_seed_payload(session: Any) -> dict[str, Any]:
    people = session.query(Person).order_by(Person.id).all()
    books = session.query(Book).order_by(Book.id).all()
    publishers = session.query(Publisher).order_by(Publisher.id).all()

    def _select(items: list[Any], predicate: Any, label: str) -> Any:
        for item in items:
            if predicate(item):
                return item
        raise RuntimeError(f"Unable to build seed payload: no parent row found for {label}")

    def _single_identifier(value: Any, label: str) -> dict[str, str]:
        item = _first_sorted_related(value)
        if item is None:
            raise RuntimeError(f"Unable to build seed payload: relationship '{label}' has no linkage values")
        return _instance_identifier(item)

    relationships: dict[str, Any] = {}
    relationship_path_params: dict[str, dict[str, str]] = {}

    person_friends = _select(people, lambda item: bool(_relationship_items(item.friends)), "People.friends")
    relationships["People.friends"] = {"data": [_single_identifier(person_friends.friends, "People.friends")]}
    relationship_path_params["People.friends"] = {"PersonId": _instance_jsonapi_id(person_friends)}

    person_books_read = _select(people, lambda item: bool(_relationship_items(item.books_read)), "People.books_read")
    relationships["People.books_read"] = {"data": [_single_identifier(person_books_read.books_read, "People.books_read")]}
    relationship_path_params["People.books_read"] = {"PersonId": _instance_jsonapi_id(person_books_read)}

    person_books_written = _select(people, lambda item: bool(_relationship_items(item.books_written)), "People.books_written")
    relationships["People.books_written"] = {
        "data": [_single_identifier(person_books_written.books_written, "People.books_written")]
    }
    relationship_path_params["People.books_written"] = {"PersonId": _instance_jsonapi_id(person_books_written)}

    person_reviews = _select(people, lambda item: bool(_relationship_items(item.reviews)), "People.reviews")
    relationships["People.reviews"] = {"data": [_single_identifier(person_reviews.reviews, "People.reviews")]}
    relationship_path_params["People.reviews"] = {"PersonId": _instance_jsonapi_id(person_reviews)}

    book_author = _select(books, lambda item: getattr(item, "author", None) is not None, "Books.author")
    relationships["Books.author"] = {"data": _instance_identifier(book_author.author)}
    relationship_path_params["Books.author"] = {"BookId": _instance_jsonapi_id(book_author)}

    book_reader = _select(books, lambda item: getattr(item, "reader", None) is not None, "Books.reader")
    relationships["Books.reader"] = {"data": _instance_identifier(book_reader.reader)}
    relationship_path_params["Books.reader"] = {"BookId": _instance_jsonapi_id(book_reader)}

    book_publisher = _select(books, lambda item: getattr(item, "publisher", None) is not None, "Books.publisher")
    relationships["Books.publisher"] = {"data": _instance_identifier(book_publisher.publisher)}
    relationship_path_params["Books.publisher"] = {"BookId": _instance_jsonapi_id(book_publisher)}

    book_reviews = _select(books, lambda item: bool(_relationship_items(item.reviews)), "Books.reviews")
    relationships["Books.reviews"] = {"data": [_single_identifier(book_reviews.reviews, "Books.reviews")]}
    relationship_path_params["Books.reviews"] = {"BookId": _instance_jsonapi_id(book_reviews)}

    publisher_books = _select(publishers, lambda item: bool(_relationship_items(item.books)), "Publishers.books")
    relationships["Publishers.books"] = {"data": [_single_identifier(publisher_books.books, "Publishers.books")]}
    relationship_path_params["Publishers.books"] = {"PublisherId": _instance_jsonapi_id(publisher_books)}

    payload: dict[str, Any] = {
        "PersonId": _instance_jsonapi_id(person_friends),
        "FriendId": relationships["People.friends"]["data"][0]["id"],
        "BookId": _instance_jsonapi_id(book_reviews),
        "PublisherId": _instance_jsonapi_id(publisher_books),
        "ReviewId": relationships["Books.reviews"]["data"][0]["id"],
        "relationship_path_params": relationship_path_params,
        "relationships": relationships,
    }

    _validate_seed_payload(payload)
    return payload
