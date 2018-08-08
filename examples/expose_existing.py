# coding: utf-8
from sqlalchemy import CHAR, Column, DateTime, Float, ForeignKey, Index, Integer, String, TIMESTAMP, Table, Text, UniqueConstraint, text
from sqlalchemy.sql.sqltypes import NullType
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

import sys, logging
from flask import Flask, render_template, Flask, redirect, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_swagger_ui import get_swaggerui_blueprint
from flask_marshmallow import Marshmallow
from flask_cors import CORS
from flask_admin import Admin, BaseView
from flask_admin.contrib import sqla
from safrs import SAFRSBase, jsonapi_rpc, SAFRSJSONEncoder, Api
from safrs import search, startswith

# Needed because we don't want to implicitly commit when using flask-admin
SAFRSBase.db_commit = False
SAFRSBase.search = search
SAFRSBase.startswith = startswith

app = Flask('SAFRS Demo App', template_folder='/home/thomaxxl/mysite/templates')
app.secret_key ='not so secret'
CORS( app,
      origins="*",
      allow_headers=[ "Content-Type", "Authorization", "Access-Control-Allow-Credentials"],
      supports_credentials = True)

app.config.update( SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:password@localhost/employees',
                   DEBUG = True)
app.url_map.strict_slashes = False
db = SQLAlchemy(app)
ma = Marshmallow(app)

import builtins
builtins.db = db

from mysql_test_db import *

def start_api(HOST = '0.0.0.0' ,PORT = 80):

    db.create_all()
    with app.app_context():
        
        api  = Api(app, api_spec_url = '/api/swagger', host = '{}:{}'.format(HOST,PORT), schemes = [ "http" ], description = description )

        for model in [ Department, Employee, DeptEmp, DeptManager, Salary, Title ] :
            # Create an API endpoint
            api.expose_object(model)
        
        # Set the JSON encoder used for object to json marshalling
        app.json_encoder = SAFRSJSONEncoder
        # Register the API at /api
        swaggerui_blueprint = get_swaggerui_blueprint('/api', '/api/swagger.json')
        app.register_blueprint(swaggerui_blueprint, url_prefix='/api')

        @app.route('/')
        def goto_api():
            return redirect('/api')

description = ''' '''

if __name__ == '__main__':
    HOST = sys.argv[1] if len(sys.argv) > 1 else 'thomaxxl.pythonanywhere.com'
    PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    start_api(HOST,PORT)
    app.run(host=HOST, port=PORT)

