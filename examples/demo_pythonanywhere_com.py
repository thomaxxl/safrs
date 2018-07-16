# A very simple Flask Hello World app
#
# This script is deployed on thomaxxl.pythonanywhere.com
#

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
# - swagger2 documentation is generated
# - Flask-Admin frontend is created
# - jsonapi-admin pages are served
#
import sys, os
from flask import Flask
from flask import render_template
from flask import Flask, redirect
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, ForeignKey, Table
from safrs.db import SAFRSBase, documented_api_method
from safrs.jsonapi import SAFRSRestAPI, SAFRSJSONEncoder, Api
from flask_swagger_ui import get_swaggerui_blueprint
from flask_marshmallow import Marshmallow

from flask_cors import CORS
from safrs.db import SAFRSBase, jsonapi_rpc
from safrs.jsonapi import SAFRSJSONEncoder, Api, paginate, jsonapi_format_response, SAFRSFormattedResponse
from safrs.errors import ValidationError, GenericError
from safrs.api_methods import search, startswith


from flask_admin import Admin
from flask_admin import BaseView
from flask_admin.contrib import sqla

# Needed because we don't want to implicitly commit when using flask-admin
SAFRSBase.db_commit = False


app = Flask('SAFRS Demo App', template_folder='/home/thomaxxl/mysite/templates')
CORS(   app,
        origins="*",
        allow_headers=[ "Content-Type", "Authorization", "Access-Control-Allow-Credentials"],
       supports_credentials = True)

app.config.update( SQLALCHEMY_DATABASE_URI = 'sqlite://',
                   DEBUG = True)
app.url_map.strict_slashes = False
db = SQLAlchemy(app)
ma = Marshmallow(app)

# Example sqla database object
class User(SAFRSBase, db.Model):
    '''
        description: User description
    '''
    __tablename__ = 'Users'
    id = Column(String, primary_key=True)
    name = Column(String, default = '')
    email = Column(String, default = '')
    comment = Column(db.Text, default = '')
    books = db.relationship('Book', back_populates = "user")

    # Following method is exposed through the REST API
    # This means it can be invoked with a HTTP POST
    @classmethod
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

    search = search
    startswith = startswith


class Foo(SAFRSBase, db.Model):
    '''
        description: Book description
    '''
    __tablename__ = 'Foo'
    id = Column(String, primary_key=True)
    arg1 = Column(String, default = '')
    bar = Column(String, default = '')


class Book(SAFRSBase, db.Model):
    '''
        description: Book description
    '''
    __tablename__ = 'Books'
    id = Column(String, primary_key=True)
    name = Column(String, default = '')
    user_id = Column(String, ForeignKey('Users.id'))
    user = db.relationship('User', back_populates='books')

    search = search


db.create_all()


#
# Flask-Admin Config
#
class UserView(sqla.ModelView):
    pass


class BookView(sqla.ModelView):
    pass

admin = Admin(app, url='/admin')
admin.add_view(UserView(User, db.session))
admin.add_view(BookView(Book, db.session))

#
# jsonapi-admin config
#
from flask import make_response, send_from_directory

@app.route('/ja')
def redir_ja():
    return redirect('/ja/index.html')

@app.route('/ja/<path:path>', endpoint="jsonapi_admin")
def send_ja(path):
    return send_from_directory('/home/thomaxxl/mysite/jsonapi-admin/build', path)


description = '''<a href=http://jsonapi.org>Json-API</a> compliant API built with https://github.com/thomaxxl/safrs <br/>
- <a href="https://github.com/thomaxxl/safrs/blob/master/examples/demo_relationship.py">Source code of this page</a> <br/>
- Auto-generated swagger spec: <a href=swagger.json>swagger.json</a> <br/> 
- Petstore <a href=http://petstore.swagger.io/?url=http://thomaxxl.pythonanywhere.com/api/swagger.json>Swagger2 UI</a><br/>
- <a href="/ja/index.html">reactjs+redux frontend</a>
- <a href="/admin">Flask-Admin frontend</a>
'''


with app.app_context():
    # populate the database
    for i in range(100):
        user= User( name = 'name' +str(i), email="email"+str(i) )
        book = Book(name='test_book' + str(i))
        user.books.append(book)
        db.session.add(user)
        db.session.add(book)
        db.session.commit()
    
    api  = Api(app, api_spec_url = '/api/swagger', host = '{}'.format('thomaxxl.pythonanywhere.com'), schemes = [ "http" ], description = description )
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


if __name__ == '__main__':
    HOST = sys.argv[1] if len(sys.argv) > 1 else '0.0.0.0'
    PORT = 5000
    app.run(host=HOST, port=PORT)


