#!/usr/bin/env python
#
# Custom Swagger prefix & blueprint
#
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from safrs import SAFRSBase, SAFRSAPI
from flask_swagger_ui import get_swaggerui_blueprint

db = SQLAlchemy()


class User(SAFRSBase, db.Model):
    """
        description: User description
    """

    __tablename__ = "Users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    email = db.Column(db.String)


def create_api(app, HOST="localhost", PORT=5000, prefix=""):
    api_spec_url = f"/my_swagger"
    api = SAFRSAPI(app, host=HOST, port=PORT, prefix=prefix, swaggerui_blueprint=False, api_spec_url=api_spec_url)
    swaggerui_blueprint = get_swaggerui_blueprint(prefix, f"{prefix}/{api_spec_url}.json", config={"docExpansion": "none", "defaultModelsExpandDepth": -1})
    app.register_blueprint(swaggerui_blueprint, url_prefix=prefix)
    api.expose_object(User)
    user = User(name="test", email="email@x.org")
    print(f"Starting API: http://{HOST}:{PORT}/{prefix}")


def create_app(config_filename=None, host="localhost"):
    app = Flask("demo_app")
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://")
    db.init_app(app)
    with app.app_context():
        db.create_all()
        create_api(app, host, prefix="/xx")
    return app


host = "localhost"
app = create_app(host=host)

if __name__ == "__main__":
    app.run(host=host)
