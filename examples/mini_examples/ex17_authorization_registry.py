"""Small Flask example for the optional sparse authorization registry.

`db.create_all()` is used only to keep this demo self-contained. Production
applications should create the grant table through their migration system.
"""

from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy

from safrs import AuthContext, AuthorizationRegistry, SAFRSBase, SafrsApi


app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
db = SQLAlchemy(app)


class Note(SAFRSBase, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, nullable=False)
    internal_note = db.Column(db.String)


authorization = AuthorizationRegistry(metadata=db.metadata)
authorization.register(Note, key="example.note")


def principal() -> AuthContext:
    user = request.headers.get("X-User", "anonymous")
    return AuthContext("example", (f"user:{user}",))


with app.app_context():
    db.create_all()
    # SAFRS inspects the active application's SQLAlchemy extension while it
    # builds routes and documentation, so expose models inside this context.
    api = SafrsApi(
        app,
        app_db=db,
        authorization=authorization,
        principal_provider=principal,
    )
    api.expose_object(Note)

    note = Note(id=1, title="Visible title", internal_note="Hidden by default")
    db.session.add(note)
    db.session.flush()
    authorization.grant(
        db.session,
        scope_key="example",
        subject_key="user:alice",
        Model=Note,
        action="read",
        object_id=1,
    )
    authorization.grant(
        db.session,
        scope_key="example",
        subject_key="user:alice",
        Model=Note,
        action="read",
        object_id=1,
        field="title",
    )
    db.session.commit()


if __name__ == "__main__":
    app.run()
