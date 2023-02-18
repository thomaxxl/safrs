#!/usr/bin/env python
#
# Custom Swagger prefix & blueprint
#
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from safrs import SAFRSBase, SafrsApi
from flask_swagger_ui import get_swaggerui_blueprint
from werkzeug.middleware.dispatcher import DispatcherMiddleware

db = SQLAlchemy()

class User(SAFRSBase, db.Model):
    """
        description: User description
    """

    __tablename__ = "Users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    email = db.Column(db.String)


def create_api(app, host="localhost", port=5000, prefix=""):
    custom_swagger = {"basePath" : prefix}
    api_spec_url = f"/my_swagger"
    api = SafrsApi(app, host=host, port=port, prefix="", swaggerui_blueprint=False, api_spec_url=api_spec_url, custom_swagger=custom_swagger)
    swaggerui_blueprint = get_swaggerui_blueprint(".", f".{api_spec_url}.json", config={"docExpansion": "none", "defaultModelsExpandDepth": -1})
    app.register_blueprint(swaggerui_blueprint, url_prefix="")
    api.expose_object(User)
    user = User(name="test", email="email@x.org")


def create_app(config_filename=None, host="localhost", prefix=""):
    app = Flask(f"{prefix} demo_app")
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://")
    db.init_app(app)
    with app.app_context():
        db.create_all()
        create_api(app, host, prefix=prefix)
    return app

application = Flask("demo_app")
app1 = create_app(host="localhost", prefix="/foo")
app2 = create_app(host="localhost", prefix="/bar")

application.wsgi_app = DispatcherMiddleware(
    application.wsgi_app, {"/foo": app1, 
                           "/bar": app2}
)

if __name__ == "__main__":
    application.run(host="0.0.0.0")
