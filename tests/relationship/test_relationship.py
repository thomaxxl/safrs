import jsonapi_requests

api = jsonapi_requests.orm.OrmApi.config(
    {
        "API_ROOT": "http://127.0.0.1:5000/",
        "AUTH": ("basic_auth_login", "basic_auth_password"),
        "VALIDATE_SSL": False,
        "TIMEOUT": 1,
    }
)


class User(jsonapi_requests.orm.ApiModel):
    """
        __tablename__ = 'Users'
        id = db.Column(db.String, primary_key=True)
        name = db.Column(db.String, default='')
        email = db.Column(db.String, default='')
        books = db.relationship('Book', back_populates="user", lazy='dynamic')
    """

    class Meta:
        type = "Users"
        api = api

    name = jsonapi_requests.orm.AttributeField("name")
    email = jsonapi_requests.orm.AttributeField("email")
    books = jsonapi_requests.orm.RelationField("books")


class Book(jsonapi_requests.orm.ApiModel):
    """
        __tablename__ = 'Books'
        id = db.Column(db.String, primary_key=True)
        name = db.Column(db.String, default='')
        user_id = db.Column(db.String, db.ForeignKey('Users.id'))
        user = db.relationship('User', back_populates='books')
    """

    class Meta:
        type = "Books"
        api = api

    name = jsonapi_requests.orm.AttributeField("name")
    user_id = jsonapi_requests.orm.AttributeField("user_id")
    user = jsonapi_requests.orm.RelationField("user")


def test_get():
    endpoint = api.endpoint("Users")
    response = endpoint.get(params={"include": "books"})

    for user in response.data:
        print(user.id, user.attributes["name"])
        user = User.from_id(user.id)

    endpoint = api.endpoint("Books")
    response = endpoint.get(params={"include": "user"})

    for book in response.data:
        print(book.id, book.attributes["name"], book.attributes["user_id"])
        print(book.relationships)
        book = Book.from_id(book.id, params={"include": "user"})

    print(user.books)
    print(book.user)

    assert book.attributes["user_id"] == user.id


if __name__ == "__main__":
    test_get()
