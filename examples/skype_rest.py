# -*- coding: utf-8 -*-

import sys

if sys.version_info[0] == 3:
    import builtins as __builtin__
    __builtins__.unicode = str
else:
    import __builtin__

from flask import Flask, redirect
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, ForeignKey, Table
from safrs.db import SAFRSBase, documented_api_method
from safrs.restful import SAFRSRestAPI, SAFRSJSONEncoder, Api
from flask_swagger_ui import get_swaggerui_blueprint
from flask_marshmallow import Marshmallow

app = Flask('Skype DB API')
__builtin__.app = app

app.config.update( SQLALCHEMY_DATABASE_URI = 'sqlite:////home/tpollet/main.db.sqlitedb',         
                   DEBUG = True)

db = SQLAlchemy(app)

from sqlalchemy.ext.automap import automap_base
from sqlalchemy import create_engine, inspect


def expose_tables():
    from sqlalchemy.orm import scoped_session
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.ext.declarative import as_declarative

    Base = automap_base()
    Base.prepare(db.engine, reflect=True)
    
    for table in Base.classes:

        print(table)

        sclass = type(str(table.__table__.name), (SAFRSBase, table), 
                      dict(__tablename__ = table.__table__.name, _table = table))

        session = scoped_session(sessionmaker(bind=db.engine))
        api.expose_object(sclass)
        continue
        try:
            api.expose_object(sclass)
        except UnicodeDecodeError as exc:
            print(exc)
        except AttributeError as exc:
            print(exc)
            print(sclass)
            print(dir(sclass))



HOST = sys.argv[1] if len(sys.argv)  > 1 else '0.0.0.0'
PORT = 5000

ma = Marshmallow(app)

# We need some cross-module global variables to be set
__builtin__.db  = db
__builtin__.log =  app.logger
__builtin__.ma  = ma
# Create the database


api  = Api(app, api_spec_url = '/api/swagger', host = '{}:{}'.format(HOST,PORT), schemes = [ "http" ] )

expose_tables()
# Expose the objects
# Set the JSON encoder used for object to json marshalling
app.json_encoder = SAFRSJSONEncoder
# Register the API at /api/docs
swaggerui_blueprint = get_swaggerui_blueprint('/api', '/api/swagger.json')
app.register_blueprint(swaggerui_blueprint, url_prefix='/api')

@app.route('/')
def goto_api():
    return redirect('/api')

log.info('Starting API: http://{}:{}/api'.format(HOST,PORT))
app.run(host=HOST, port = PORT)
