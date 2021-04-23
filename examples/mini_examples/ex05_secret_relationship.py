#!/usr/bin/env python
#
# hidden relationship example
#
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from safrs import SAFRSBase, SAFRSAPI, jsonapi_attr

db = SQLAlchemy()

class SecretData(db.Model):
    """
        Secret model: not accessible through the api
    """
    
    __tablename__ = "SecretData"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("Users.id"))
    key = db.Column(db.String, default="secret key")
    user = db.relationship("User", back_populates="secret_data")

class User(SAFRSBase, db.Model):
    """
        description: User description
    """

    __tablename__ = "Users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, default="")
    email = db.Column(db.String, default="")
    books = db.relationship("Book", back_populates="user", lazy="dynamic")
    secret_data = db.relationship("SecretData", back_populates="user", lazy="dynamic")


class Book(SAFRSBase, db.Model):
    """
        description: Book description
    """

    __tablename__ = "Books"
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, default="")
    user_id = db.Column(db.Integer, db.ForeignKey("Users.id"))
    user = db.relationship("User", back_populates="books")


def create_api(app, HOST="localhost", PORT=5000, API_PREFIX=""):
    api = SAFRSAPI(app, host=HOST, port=PORT, prefix=API_PREFIX)
    api.expose_object(User)
    api.expose_object(Book)
    for i in range(200):
        user = User(name=f"user{i}", email=f"email{i}@dev.to")
        book = Book(name="test_book")
        user.books.append(book)
    print("Starting API: http://{}:{}/{}".format(HOST, PORT, API_PREFIX))


def create_app(config_filename=None, host="localhost"):
    app = Flask("demo_app")
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://")
    db.init_app(app)
    with app.app_context():
        db.create_all()
        create_api(app, host)
    return app


host = "192.168.235.136"
app = create_app(host=host)

if __name__ == "__main__":
    app.run(host=host)
