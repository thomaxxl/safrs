#!/usr/bin/env python
#
# This is a demo application to demonstrate the functionality of the safrs_rest REST API with JWT auth
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
'''
Example invocation: 

t@TEMP:~$ token=$(curl -X POST localhost:5000/login -d '{ "username" : "test", "password" : "test" }' --header "Content-Type: application/json" | jq .access_token -r)
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100   344  100   300  100    44  19197   2815 --:--:-- --:--:-- --:--:-- 18750
t@TEMP:~$ curl localhost:5000/users/ -H "Authorization: Bearer $token"
{
  "data": [
    {
      "attributes": {
        "password_hash": null,
        "username": "admin"
      },
      "id": "ac608ebb-1b67-48d3-a9a0-1fba75a78227",
      "relationships": {},
      "type": "users"
    }
  ],
  "jsonapi": {
    "version": "1.0"
  },
  "links": {
    "self": "http://localhost:5000/users/?page[offset]=0&page[limit]=250"
  },
  "meta": {
    "count": 1,
    "limit": 250
  }
}
'''
import sys
import os
import logging
import builtins
from functools import wraps
from flask import Flask, redirect, jsonify, make_response
from flask import abort, request, g, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String
from safrs import SAFRSBase, SAFRSJSONEncoder, Api, jsonapi_rpc
from flask_swagger_ui import get_swaggerui_blueprint
from flask_sqlalchemy import SQLAlchemy

db  = SQLAlchemy()


def test_decorator(fun):
    print('Wrapping:', fun.SAFRSObject.__name__, fun.__name__, fun)
    @wraps(fun)
    def wrapped_fun(*args, **kwargs):
        print('IN HERE:', fun.SAFRSObject.__name__, fun.__name__)
        result = fun(*args, **kwargs)
        return result
    return wrapped_fun


class Item(SAFRSBase, db.Model):
    '''
        description: Item description
    '''
    __tablename__ = 'Items'
    id = Column(String, primary_key=True)
    name = Column(String, default = '')
    user_id = db.Column(db.String, db.ForeignKey('Users.id'))
    user = db.relationship('User', back_populates="items_rel")


class User(SAFRSBase, db.Model):
    '''
        description: User description (With test_decorator)
    '''    
    __tablename__ = 'Users'
    #
    # Add the test_decorator decorator to the exposed methods
    #
    custom_decorators = [test_decorator]

    id = db.Column(String, primary_key=True)
    username = db.Column(db.String(32), index=True)
    items_rel = db.relationship('Item', back_populates="user", lazy='dynamic')

    

def start_app(app):

    api  = Api(app, api_spec_url = '/api/swagger', host = '{}:{}'.format(HOST,PORT), schemes = [ "http" ] )
    
    item = Item(name='test',email='em@il')
    user = User(username='admin')

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
                   JWT_SECRET_KEY = 'ik,ncbxh',
                   DEBUG = True)
HOST = sys.argv[1] if len(sys.argv) > 1 else '0.0.0.0'
PORT = 5000
db.init_app(app)


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

