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
# - A database is created and a person is added
# - A rest api is available
# - swagger2 documentation is generated
# - Flask-Admin frontend is created
# - jsonapi-admin pages are served
#
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

app.config.update( SQLALCHEMY_DATABASE_URI = 'sqlite://',
                   DEBUG = True)
app.url_map.strict_slashes = False
db = SQLAlchemy(app)
ma = Marshmallow(app)


class Book(SAFRSBase, db.Model):
    '''
        description: Book description
    '''
    __tablename__ = 'Books'
    id = db.Column(db.String, primary_key=True)
    title = db.Column(db.String, default = '')
    reader_id = db.Column(db.String, db.ForeignKey('People.id'))
    reader = db.relationship('Person', back_populates='books_read', foreign_keys=[reader_id])
    author_id = db.Column(db.String, db.ForeignKey('People.id'))
    author = db.relationship('Person', back_populates='books_written', foreign_keys=[author_id])
    publisher_id = db.Column(db.String, db.ForeignKey('Publishers.id'))
    publisher = db.relationship('Publisher', back_populates='books')
    reviews = db.relationship('Review')


class Person(SAFRSBase, db.Model):
    '''
        description: People description
    '''
    __tablename__ = 'People'
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, default = '')
    email = db.Column(db.String, default = '')
    comment = db.Column(db.Text, default = '')
    books_read = db.relationship('Book', back_populates = "reader", foreign_keys = [Book.reader_id])
    books_written = db.relationship('Book', back_populates = "author", foreign_keys = [Book.author_id])
    reviews = db.relationship('Review', back_populates = "person")

    # Following method is exposed through the REST API
    # This means it can be invoked with a HTTP POST
    @classmethod
    @jsonapi_rpc(http_methods = ['GET'])
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


class Publisher(SAFRSBase, db.Model):
    '''
        description: Publisher description
    '''
    __tablename__ = 'Publishers'
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, default = '')
    books = db.relationship('Book', back_populates = "publisher")
        

class Review(SAFRSBase, db.Model):
    '''
        description: Review description
    '''
    __tablename__ = 'Reviews'
    reader_id = db.Column(db.String, db.ForeignKey('People.id'), primary_key=True)
    book_id = db.Column(db.String, db.ForeignKey('Books.id'), primary_key=True)
    review = db.Column(db.String, default = '')
    person = db.relationship(Person)
    book = db.relationship(Book)

db.create_all()

#
# Flask-Admin Config
#
admin = Admin(app, url='/admin')
admin.add_view(sqla.ModelView(Person, db.session))
admin.add_view(sqla.ModelView(Book, db.session))
admin.add_view(sqla.ModelView(Review, db.session))
admin.add_view(sqla.ModelView(Publisher, db.session))

#
# jsonapi-admin config
#

@app.route('/ja')
def redir_ja():
    return redirect('/ja/index.html')

@app.route('/ja/<path:path>', endpoint="jsonapi_admin")
def send_ja(path):
    return send_from_directory('/home/thomaxxl/mysite/jsonapi-admin/build', path)


description = '''<a href=http://jsonapi.org>Json-API</a> compliant API built with https://github.com/thomaxxl/safrs <br/>
- <a href="https://github.com/thomaxxl/safrs/blob/master/examples/demo_pythonanywhere_com.py">Source code of this page</a> <br/>
- Auto-generated swagger spec: <a href=swagger.json>swagger.json</a> <br/> 
- Petstore <a href=http://petstore.swagger.io/?url=http://thomaxxl.pythonanywhere.com/api/swagger.json>Swagger2 UI</a><br/>
- <a href="http://thomaxxl.pythonanywhere.com/ja/index.html">reactjs+redux frontend</a>
- <a href="/admin/person">Flask-Admin frontend</a>
'''

HOST = 'thomaxxl.pythonanywhere.com'

with app.app_context():
    # populate the database
    for i in range(500):
        reader = Person(name='Reader '+str(i), email="reader_email"+str(i) )
        author = Person(name='Author '+str(i), email="author_email"+str(i) )
        book = Book(title='book_title' + str(i))
        review = Review(reader_id=reader.id, book_id=book.id, review='review ' + str(i))
        publisher = Publisher(name = 'name' + str(i))
        publisher.books.append(book)
        reader.books_read.append(book)
        author.books_written.append(book)
        db.session.add(reader)
        db.session.add(author)
        db.session.add(book)
        db.session.add(publisher)
        db.session.add(review)
        db.session.commit()
    
    api  = Api(app, api_spec_url = '/api/swagger', host = '{}'.format(HOST), schemes = [ "http" ], description = description )
    # Expose the Person object
    api.expose_object(Person)
    api.expose_object(Book)
    api.expose_object(Publisher)
    api.expose_object(Review)
    # Set the JSON encoder used for object to json marshalling
    app.json_encoder = SAFRSJSONEncoder
    # Register the API at /api
    swaggerui_blueprint = get_swaggerui_blueprint('/api', '/api/swagger.json')
    app.register_blueprint(swaggerui_blueprint, url_prefix='/api')

    @app.route('/')
    def goto_api():
        return redirect('/api')


if __name__ == '__main__':
    HOST = sys.argv[1] if len(sys.argv) > 1 else '0.0.0.0'
    PORT = 5000
    app.run(host=HOST, port=PORT)
