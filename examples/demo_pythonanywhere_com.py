# This script is deployed on thomaxxl.pythonanywhere.com
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
import sys
import os
import datetime
from flask import Flask, render_template, redirect, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_admin import Admin, BaseView
from flask_admin.contrib import sqla
from safrs import SAFRSAPI # api factory
from safrs import SAFRSBase # db Mixin
from safrs import jsonapi_rpc # rpc decorator
from safrs import search, startswith # rpc methods

db = SQLAlchemy()
# Add search and startswith methods so we can perform lookups from the frontend
SAFRSBase.search = search
SAFRSBase.startswith = startswith
# Needed because we don't want to implicitly commit when using flask-admin
SAFRSBase.db_commit = False

class Book(SAFRSBase, db.Model):
    '''
        description: Book description
    '''
    __tablename__ = 'Books'
    id = db.Column(db.String, primary_key=True)
    title = db.Column(db.String, default = '')
    reader_id = db.Column(db.String, db.ForeignKey('People.id'))
    author_id = db.Column(db.String, db.ForeignKey('People.id'))
    publisher_id = db.Column(db.String, db.ForeignKey('Publishers.id'))
    publisher = db.relationship('Publisher', back_populates='books')
    reviews = db.relationship('Review', backref="book", cascade="save-update, merge, delete, delete-orphan")


class Person(SAFRSBase, db.Model):
    '''
        description: People description
    '''
    __tablename__ = 'People'
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, default = '')
    email = db.Column(db.String, default = '')
    comment = db.Column(db.Text, default = '')
    dob = db.Column(db.Date, default='1970-01-01')
    books_read = db.relationship('Book', backref = "reader", foreign_keys = [Book.reader_id], cascade="save-update, merge, delete, delete-orphan")
    books_written = db.relationship('Book', backref = "author", foreign_keys = [Book.author_id])
    reviews = db.relationship('Review', backref = "reader")
    # Following method is exposed through the REST API
    # This means it can be invoked with a HTTP POST
    @classmethod
    @jsonapi_rpc(http_methods = ['POST'])
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
    id = db.Column(db.Integer, primary_key=True) # Integer pk instead of str
    name = db.Column(db.String, default = '')
    books = db.relationship('Book', back_populates = "publisher")
        

class Review(SAFRSBase, db.Model):
    '''
        description: Review description
    '''
    __tablename__ = 'Reviews'
    reader_id = db.Column(db.String, db.ForeignKey('People.id',ondelete="CASCADE"), primary_key=True)
    book_id = db.Column(db.String, db.ForeignKey('Books.id'), primary_key=True)
    review = db.Column(db.String, default = '')
    created = db.Column(db.DateTime, default=datetime.datetime.now())


def start_api(HOST = '0.0.0.0' ,PORT = None):

    with app.app_context():
        db.init_app(app)
        db.create_all()
        # populate the database
        for i in range(300):
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
        
        swagger_host = HOST
        if PORT and PORT != 80:
            swagger_host += ':{}'.format(PORT)
        
        #api  = Api(app, api_spec_url = '/api/swagger', host = swagger_host, schemes = [ "http", "https" ], description = description )
        api = SAFRSAPI(app, host=HOST, port=PORT, prefix=API_PREFIX, api_spec_url = '/api/swagger', schemes = [ "http", "https" ], description = description )

        # Flask-Admin Config
        admin = Admin(app, url='/admin')
        
        for model in [ Person, Book, Review, Publisher] :
            # add the flask-admin view
            admin.add_view(sqla.ModelView(model, db.session))
            # Create an API endpoint
            api.expose_object(model)


API_PREFIX='/api'
app = Flask('SAFRS Demo App', template_folder='/home/thomaxxl/mysite/templates')
app.secret_key ='not so secret'
CORS( app,
      origins="*",
      allow_headers=[ "Content-Type", "Authorization", "Access-Control-Allow-Credentials"],
      supports_credentials = True)

app.config.update( SQLALCHEMY_DATABASE_URI = 'sqlite://',
                   DEBUG = True ) # DEBUG will also show safrs log messages + exception messages

@app.route('/ja')
@app.route('/ja/<path:path>', endpoint="jsonapi_admin")
def send_ja(path='index.html'):
    return send_from_directory(os.path.join(os.path.dirname(__file__),'..','jsonapi-admin/build'), path)

@app.route('/')
def goto_api():
    return redirect(API_PREFIX)

description = '''<a href=http://jsonapi.org>Json-API</a> compliant API built with https://github.com/thomaxxl/safrs <br/>
- <a href="https://github.com/thomaxxl/safrs/blob/master/examples/demo_pythonanywhere_com.py">Source code of this page</a> (only 150 lines!)<br/>
- <a href="/ja/index.html">reactjs+redux frontend</a>
- <a href="/admin/person">Flask-Admin frontend</a>
- Auto-generated swagger spec: <a href=/swagger.json>swagger.json</a><br/> 
- Petstore <a href=http://petstore.swagger.io/?url=http://thomaxxl.pythonanywhere.com/api/swagger.json>Swagger2 UI</a><br/>
'''

if __name__ == '__main__':
    HOST = sys.argv[1] if len(sys.argv) > 1 else 'thomaxxl.pythonanywhere.com'
    PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    start_api(HOST,PORT)
    app.run(host=HOST, port=PORT)
