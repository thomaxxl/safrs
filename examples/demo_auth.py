#!/usr/bin/env python
#
# This is a demo application to demonstrate the functionality of the safrs_rest REST API with authentication
#
# It can be ran standalone like this:
# python demo.py [Listener-IP]
#
# This will run the example on http://Listener-Ip:5000
#
# - A database is created and a item is added
# - A rest api is available
# - swagger2 documentation is generated
#
import sys
import os
from flask import Flask, redirect, jsonify, make_response
from flask import abort, request, g, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String
from safrs import SAFRSBase, SAFRSJSONEncoder, Api, jsonapi_rpc
from flask_swagger_ui import get_swaggerui_blueprint
from flask_sqlalchemy import SQLAlchemy
from flask_httpauth import HTTPBasicAuth
from passlib.apps import custom_app_context as pwd_context
from itsdangerous import (TimedJSONWebSignatureSerializer as Serializer, BadSignature, SignatureExpired)

db  = SQLAlchemy()
auth = HTTPBasicAuth()


# Example sqla database object
class Item(SAFRSBase, db.Model):
    '''
        description: Item description
    '''
    __tablename__ = 'items'
    id = Column(String, primary_key=True)
    name = Column(String, default = '')


class User(SAFRSBase, db.Model):
    '''
        description: User description
    '''    
    __tablename__ = 'users'
    id = db.Column(String, primary_key=True)
    username = db.Column(db.String(32), index=True)
    password_hash = db.Column(db.String(64))

    @jsonapi_rpc(http_methods = ['POST'])
    def hash_password(self, password):
        self.password_hash = pwd_context.encrypt(password)

    @jsonapi_rpc(http_methods = ['POST'])
    def verify_password(self, password):
        return pwd_context.verify(password, self.password_hash)

    @jsonapi_rpc(http_methods = ['POST'])
    def generate_auth_token(self, expiration=600):
        s = Serializer(app.config['SECRET_KEY'], expires_in=expiration)
        return s.dumps({'id': self.id})

    @staticmethod
    @jsonapi_rpc(http_methods = ['POST'])
    def verify_auth_token(token):
        s = Serializer(app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except SignatureExpired:
            return None    # valid token, but expired
        except BadSignature:
            return None    # invalid token
        user = User.query.get(data['id'])
        return user


def start_app(app):

    api  = Api(app, api_spec_url = '/api/swagger', host = '{}:{}'.format(HOST,PORT), schemes = [ "http" ] )
    
    item = Item(name='test',email='em@il')
    user = User(username='admin')
    user.hash_password('admin')

    api.expose_object(Item)
    api.expose_object(User)


    # Set the JSON encoder used for object to json marshalling
    app.json_encoder = SAFRSJSONEncoder
    # Register the API at /api/docs
    swaggerui_blueprint = get_swaggerui_blueprint('/api', '/api/swagger.json')
    app.register_blueprint(swaggerui_blueprint, url_prefix='/api')


    print('Starting API: http://{}:{}/api'.format(HOST,PORT))
    app.run(host=HOST, port = PORT)


#
# APP Initialization
#

app = Flask('demo_app')
app.config.update( SQLALCHEMY_DATABASE_URI = 'sqlite://',
                   SQLALCHEMY_TRACK_MODIFICATIONS = False,   
                   SECRET_KEY = b'sdqfjqsdfqizroqnxwc',
                   DEBUG = True)
HOST = sys.argv[1] if len(sys.argv) > 1 else '0.0.0.0'
PORT = 5000
db.init_app(app)


#
# Authentication and custom routes
#
@auth.verify_password
def verify_password(username_or_token, password):
    # first try to authenticate by token
    user = User.verify_auth_token(username_or_token)
    if not user:
        # try to authenticate with username/password
        user = User.query.filter_by(username=username_or_token).first()
        if not user or not user.verify_password(password):
            return False
    print('Authentication Successful for "{}"'.format(user.username))
    g.user = user
    return True

@app.route('/api/token', endpoint='get_auth_token')
@auth.login_required
def get_auth_token():
    '''
        Get username/pass from basic auth header, if valid:
        - Return the token
        - Set cookie token
    '''
    duration = 600
    token = g.user.generate_auth_token(duration).decode('ascii')
    response = make_response(jsonify({'token': token, 'duration': duration}) )
    response.set_cookie('token', token)
    return response

@app.before_request
def before_request():
    
    _insecure_views = ['get_auth_token']
    
    if request.method == 'OPTIONS': 
        return

    if request.endpoint in _insecure_views:
        return

    # Authentication is ok if a valid token is provided in one of these:
    # - "bearer" authorization header *OR*
    # - request "token" query arg *OR*
    # - cookie 

    token = None
    auth_header = request.headers.get('Authorization','')
    if auth_header.upper().startswith('BEARER '):
        token = auth_header.split()[1]

    token = request.cookies.get('token', token)
    token = request.args.get('token',token)

    if token and verify_password(token, None):
        return

    print('Authentication failed for endpoint {}'.format(request.endpoint))
    return redirect(url_for('get_auth_token'))

@app.route('/')
def goto_api():
    return redirect('/api')

@app.teardown_appcontext
def shutdown_session(exception=None):
    '''cfr. http://flask.pocoo.org/docs/0.12/patterns/sqlalchemy/'''
    db.session.remove()


# Start the application
with app.app_context():
    db.create_all()
    start_app(app)