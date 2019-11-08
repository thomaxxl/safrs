# A very simple Flask Hello World app
#
# This script is deployed on thomaxxl.pythonanywhere.com
#

#!/usr/bin/env python
#
# This is a demo application to demonstrate the functionality of the safrs_rest REST API
#
# It can be ran standalone like this:
# python demo_relationship.py [Listener-IP]
#
# This will run the example on http://Listener-Ip:5000
#
# - A database is created and a person is added
# - A rest api is available
# - swagger2 documentation is generated
# - Flask-Admin frontend is created
# - jsonapi-admin pages are served
# - authentication using flaks_login
#
import sys, logging
from flask import Flask, redirect, request, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_swagger_ui import get_swaggerui_blueprint
from flask_marshmallow import Marshmallow
from flask_cors import CORS
from flask_admin import Admin, BaseView
from flask_admin.contrib import sqla
from safrs import SAFRSBase, jsonapi_rpc, SAFRSJSONEncoder, Api
from safrs import search, startswith
from passlib.apps import custom_app_context as pwd_context
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer, BadSignature, SignatureExpired
import flask_login as login

# Needed because we don't want to implicitly commit when using flask-admin
SAFRSBase.db_commit = False
SAFRSBase.search = search
SAFRSBase.startswith = startswith

app = Flask("SAFRS Demo App", template_folder="examples/templates")
app.secret_key = "not so secret"
CORS(app, origins="*", allow_headers=["Content-Type", "Authorization", "Access-Control-Allow-Credentials"], supports_credentials=True)

app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", DEBUG=True, CSRF_SECRET_KEY=b"qsdffrhovdbjkxcwbuisidf")
app.url_map.strict_slashes = False
db = SQLAlchemy(app)
ma = Marshmallow(app)


class Book(SAFRSBase, db.Model):
    """
        description: Book description
    """

    __tablename__ = "Books"
    id = db.Column(db.String, primary_key=True)
    title = db.Column(db.String, default="")
    reader_id = db.Column(db.String, db.ForeignKey("People.id"))
    reader = db.relationship("Person", back_populates="books_read", foreign_keys=[reader_id])
    author_id = db.Column(db.String, db.ForeignKey("People.id"))
    author = db.relationship("Person", back_populates="books_written", foreign_keys=[author_id])
    publisher_id = db.Column(db.String, db.ForeignKey("Publishers.id"))
    publisher = db.relationship("Publisher", back_populates="books")
    reviews = db.relationship("Review")


class Person(SAFRSBase, db.Model):
    """
        description: People description
    """

    __tablename__ = "People"
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, default="")
    email = db.Column(db.String, default="")
    comment = db.Column(db.Text, default="")
    books_read = db.relationship("Book", back_populates="reader", foreign_keys=[Book.reader_id])
    books_written = db.relationship("Book", back_populates="author", foreign_keys=[Book.author_id])
    reviews = db.relationship("Review", back_populates="person")

    # Following method is exposed through the REST API
    # This means it can be invoked with a HTTP POST
    @classmethod
    @jsonapi_rpc(http_methods=["GET"])
    def send_mail(self, email):
        """
            description : Send an email
            args:
                email:
                    type : string
                    example : test email
        """
        content = "Mail to {} : {}\n".format(self.name, email)
        with open("/tmp/mail.txt", "a+") as mailfile:
            mailfile.write(content)
        return {"result": "sent {}".format(content)}


class Publisher(SAFRSBase, db.Model):
    """
        description: Publisher description
    """

    __tablename__ = "Publishers"
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, default="")
    books = db.relationship("Book", back_populates="publisher")


class Review(SAFRSBase, db.Model):
    """
        description: Review description
    """

    __tablename__ = "Reviews"
    reader_id = db.Column(db.String, db.ForeignKey("People.id"), primary_key=True)
    book_id = db.Column(db.String, db.ForeignKey("Books.id"), primary_key=True)
    review = db.Column(db.String, default="")
    person = db.relationship(Person)
    book = db.relationship(Book)


class User(SAFRSBase, db.Model):
    __tablename__ = "Users"
    id = db.Column(db.String(300), primary_key=True)
    username = db.Column(db.String(32), index=True)
    password_hash = db.Column(db.String(200))
    role = db.Column(db.String(200))

    def hash_password(self, password):
        self.password_hash = pwd_context.encrypt(password)

    def verify_password(self, password):
        return pwd_context.verify(password, self.password_hash)

    def generate_auth_token(self, expiration=60000):
        s = Serializer(app.config["SECRET_KEY"], expires_in=expiration)
        return s.dumps({"id": self.id})

    def __init__(self, *args, **kwargs):
        super().__init__(self, *args, **kwargs)

    @staticmethod
    def verify_auth_token(token):
        s = Serializer(app.config["SECRET_KEY"])
        try:
            data = s.loads(token)
        except SignatureExpired:
            log.error("SignatureExpired")
            return None  # valid token, but expired
        except BadSignature:
            log.error("BadSignature")
            return None  # invalid token
        user = User.query.get(data["id"])
        return user

    def get_id(self):
        return self.id

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    @property
    def login(self):
        return self.username


from flask_admin import Admin, AdminIndexView, helpers, expose
from wtforms import Form, BooleanField, StringField, PasswordField, validators, SelectField, IntegerField
from wtforms import form, fields

# Define login and registration forms (for flask-login)
class LoginForm(form.Form):

    username = fields.StringField(validators=[validators.required()])
    password = fields.PasswordField(validators=[validators.required()])

    def validate_login(self, field):
        user = self.get_user()

        if user is None:
            log.error("Invalid user")
            raise validators.ValidationError("Invalid user")

        # we're comparing the plaintext pw with the the hash from the db
        if not user.verify_password(self.password.data):
            # to compare plain text passwords use
            # if user.password != self.password.data:
            raise validators.ValidationError("Invalid password")

    def get_user(self):
        return db.session.query(User).filter_by(username=self.username.data).first()


from wtforms.csrf.session import SessionCSRF
from flask import Flask, session


class RegistrationForm(form.Form):
    class Meta:
        csrf = True
        csrf_class = SessionCSRF
        csrf_secret = app.config["CSRF_SECRET_KEY"]

        @property
        def csrf_context(self):
            return session

    username = fields.StringField(validators=[validators.required()])
    email = fields.StringField()
    name = fields.StringField()
    role = SelectField("Role", choices=[("user", "user"), ("admin", "admin")])
    comment = fields.StringField()
    password = fields.PasswordField(validators=[validators.required()])

    def validate_login(self, field):
        if db.session.query(User).filter_by(username=self.username.data).count() > 0:
            raise validators.ValidationError("Duplicate username")


class MyAdminIndexView(AdminIndexView):
    @expose("/")
    def index(self):
        if not login.current_user.is_authenticated:
            print("Not authenticated")
            return redirect(url_for(".login_view"))
        return super(MyAdminIndexView, self).index()

    @expose("/login/", methods=("GET", "POST"))
    def login_view(self):

        form = LoginForm(request.form)
        if helpers.validate_form_on_submit(form):
            user = form.get_user()
            if not user:
                log.error("User not found")
                return redirect(url_for(".login_view"))
            log.info("Logging in {}".format(user))
            login.login_user(user)

        if login.current_user.is_authenticated:
            return redirect(url_for(".index"))

        link = "<p>Don't have an account? <a href=\"" + url_for(".register_view") + '">Click here to register.</a></p>'
        self._template_args["form"] = form
        self._template_args["link"] = link

        return super(MyAdminIndexView, self).index()

    @expose("/register/", methods=("GET", "POST"))
    def register_view(self):

        form = RegistrationForm(request.form)
        if helpers.validate_form_on_submit(form):
            user = User()

            form.populate_obj(user)
            # we hash the users password to avoid saving it as plaintext in the db,
            user.hash_password(form.password.data)

            db.session.add(user)
            db.session.commit()

            login.login_user(user)
            log.info("redirect rv")
            return redirect(url_for(".index"))
        link = '<p>Already have an account? <a href="' + url_for(".login_view") + '">Click here to log in.</a></p>'
        self._template_args["form"] = form
        self._template_args["link"] = link

        return super(MyAdminIndexView, self).index()

    @expose("/logout/")
    def logout_view(self):
        login.logout_user()
        return redirect(url_for(".index"))


def start_api(HOST="0.0.0.0", PORT=80):

    db.create_all()
    with app.app_context():
        # populate the database
        for i in range(50):
            reader = Person(name="Reader " + str(i), email="reader_email" + str(i))
            author = Person(name="Author " + str(i), email="author_email" + str(i))
            book = Book(title="book_title" + str(i))
            review = Review(reader_id=reader.id, book_id=book.id, review="review " + str(i))
            publisher = Publisher(name="name" + str(i))
            publisher.books.append(book)
            reader.books_read.append(book)
            author.books_written.append(book)
            db.session.add(reader)
            db.session.add(author)
            db.session.add(book)
            db.session.add(publisher)
            db.session.add(review)

        user = User(username="admin")
        user.hash_password("admin")
        db.session.add(user)
        db.session.commit()

        api = Api(app, api_spec_url="/api/swagger", host="{}:{}".format(HOST, PORT), schemes=["http"], description=description)

        # Flask-Admin Config
        admin = Admin(app, url="/admin", index_view=MyAdminIndexView(), base_template="my_master.html")

        for model in [Person, Book, Review, Publisher, User]:
            # add the flask-admin view
            admin.add_view(sqla.ModelView(model, db.session))
            # Create an API endpoint
            api.expose_object(model)

        # Set the JSON encoder used for object to json marshalling
        app.json_encoder = SAFRSJSONEncoder
        # Register the API at /api
        swaggerui_blueprint = get_swaggerui_blueprint("/api", "/api/swagger.json")
        app.register_blueprint(swaggerui_blueprint, url_prefix="/api")

        @app.route("/")
        def goto_api():
            return redirect("/api")


@app.route("/ja")
def redir_ja():
    return redirect("/ja/index.html")


@app.route("/ja/<path:path>", endpoint="jsonapi_admin")
def send_ja(path):
    return send_from_directory("/home/thomaxxl/mysite/jsonapi-admin/build", path)


#
# Authentication
#
def init_login():
    login_manager = login.LoginManager()
    login_manager.init_app(app)

    # Create user loader function
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.query(User).get(user_id)


@app.before_request
def before_request():
    _insecure_views = [
        "do_login",
        "get_resource",
        "new_user",
        "get_auth_token",
        "get_user",
        "admin.login_view",
        "admin.index",
        "do_logout",
        "jsonapi_admin_static",
        "admin.static",
    ]
    _secured_views = ["api.Users"]

    if request.method == "OPTIONS":
        return

    # if request.endpoint  api.Users

    # Cookie based authentication
    if login.current_user and login.current_user.is_authenticated:
        return

    print(request.endpoint)


init_login()
#
#
#

description = """<a href=http://jsonapi.org>Json-API</a> compliant API built with https://github.com/thomaxxl/safrs <br/>
- <a href="https://github.com/thomaxxl/safrs/blob/master/examples/demo_pythonanywhere_com.py">Source code of this page</a> <br/>
- Auto-generated swagger spec: <a href=swagger.json>swagger.json</a> <br/> 
- Petstore <a href=http://petstore.swagger.io/?url=http://thomaxxl.pythonanywhere.com/api/swagger.json>Swagger2 UI</a><br/>
- <a href="http://thomaxxl.pythonanywhere.com/ja/index.html">reactjs+redux frontend</a>
- <a href="/admin/person">Flask-Admin frontend</a>
"""

if __name__ == "__main__":
    HOST = sys.argv[1] if len(sys.argv) > 1 else "thomaxxl.pythonanywhere.com"
    PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    start_api(HOST, PORT)
    app.run(host=HOST, port=PORT)
