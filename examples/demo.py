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
from sqlalchemy import Column, Integer, String
from safrs import SAFRSBase, jsonapi_rpc, SAFRS, Api

db  = SQLAlchemy()

# Example sqla database object
class User(SAFRSBase, db.Model):
    '''
        description: User description
    '''
    __tablename__ = 'users'
    id = Column(String, primary_key=True)
    name = Column(String, default = '')
    email = Column(String, default = '')

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


def create_api(app):

    api  = Api(app, host = '{}:{}'.format(HOST,PORT), schemes = [ "http" ] )
    # Expose the User object 
    api.expose_object(User)
    user = User(name='test',email='em@il')

    print('Starting API: http://{}:{}/api'.format(HOST,PORT))
    app.run(host=HOST, port = PORT)



if __name__ == '__main__':
    app = Flask('demo_app')
    db.init_app(app)
    SAFRS(app, db)
    app.config.update( SQLALCHEMY_DATABASE_URI = 'sqlite://' )
    
    # Start the application
    HOST = sys.argv[1] if len(sys.argv) > 1 else '0.0.0.0'
    PORT = 5000

    db.init_app(app)
    # Create the database

    with app.app_context():
        db.create_all()
        create_api(app)