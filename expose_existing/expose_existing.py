#
# This script exposes an existing database as a webservice.
# A lot of dirty things going on here because we have to handle all sorts of edge cases
#

import sys, logging, inspect, builtins, os, argparse
from sqlalchemy import CHAR, Column, DateTime, Float, ForeignKey, Index, Integer, String, TIMESTAMP, Table, Text, UniqueConstraint, text
from sqlalchemy.sql.sqltypes import NullType
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, redirect
from flask_swagger_ui import get_swaggerui_blueprint
from safrs import SAFRSBase, jsonapi_rpc, SAFRSJSONEncoder, Api
from safrs import search, startswith
from io import StringIO
from sqlalchemy.engine import create_engine
from sqlalchemy.schema import MetaData

sqlacodegen_dir = os.path.join(os.path.dirname(__file__), 'sqlacodegen')
if not os.path.isdir(sqlacodegen_dir):
    print('sqlacodegen not found')


sys.path.insert(0,sqlacodegen_dir)
from sqlacodegen.codegen import CodeGenerator


def get_args():

    parser = argparse.ArgumentParser(
        description='Generates SQLAlchemy model code from an existing database.')
    parser.add_argument('url', nargs='?', help='SQLAlchemy url to the database')
    parser.add_argument('--version', action='store_true', help="print the version number and exit")
    parser.add_argument('--host',  default = '0.0.0.0', help="host (interface ip) to run")
    parser.add_argument('--port',  default = 5000, type=int, help="host (interface ip) to run")
    parser.add_argument('--models', action='store_true', help="Load models from file instead of generating them dynamically")
    parser.add_argument('--schema', help='load tables from an alternate schema')
    parser.add_argument('--tables', help='tables to process (comma-separated, default: all)')
    parser.add_argument('--noviews', action='store_true', help="ignore views")
    parser.add_argument('--noindexes', action='store_true', help='ignore indexes')
    parser.add_argument('--noconstraints', action='store_true', help='ignore constraints')
    parser.add_argument('--nojoined', action='store_true',
                        help="don't autodetect joined table inheritance")
    parser.add_argument('--noinflect', action='store_true',
                        help="don't try to convert tables names to singular form")
    parser.add_argument('--noclasses', action='store_true',
                        help="don't generate classes, only tables")
    parser.add_argument('--outfile', help='file to write output to (default: stdout)')
    args = parser.parse_args()

    if args.version:
        version = pkg_resources.get_distribution('sqlacodegen').parsed_version
        print(version.public)
        exit()
    if not args.url:
        print('You must supply a url\n', file=sys.stderr)
        parser.print_help()
        exit(1)

    return args


def fix_generated(code):
    if db.session.bind.dialect.name == 'sqlite':
        code = code.replace('Numeric', 'String')

    return code

def codegen(args):

    # Use reflection to fill in the metadata
    engine = create_engine(args.url)
    
    metadata = MetaData(engine)
    tables = args.tables.split(',') if args.tables else None
    metadata.reflect(engine, args.schema, not args.noviews, tables)
    if db.session.bind.dialect.name == 'sqlite':
        # dirty hack for sqlite
        engine.execute('''PRAGMA journal_mode = OFF''')
        
    

    # Write the generated model code to the specified file or standard output

    capture = StringIO()
    outfile = io.open(args.outfile, 'w', encoding='utf-8') if args.outfile else capture # sys.stdout
    generator = CodeGenerator(metadata, args.noindexes, args.noconstraints, args.nojoined,
                              args.noinflect, args.noclasses)
    generator.render(outfile)
    generated = outfile.getvalue()
    generated = fix_generated(generated)
    return generated

args = get_args()
app = Flask('SAFRS Demo App')
app.config.update( SQLALCHEMY_DATABASE_URI = args.url,
                   DEBUG = True)
app.url_map.strict_slashes = False
SAFRSBase.db_commit = False
builtins.db  = SQLAlchemy(app) # set db as a global variable to be used in employees.py

models = codegen(args)

#
# Write the models to file, we could try to exec() but this makes our code more complicated
# Also, we can modify models.py in case things go awry
#
if not args.models:
    with open('models.py','w+') as models_f:
        models_f.write(models)

import models


def start_api(HOST = '0.0.0.0' ,PORT = 80):
    
    with app.app_context():
        api  = Api(app, api_spec_url = '/api/swagger', host = '{}:{}'.format(HOST,PORT), schemes = [ "http" ], description = '' )

        for name, model in inspect.getmembers(models):
            bases = getattr(model, '__bases__', [] )
            
            if SAFRSBase in bases:
                # Create an API endpoint
                api.expose_object(model)

        # Set the JSON encoder used for object to json marshalling
        app.json_encoder = SAFRSJSONEncoder
        # Register the API at /api
        swaggerui_blueprint = get_swaggerui_blueprint('/api', '/api/swagger.json')
        app.register_blueprint(swaggerui_blueprint, url_prefix='/api')

        @app.route('/')
        def goto_api():
            return redirect('/api')

if __name__ == '__main__':
    print()
    HOST = args.host
    PORT = args.port
    start_api(HOST,PORT)

    app.run(host=HOST, port=PORT)

