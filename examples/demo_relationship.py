#!/usr/bin/env python
#
# This is a demo application to demonstrate the functionality of the safrs_rest REST API
#
# It can be ran standalone like this:
# python demo_relationship.py [Listener-IP]
#
# This will run the example on http://Listener-Ip:5000
#
# - A database is created and a user is added
# - A rest api is available
# - swagger documentation is generated
#
import sys, logging
import builtins
from flask import Flask, redirect
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, ForeignKey, Table
from safrs.db import SAFRSBase, documented_api_method
from safrs.jsonapi import SAFRSJSONEncoder, Api
from flask_swagger_ui import get_swaggerui_blueprint

app = Flask('safrs_demo_app')
app.config.update( SQLALCHEMY_DATABASE_URI = 'sqlite://' )
db = SQLAlchemy(app)

# Example sqla database object
class User(SAFRSBase, db.Model):
    '''
        description: User description
    '''
    __tablename__ = 'Users'
    id = Column(String, primary_key=True)
    name = Column(String, default = '')
    email = Column(String, default = '')
    books = db.relationship('Book', back_populates = "user" , lazy='dynamic')

    # Following method is exposed through the REST API 
    # This means it can be invoked with a HTTP POST
    @documented_api_method
    def send_mail(self, email):
        '''
            description : Send an email
            args:
                email:
                    type : string 
                    example : test email
        '''
        content = 'Mail to {} : {}\n'.format(self.name, email)
        with open('/tmp/mail.txt', 'a+') as mailfile : 
            mailfile.write(content)
        return { 'result' : 'sent {}'.format(content)}

class Book(SAFRSBase, db.Model):
    '''
        description: Book description
    '''
    __tablename__ = 'Books'
    id = Column(String, primary_key=True)
    name = Column(String, default = '')
    user_id = Column(String, ForeignKey('Users.id'))
    user = db.relationship('User', back_populates='books')


# Create the database
db.create_all()

HOST = sys.argv[1] if len(sys.argv) > 1 else '0.0.0.0'
PORT = 5000
log = logging.getLogger()
log.setLevel(logging.DEBUG)
builtins.log = log

with app.app_context():
    # Create a user
    user = User(name='test',email='em@il')
    book = Book(name='test_book')
    user.books.append(book)

    api  = Api(app, api_spec_url = '/api/swagger', host = '{}:{}'.format(HOST,PORT), schemes = [ "http" ] )
    # Expose the User object 
    api.expose_object(User)
    api.expose_object(Book)
    # Set the JSON encoder used for object to json marshalling
    app.json_encoder = SAFRSJSONEncoder
    # Register the API at /api/docs
    swaggerui_blueprint = get_swaggerui_blueprint('/api', '/api/swagger.json')
    app.register_blueprint(swaggerui_blueprint, url_prefix='/api')

    @app.route('/')
    def goto_api():
        return redirect('/api')

    print('Starting API: http://{}:{}/api'.format(HOST,PORT))
    app.run(host=HOST, port = PORT)
