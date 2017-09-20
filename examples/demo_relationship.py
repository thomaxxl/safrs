#!/usr/bin/env python
#
# This is a demo application to demonstrate the functionality of the safrs_rest REST API
#
# - A database is created and a user is added
# - A rest api is available
# - swagger2 documentation is generated
#
import __builtin__, sys
from flask import Flask, redirect
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, ForeignKey, Table
from db import SAFRSBase, documented_api_method
from flask_swagger_ui import get_swaggerui_blueprint
from flask_marshmallow import Marshmallow
from restful import SAFRSRestAPI, SAFRSJSONEncoder, Api

app = Flask('safrs_demo_app')
__builtin__.app = app

app.config.update( SQLALCHEMY_DATABASE_URI = 'sqlite://',         
                   DEBUG = True)
db = SQLAlchemy(app)
ma = Marshmallow(app)

users_books_table = Table('users_books_table', db.Model.metadata,
    Column('user_id', String, ForeignKey('Users.id', onupdate="CASCADE")),
    Column('book_id', String, ForeignKey('Books.id', onupdate="CASCADE")),
    extend_existing=True
)

# Example sqla database object
class User(SAFRSBase, db.Model):
    '''
        description: User description
    '''
    __tablename__ = 'Users'
    id = Column(String, primary_key=True)
    name = Column(String, default = '')
    email = Column(String, default = '')
    books = db.relationship('Book', secondary = users_books_table)

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


HOST = sys.argv[1] if len(sys.argv) > 1 else '0.0.0.0'
PORT = 5000

# We need some cross-module global variables to be set
__builtin__.db  = db
__builtin__.log =  app.logger
__builtin__.ma  = ma
# Create the database
db.create_all()

# Create a user
user = User(name='test',email='em@il')
book = Book(name='test_book')
user.books.append(book)
db.session.add(user)
db.session.add(book)

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

log.info('Starting API: http://{}:{}/api'.format(HOST,PORT))
app.run(host=HOST, port = PORT)
