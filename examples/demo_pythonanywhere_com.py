#!/usr/bin/env python3
# This script is deployed on thomaxxl.pythonanywhere.com
#
# This is a demo application to demonstrate the functionality of the safrs REST API
#
# It can be ran standalone like this:
# python demo_relationship.py [Listener-IP]
#
# This will run the example on http://Listener-Ip:5000
#
# - A database is created and items are added
# - A rest api is available
# - swagger2 documentation is generated
# - Flask-Admin frontend is created
# - jsonapi-admin pages are served
#
# All sorts of customizations are applied to the exposed objects
# The explanation can be found on the github wiki (https://github.com/thomaxxl/safrs/wiki)
#
import sys
import os
import datetime
import hashlib
from flask import Flask, redirect, send_from_directory, request
from flask_sqlalchemy import SQLAlchemy
try:
    from flask_admin import Admin
    from flask_admin.contrib import sqla
except:
    print("Failed to import flask-admin")
from safrs import SAFRSAPI, SAFRSRestAPI  # api factory
from safrs import SAFRSBase  # db Mixin
from safrs import SAFRSFormattedResponse, jsonapi_format_response, log, paginate
from safrs import jsonapi_attr, ValidationError
from safrs import jsonapi_rpc  # rpc decorator
from safrs.api_methods import search, startswith, duplicate  # rpc methods
from flask import url_for, jsonify
from functools import wraps

# This html will be rendered in the swagger UI
description = """
<a href=http://jsonapi.org>Json:API</a> compliant API built with https://github.com/thomaxxl/safrs <br/>
- <a href="https://github.com/thomaxxl/safrs/blob/master/examples/demo_pythonanywhere_com.py">Source code of this page</a><br/>
- <a href="/ja/index.html">reactjs+redux frontend</a>
- <a href="/admin/person">Flask-Admin frontend</a>
- Auto-generated swagger spec: <a href=/api/swagger.json>swagger.json</a><br/>
- <a href="/swagger_editor/index.html?url=/api/swagger.json">Swagger2 Editor</a> (updates can be added with the SAFRSAPI "custom_swagger" argument)
"""

def testdec(func):
    @wraps(func)
    def testd(*args, **kwargs):
        print(func)
        result = func(*args, **kwargs)
        return result
    return testd

db = SQLAlchemy()

# SQLAlchemy Mixin Superclass with multiple inheritance


class BaseModel(SAFRSBase, db.Model):
    __abstract__ = True


# Customized columns


class WriteOnlyColumn(db.Column):
    """
        The "permissions" attribute set to "w" indicates that the column shouldn't be readable
        in this case it's write-only
    """
    permissions = "w"


class DocumentedColumn(db.Column):
    """
        The class attributes are used for the swagger
    """
    description = "My custom column description"
    swagger_type = "string"
    swagger_format = "string"
    name_format = "filter[{}]"  # Format string with the column name as argument
    required = False
    default_filter = ""
    sample = "my custom value"


# Customized relationships


def hiddenRelationship(*args, **kwargs):
    """
        To hide a relationship, set the expose attribute to False
    """
    relationship = db.relationship(*args, **kwargs)
    relationship.expose = False
    return relationship

# SQLA objects that will be exposed

friendship = db.Table(
    'friendships', db.metadata,
    db.Column('friend_a_id', db.Integer, db.ForeignKey('People.id'),
                                        primary_key=True),
    db.Column('friend_b_id', db.Integer, db.ForeignKey('People.id'),
                                        primary_key=True)
)

class Book(BaseModel):
    """
        description: My book description
    """

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
    """
        description: My person description
    """

    __tablename__ = "People"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, default="John Doe")
    email = db.Column(db.String, default="")
    comment = DocumentedColumn(db.Text, default="my empty comment")
    dob = db.Column(db.Date)
    books_read = db.relationship("Book", backref="reader", foreign_keys=[Book.reader_id], cascade="save-update, merge")
    books_written = db.relationship("Book", backref="author", foreign_keys=[Book.author_id])
    reviews = db.relationship("Review", backref="reader", cascade="save-update, delete")
    password = WriteOnlyColumn(db.String, default="")
    employer_id = db.Column(db.Integer, db.ForeignKey("Publishers.id"))
    employer = hiddenRelationship("Publisher", back_populates="employees", cascade="save-update, delete")
    _salary = db.Column(db.String, default="")  # hidden column
    friends = db.relationship("Person", secondary=friendship,
                           primaryjoin=id==friendship.c.friend_a_id,
                           secondaryjoin=id==friendship.c.friend_b_id,
    )

    # Following methods are exposed through the REST API
    @jsonapi_rpc(http_methods=["POST"])
    def send_mail(self, email=""):
        """
            description : Send an email
            args:
                email: test email
            parameters:
                - name : my_query_string_param
                  default : my_value
        """
        content = "Mail to {} : {}\n".format(self.name, email)
        with open("/tmp/mail.txt", "a+") as mailfile:
            mailfile.write(content)
        return {"output": "sent {}".format(content)}

    @classmethod
    @jsonapi_rpc(http_methods=["POST"])
    def my_rpc(cls, *args, **kwargs):
        """
            pageable: false
            parameters:
                - name : my_query_string_param
                  default : my_value
            args:
                email: test email
        """
        o1 = cls.query.first()
        o2 = cls.query.first()
        o1.friends.append(o2)
        data = [o1,o2]
        response = SAFRSFormattedResponse(data, {}, {}, {}, 1)
        return response
        

class Publisher(BaseModel):
    """
        description: My publisher description
        ---
        demonstrate custom (de)serialization in __init__ and to_dict
    """

    __tablename__ = "Publishers"
    id = db.Column(db.Integer, primary_key=True)  # Integer pk instead of str
    name = db.Column(db.String, default="")
    # books = db.relationship("Book", back_populates="publisher", lazy="dynamic")
    books = db.relationship("Book", back_populates="publisher")
    employees = hiddenRelationship(Person, back_populates="employer")
    
    def __init__(self, *args, **kwargs):
        custom_field = kwargs.pop("custom_field", None)
        SAFRSBase.__init__(self, **kwargs)

    def to_dict(self):
        result = SAFRSBase.to_dict(self)
        result["custom_field"] = "some customization"
        return result

    @classmethod
    def filter(cls, arg):
        """
            Sample custom filtering, override this method to implement custom filtering
            using the sqlalchemy orm

            This method will be called when the filter= url query argument is provided, eg.
            GET /Publishers/?filter=some_filter
        """
        print(arg)
        return {1:1}
        return cls.query.filter_by(name=arg)

    @jsonapi_attr
    def stock(self):
        """
            default: 30
            ---
            Custom Attribute that will be shown in the book swagger
        """
        return 100


class Review(BaseModel):
    """
        description: Review description
    """

    __tablename__ = "Reviews"
    book_id = db.Column(db.String, db.ForeignKey("Books.id"), primary_key=True)
    reader_id = db.Column(db.Integer, db.ForeignKey("People.id", ondelete="CASCADE"), primary_key=True)
    review = db.Column(db.String, default="")
    created = db.Column(db.DateTime, default=datetime.datetime.now())
    http_methods = {"GET", "POST"}  # only allow GET and POST


# API app initialization:
# Create the instances and exposes the classes


def start_api(swagger_host="0.0.0.0", PORT=None):

    # Add startswith methods so we can perform lookups from the frontend
    SAFRSBase.startswith = startswith
    # Needed because we don't want to implicitly commit when using flask-admin
    SAFRSBase.db_commit = False

    with app.app_context():
        db.init_app(app)
        db.create_all()
        # populate the database
        NR_INSTANCES = 200
        for i in range(NR_INSTANCES):
            reader = Person(name="Reader " + str(i), email="reader@email" + str(i), password=hashlib.sha256(bytes(i)).hexdigest())
            author = Person(name="Author " + str(i), email="author@email" + str(i), password=hashlib.sha256(bytes(i)).hexdigest())
            book = Book(title="book_title" + str(i))
            review = Review(reader_id=2*i+1, book_id=book.id, review=f"review {i}")
            publisher = Publisher(name="publisher" + str(i))
            publisher.books.append(book)
            reader.books_read.append(book)
            author.books_written.append(book)
            reader.friends.append(author)
            author.friends.append(reader)
            if i % 20 == 0:
                reader.comment = ""
            for obj in [reader, author, book, publisher, review]:
                db.session.add(obj)

            db.session.commit()
            
        custom_swagger = {
            "info": {"title": "My Customized Title"},
            "securityDefinitions": {"ApiKeyAuth": {"type": "apiKey", "in": "header", "name": "My-ApiKey"}},
        }  # Customized swagger will be merged

        api = SAFRSAPI(
            app,
            host=swagger_host,
            port=PORT,
            prefix=API_PREFIX,
            custom_swagger=custom_swagger,
            schemes=["http", "https"],
            description=description,
        )

        for model in [Person, Book, Review, Publisher]:
            # Create an API endpoint
            api.expose_object(model, method_decorators={"get":[testdec]})

        # see if we can add the flask-admin views
        try:
            admin = Admin(app, url="/admin")
            for model in [Person, Book, Review, Publisher]:
                admin.add_view(sqla.ModelView(model, db.session))
        except Exception as exc:
            print(f"Failed to add flask-admin view {exc}")


API_PREFIX = "/api"  # swagger location
app = Flask("SAFRS Demo App", template_folder="/home/thomaxxl/mysite/templates")
app.secret_key = "not so secret"

app.config.update(SQLALCHEMY_DATABASE_URI="sqlite:///", DEBUG=True)  # DEBUG will also show safrs log messages + exception messages


@app.route("/ja")  # React jsonapi frontend
@app.route("/ja/<path:path>", endpoint="jsonapi_admin")
def send_ja(path="index.html"):
    return send_from_directory(os.path.join(os.path.dirname(__file__), "..", "jsonapi-admin/build"), path)


@app.route("/swagger_editor/<path:path>", endpoint="swagger_editor")
def send_swagger_editor(path="index.html"):
    return send_from_directory(os.path.join(os.path.dirname(__file__), "..", "swagger-editor"), path)


@app.route("/")
def goto_api():
    return redirect(API_PREFIX)


if __name__ == "__main__":
    HOST = sys.argv[1] if len(sys.argv) > 1 else "thomaxxl.pythonanywhere.com"
    PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    start_api(HOST, PORT)
    app.run(host=HOST, port=PORT, threaded=False)
