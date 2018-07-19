
import sys
from flask import Flask, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_swagger_ui import get_swaggerui_blueprint
from flask_cors import CORS
from sqlalchemy import Column, String, ForeignKey

from flask_admin import Admin
from flask_admin import BaseView
from flask_admin.contrib import sqla

db = SQLAlchemy()

def __constructor__(self, *args, **kwargs):
    # initialize super of class type
    super(self.__class__, self).__init__(*args, **kwargs)

def expose_tables(admin):
    from sqlalchemy.orm import scoped_session
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.ext.declarative import as_declarative

    Base = automap_base()
    Base.prepare(db.engine, reflect=True)
    db.engine.execute('''PRAGMA journal_mode = OFF''') 

    for table in Base.classes:
        table_name = str(table.__table__.name)
        print('exposing', table_name)
        sclass = type(table_name, (table,), {'__init__':__constructor__})
        session = scoped_session(sessionmaker(bind=db.engine))

        class FlaskAdminView(sqla.ModelView):
            pass

        admin.add_view(FlaskAdminView(sclass, session))

from sqlalchemy.ext.automap import automap_base


if __name__ == '__main__':
    HOST = sys.argv[1] if len(sys.argv) > 1 else '0.0.0.0'
    PORT = 5000
    app = Flask('SAFRS Demo Application')
    app.config.update(SQLALCHEMY_DATABASE_URI='sqlite:////tmp/test.sqlite', DEBUG=True, SECRET_KEY = 'secret')
    db.init_app(app)
    db.app = app
    # Create the database
    db.create_all()
    admin = Admin(app, url='/admin')
    expose_tables(admin)
    
    with app.app_context():
        app.run(host=HOST, port=PORT)
