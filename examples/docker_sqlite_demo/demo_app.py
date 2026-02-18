"""SQLite-only SAFRS demo app (Docker-friendly).

This module intentionally has *no* side effects at import time. A small WSGI
wrapper (`demo_wsgi.py`) creates the Flask app, initializes SAFRS, seeds the DB,
and returns the WSGI app for gunicorn.

What it demonstrates:
- SQLAlchemy models exposed as JSON:API endpoints under `/api`
- Swagger/OpenAPI generation by SAFRS
- Custom swagger merge via `custom_swagger`
- `@jsonapi_attr` and `@jsonapi_rpc` examples
- Relationship exposure + hidden relationships
"""

from __future__ import annotations

import datetime
import hashlib
from pathlib import Path
from typing import Any, Optional

from flask import Flask, Response, redirect, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

from safrs import SAFRSBase, SAFRSFormattedResponse, SafrsApi, jsonapi_attr, jsonapi_rpc
from safrs.api_methods import search as safrs_search
from safrs.api_methods import startswith as safrs_startswith

API_PREFIX = "/api"

# Repository root is two levels above this file: /app/examples/docker_sqlite_demo/demo_app.py
REPO_ROOT = Path(__file__).resolve().parents[2]
JSONAPI_ADMIN_BUILD = REPO_ROOT / "jsonapi-admin" / "build"
SWAGGER_EDITOR_DIR = REPO_ROOT / "swagger-editor"

SWAGGER_DESCRIPTION = """
<a href="https://jsonapi.org">JSON:API</a> compliant API built with
<a href="https://github.com/thomaxxl/safrs">SAFRS</a>.<br/>
<ul>
  <li><a href="/api/swagger.json">swagger.json</a></li>
  <li><a href="/ja/">jsonapi-admin</a> (optional assets)</li>
  <li><a href="/swagger_editor/">Swagger editor</a> (optional assets)</li>
</ul>
"""

db = SQLAlchemy()
_api: Optional[SafrsApi] = None


def build_sqlite_uri(sqlite_path: str) -> str:
    """Return a SQLAlchemy sqlite URI for the given file path.

    - absolute path -> sqlite:////abs/path.db (via string formatting)
    - relative path -> sqlite:///relative.db
    """
    path = Path(sqlite_path).expanduser()
    return f"sqlite:///{path}"


class BaseModel(SAFRSBase, db.Model):
    """Common base for all demo models."""

    __abstract__ = True

    # Explicit commits (simpler to reason about in a demo)
    db_commit = False

    # Helper JSON:API RPC methods used by frontends
    search = safrs_search
    startswith = safrs_startswith


class DocumentedColumn(db.Column):
    """Column with swagger hints."""

    description = "My custom column description"
    swagger_type = "string"
    swagger_format = "string"
    name_format = "filter[{}]"  # Format string with the column name as argument
    required = False
    default_filter = ""
    sample = "my custom value"


def hidden_relationship(*args: Any, **kwargs: Any) -> Any:
    """Create a relationship that is NOT exposed by SAFRS."""
    relationship = db.relationship(*args, **kwargs)
    relationship.expose = False
    return relationship


friendship = db.Table(
    "friendships",
    db.metadata,
    db.Column("friend_a_id", db.Integer, db.ForeignKey("People.id"), primary_key=True),
    db.Column("friend_b_id", db.Integer, db.ForeignKey("People.id"), primary_key=True),
)


class Book(BaseModel):
    """description: My book description"""

    __tablename__ = "Books"

    id = db.Column(db.String, primary_key=True)
    title = db.Column(db.String, default="")
    reader_id = db.Column(db.Integer, db.ForeignKey("People.id"))
    author_id = db.Column(db.Integer, db.ForeignKey("People.id"))
    publisher_id = db.Column(db.Integer, db.ForeignKey("Publishers.id"))

    publisher = db.relationship("Publisher", back_populates="books", cascade="save-update, delete")
    reviews = db.relationship("Review", backref="book", cascade="save-update, delete")

    published = db.Column(db.Time)


class Person(BaseModel):
    """description: My person description"""

    __tablename__ = "People"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, default="John Doe")
    email = db.Column(db.String, default="")
    comment = DocumentedColumn(db.Text, default="my empty comment")
    dob = db.Column(db.Date)

    books_read = db.relationship(
        "Book",
        backref="reader",
        foreign_keys=[Book.reader_id],
        cascade="save-update, merge",
    )
    books_written = db.relationship("Book", backref="author", foreign_keys=[Book.author_id])
    reviews = db.relationship("Review", backref="reader", cascade="save-update, delete")

    employer_id = db.Column(db.Integer, db.ForeignKey("Publishers.id"))
    employer = hidden_relationship("Publisher", back_populates="employees", cascade="save-update, delete")

    _password = db.Column(db.String, default="")  # hidden column (underscore prefix)

    friends = db.relationship(
        "Person",
        secondary=friendship,
        primaryjoin=id == friendship.c.friend_a_id,
        secondaryjoin=id == friendship.c.friend_b_id,
    )

    @jsonapi_attr
    def password(self) -> Any:
        """---
        "_password" is hidden because of the "_" prefix.
        This custom attribute exposes a placeholder for demo purposes.
        """
        return "hidden, check _password"

    @password.setter
    def password(self, val: str) -> None:
        """Allow setting the hidden `_password` value."""
        self._password = hashlib.sha256(val.encode("utf-8")).hexdigest()

    @jsonapi_rpc(http_methods=["POST"])
    def send_mail(self, email: str = "") -> Any:
        """description: Send an email
        args:
          email: test email
        parameters:
          - name: my_query_string_param
            default: my_value
        """
        content = f"Mail to {self.name} : {email}\n"
        with open("/tmp/mail.txt", "a+", encoding="utf-8") as mailfile:
            mailfile.write(content)
        return {"output": f"sent {content}"}

    @classmethod
    @jsonapi_rpc(http_methods=["POST"])
    def my_rpc(cls, *args: Any, **kwargs: Any) -> Any:
        """pageable: false
        parameters:
          - name: my_query_string_param
            default: my_value
        args:
          email: test email
        """
        o1 = cls.query.first()
        o2 = cls.query.offset(1).first()

        if o1 is None:
            return {"error": "No Person rows exist to link (seed did not run?)"}

        if o2 is None:
            o2 = o1

        o1.friends.append(o2)
        db.session.add(o1)
        db.session.commit()

        # build a jsonapi response object
        response = SAFRSFormattedResponse([o1, o2], {}, {}, {}, 1)
        return response


class Publisher(BaseModel):
    """description: My publisher description
    ---
    demonstrate custom (de)serialization in __init__ and to_dict
    """

    __tablename__ = "Publishers"

    id = db.Column(db.Integer, primary_key=True)  # Integer pk instead of str
    name = db.Column(db.String, default="")
    books = db.relationship("Book", back_populates="publisher")
    employees = hidden_relationship(Person, back_populates="employer")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Custom field is intentionally ignored but demonstrates custom deserialization
        _custom_field = kwargs.pop("custom_field", None)
        SAFRSBase.__init__(self, **kwargs)

    def to_dict(self) -> Any:
        result = SAFRSBase.to_dict(self)
        result["custom_field"] = "some customization"
        return result

    @classmethod
    def filter(cls, arg: Any) -> Any:
        """Sample custom filtering (override to implement custom ORM filtering)."""
        print(arg)
        return {"provided": arg}

    @jsonapi_attr
    def stock(self) -> Any:
        """default: 30
        ---
        Custom Attribute that will be shown in the publisher swagger
        """
        return 100


class Review(BaseModel):
    """description: Review description"""

    __tablename__ = "Reviews"

    book_id = db.Column(db.String, db.ForeignKey("Books.id"), primary_key=True)
    reader_id = db.Column(db.Integer, db.ForeignKey("People.id", ondelete="CASCADE"), primary_key=True)
    review = db.Column(db.String, default="")

    # Use a callable default (evaluated per row), not a timestamp at import time
    created = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    http_methods = {"GET", "POST"}  # only allow GET and POST


def create_app(database_uri: str, debug: bool = True) -> Flask:
    """Create and configure the Flask app."""
    app = Flask("SAFRS Demo App")
    app.secret_key = "not so secret"
    app.config.update(
        SQLALCHEMY_DATABASE_URI=database_uri,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        DEBUG=debug,  # enables SAFRS debug logs + exception messages
    )

    # Enable CORS for the API.
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Init DB extension.
    db.init_app(app)

    register_routes(app)
    return app


def register_routes(app: Flask) -> None:
    """Register the demo's static frontend routes."""

    @app.route("/ja")
    @app.route("/ja/")
    @app.route("/ja/<path:path>")
    def send_ja(path: str = "index.html") -> Any:
        if not JSONAPI_ADMIN_BUILD.exists():
            return Response(
                "jsonapi-admin assets not bundled in this repo.\n\n"
                "If you have them, mount/copy a build to: "
                f"{JSONAPI_ADMIN_BUILD}\n",
                status=404,
                mimetype="text/plain",
            )
        return send_from_directory(JSONAPI_ADMIN_BUILD, path)

    @app.route("/swagger_editor")
    @app.route("/swagger_editor/")
    @app.route("/swagger_editor/<path:path>")
    def send_swagger_editor(path: str = "index.html") -> Any:
        if SWAGGER_EDITOR_DIR.exists():
            return send_from_directory(SWAGGER_EDITOR_DIR, path)

        # No local assets: show a hint + link to the hosted swagger editor.
        swagger_json_url = app.config.get("PUBLIC_SWAGGER_JSON_URL")
        if swagger_json_url:
            return redirect(f"https://editor.swagger.io/?url={swagger_json_url}")
        return redirect("https://editor.swagger.io/")

    @app.route("/")
    def goto_api() -> Any:
        return redirect(API_PREFIX)


def seed_database(n_instances: int = 100) -> None:
    """Create predictable demo data (only when the DB is empty)."""
    if db.session.query(Person).first() is not None:
        return

    objects: list[Any] = []

    for i in range(n_instances):
        reader = Person(name=f"Reader {i}", email=f"reader{i}@example.com", password=str(i))
        author = Person(name=f"Author {i}", email=f"author{i}@example.com", password=str(i))
        book = Book(title=f"book_title{i}")
        publisher = Publisher(name=f"publisher{i}")
        review = Review(review=f"review {i}", book=book, reader=reader)

        publisher.books.append(book)
        reader.books_read.append(book)
        author.books_written.append(book)

        reader.friends.append(author)
        author.friends.append(reader)

        if i % 20 == 0:
            reader.comment = ""

        objects.extend([reader, author, book, publisher, review])

    db.session.add_all(objects)
    db.session.commit()


def start_api(app: Flask, swagger_host: str, swagger_port: Optional[int]) -> SafrsApi:
    """Initialize SAFRS, create swagger spec and expose the models."""
    global _api
    if _api is not None:
        return _api

    with app.app_context():
        db.create_all()

        custom_swagger = {
            "info": {"title": "My Customized Title"},
            "securityDefinitions": {"ApiKeyAuth": {"type": "apiKey", "in": "header", "name": "My-ApiKey"}},
        }

        _api = SafrsApi(
            app,
            host=swagger_host,
            port=swagger_port,
            prefix=API_PREFIX,
            custom_swagger=custom_swagger,
            schemes=["http", "https"],
            description=SWAGGER_DESCRIPTION,
        )

        seed_database(n_instances=100)

        for model in (Person, Book, Review, Publisher):
            _api.expose_object(model)

    return _api
