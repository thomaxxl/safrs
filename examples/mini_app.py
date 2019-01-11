#!/usr/bin/env python
# run:
# $ FLASK_APP=mini_app flask run
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from safrs import SAFRSBase, SAFRSAPI

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
    api = SAFRSAPI(app, host=HOST, port=PORT, prefix=API_PREFIX)
    api.expose_object(User)
    user = User(name='test',email='em@il')
    print('Starting API: http://{}:{}/{}'.format(HOST,PORT,API_PREFIX))


def create_app(config_filename):
    app = Flask('demo_app')
    app.config.update( SQLALCHEMY_DATABASE_URI = 'sqlite://', DEBUG=True )
    db.init_app(app)
    with app.app_context():
        db.create_all()
        create_api(app)
    
    return app