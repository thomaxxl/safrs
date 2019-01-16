#!/usr/bin/env python
#
# This is a demo application to demonstrate the functionality of the safrs_rest REST API
#
# It can be ran standalone like this:
# python demo.py [Listener-IP]
#
# This will run the example on http://Listener-Ip:5000
#
# - A database is created and a user is added
# - A rest api is available
# - swagger2 documentation is generated
#
import sys
from flask import Flask, redirect
from flask_sqlalchemy import SQLAlchemy
from safrs import SAFRSBase, SAFRSAPI, jsonapi_rpc

db  = SQLAlchemy()

# Example sqla database object
class User(SAFRSBase, db.Model):
    '''
        description: User description
    '''
    __tablename__ = 'users'
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, default = '')
    email = db.Column(db.String, default = '')

    # Following method is exposed through the REST API 
    # This means it can be invoked with the argument http_methods
    @jsonapi_rpc(http_methods = ['POST', 'GET'])
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

if __name__ == '__main__':
    HOST = sys.argv[1] if len(sys.argv) > 1 else '0.0.0.0'
    PORT = 5000
    API_PREFIX = ''

    app = Flask('SAFRS Demo Application')
    app.config.update(SQLALCHEMY_DATABASE_URI='sqlite://', DEBUG=True)
    db.init_app(app)
    db.app = app
    # Create the database
    db.create_all()
    
    with app.app_context():
        # Create a user and a book and add the book to the user.books relationship
        user = User(name='thomas', email='em@il')
        api = SAFRSAPI(app, host=HOST, port=PORT, prefix=API_PREFIX)
        # Expose the database objects as REST API endpoints
        api.expose_object(User)
        # Register the API at /api/docs
        print('Starting API: http://{}:{}{}'.format(HOST, PORT, API_PREFIX))
        app.run(host=HOST, port=PORT)


