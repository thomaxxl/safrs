#!/usr/bin/env python
"""
Search Example

curl -X POST "http://localhost:5000/Users/search?page%5Boffset%5D=0&page%5Blimit%5D=10" -H  "Content-Type: application/json" -d '{
  "meta": {
    "method": "search",
    "args": {
      "query": "J"
    }
  }
}'

the "search" method is implemented in safrs.api_methods, it performs a wildcard search on all columns

"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from safrs import SAFRSBase, SAFRSAPI
from safrs.api_methods import search

db = SQLAlchemy()


class User(SAFRSBase, db.Model):
    """
    description: User description
    """

    __tablename__ = "Users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    email = db.Column(db.String)

    search = search


def create_api(app, HOST="localhost", PORT=5000, API_PREFIX=""):
    api = SAFRSAPI(app, host=HOST, port=PORT, prefix=API_PREFIX)
    api.expose_object(User)
    user = User(name="test", email="email@x.org")
    print(f"Starting API: http://{HOST}:{PORT}/{API_PREFIX}")


def create_app(config_filename=None, host="localhost"):
    app = Flask("demo_app")
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://")
    db.init_app(app)
    with app.app_context():
        db.create_all()
        create_api(app, host)
        user1 = User(name="John")
        user2 = User(name="Jane")
        user3 = User(name="Marie")
    return app


host = "localhost"
app = create_app(host=host)

if __name__ == "__main__":
    app.run(host=host)
