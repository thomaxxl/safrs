#!/usr/bin/env python
# run:
# $ FLASK_APP=mini_app flask run
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from safrs import SAFRSBase, Api
from flask_swagger_ui import get_swaggerui_blueprint

db  = SQLAlchemy()

class User(SAFRSBase, db.Model):
    '''
        description: User description
    '''
    __tablename__ = 'users'
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, default = '')
    email = db.Column(db.String, default = '')


def create_api(app, HOST='localhost', PORT=5000, API_PREFIX=''):
    api = Api(app, api_spec_url='/swagger', host='{}:{}'.format(HOST, PORT))   
    swaggerui_blueprint = get_swaggerui_blueprint(API_PREFIX, API_PREFIX + '/swagger.json')
    app.register_blueprint(swaggerui_blueprint, url_prefix=API_PREFIX)
    api.expose_object(User)
    user = User(name='test',email='em@il')
    print('Starting API: http://{}:{}/api'.format(HOST,PORT))


def create_app(config_filename):
    app = Flask('demo_app')
    app.config.update( SQLALCHEMY_DATABASE_URI = 'sqlite://', DEBUG=True )
    with app.app_context():
        db.init_app(app)
        db.create_all()
        create_api(app)
    
    return app