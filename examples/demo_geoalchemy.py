#
# Implementation using geoalchemy column types
# Documentation:
# https://github.com/thomaxxl/safrs/wiki/Postgis-Geoalchemy2
#
import json
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from geoalchemy2 import Geometry
from flask_sqlalchemy import SQLAlchemy
from safrs import SAFRSBase, SAFRSAPI
from safrs.json_encoder import SAFRSJSONEncoder
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import shape
from shapely import geometry
from geoalchemy2.elements import _SpatialElement

app = Flask(__name__)
db = SQLAlchemy()


class GeoJSONEncoder(SAFRSJSONEncoder):
    """
        json encode geometry shapes
    """

    def default(self, obj, **kwargs):
        if isinstance(obj, _SpatialElement):
            result = geometry.mapping(to_shape(obj))
            return result

        return super().default(obj, **kwargs)


class GeometryColumn(db.Column):
    """
        The class attributes are used for the swagger
    """

    description = "Geo column description"
    swagger_type = "json"
    swagger_format = "json"
    sample = {"coordinates": [-122.43129, 37.773972], "type": "Point"}


class City(SAFRSBase, db.Model):
    """
        A city, including its geospatial data
    """

    __tablename__ = "cities"

    point_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    location = db.Column(db.String(30), default="Gotham City")
    geo = GeometryColumn(Geometry(geometry_type="POINT", srid=25833, dimension=2))

    def ___init__(self, *args, **kwargs):
        # convert the json to geometry database type
        # (this can be implemented in the GeometryColumn type.python_type too)
        geo = kwargs.get("geo")
        kwargs["geo"] = str(to_shape(from_shape(geometry.shape(geo))))
        super().__init__(*args, **kwargs)

    def __repr__(self):
        return f"<City {self.location}"

    __str__ = __repr__

    def get_cities_within_radius(self, radius):
        """Return all cities within a given radius (in meters) of this city."""
        return City.query.filter(func.ST_Distance_Sphere(City.geo, self.geo) < radius).all()


def connect_to_db(app):
    """Connect the database to Flask app."""

    app.config["SQLALCHEMY_DATABASE_URI"] = "postgres:///testgis"
    app.config["SQLALCHEMY_ECHO"] = False
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.app = app
    db.init_app(app)


def create_api(app, HOST="localhost", PORT=5000, API_PREFIX=""):
    api = SAFRSAPI(app, host=HOST, port=PORT, prefix=API_PREFIX, json_encoder=GeoJSONEncoder)
    api.expose_object(City)
    print("Starting API: http://{}:{}/{}".format(HOST, PORT, API_PREFIX))


if __name__ == "__main__":

    connect_to_db(app)
    db.create_all()
    host = "192.168.235.136"
    with app.app_context():
        create_api(app, host, 5555)
        for city in City.query.all():
            pass  # print(city, city.location)

    app.run(host=host, port=5555)
