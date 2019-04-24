"""
safrs __init__.py
"""
# -*- coding: utf-8 -*-
#
# pylint: disable=line-too-long
# use max-line-length=120 in .pylintrc
#
# The code implements some seemingly awkward constructs and redundant functionality
# This is however required for backwards compatibility, we'll get rid of it eventually
#
import logging
import os
import builtins
import sys
import pprint
from flask_swagger_ui import get_swaggerui_blueprint
from flask import Flask, redirect, url_for, current_app
from flask.json import JSONEncoder
from flask_sqlalchemy import SQLAlchemy
from .__about__ import __version__, __description__
from .request import SAFRSRequest
from .response import SAFRSResponse
from .errors import ValidationError, GenericError

DB = SQLAlchemy()


def test_decorator(func):
    """ Example flask-restful decorator that can be used in the "decorators" Api argument
        cfr. https://flask-restful.readthedocs.io/en/latest/api.html#id1
    """

    def api_wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    result = api_wrapper
    result.__name__ = func.__name__  # make sure to to reset the __name__ !
    return result


# pylint: disable=invalid-name
# Uppercase bc we're returning the API class here, eventually this might become a class by itself
def SAFRSAPI(
    app, host="localhost", port=5000, prefix="", description="SAFRSAPI", **kwargs
):
    """ API factory method:
        - configure SAFRS
        - create API
        :param app: flask app
        :param host: the host used in the swagger doc
        :param port: the port used in the swagger doc
        :param prefix: the Swagger url prefix (not the api prefix)
        :param description: the swagger description
    """
    decorators = kwargs.pop("decorators", [])  # eg. test_decorator
    custom_swagger = kwargs.pop("custom_swagger", {})
    SAFRS(app, host=host, port=port, prefix=prefix)
    api = Api(
        app,
        api_spec_url="/swagger",
        host=host,
        custom_swagger=custom_swagger,
        description=description,
        decorators=decorators,
        prefix="",
    )

    @app.before_request
    def handle_invalid_usage():
        return

    api.init_app(app)
    return api


# pylint: enable=invalid-name


class SAFRS:
    """This class configures the Flask application to serve SAFRSBase instances
    :param app: a Flask application.
    :param prefix: URL prefix where the swagger should be hosted. Default is '/api'
    :param LOGLEVEL: loglevel configuration variable, values from logging module (0: trace, .. 50: critical)
    """

    # Config settings
    MAX_PAGE_LIMIT = SAFRS_UNLIMITED = 250  # SAFRS_UNLIMITED is deprecated
    ENABLE_RELATIONSHIPS = None
    LOGLEVEL = logging.WARNING
    OBJECT_ID_SUFFIX = None
    DEFAULT_INCLUDED = (
        ""
    )  # change to +all to include everything (slower because relationships will be fetched)
    INSTANCE_ENDPOINT_FMT = None
    INSTANCE_URL_FMT = None
    RESOURCE_URL_FMT = None
    INSTANCEMETHOD_URL_FMT = None
    CLASSMETHOD_URL_FMT = None
    RELATIONSHIP_URL_FMT = None
    ENDPOINT_FMT = None
    #
    config = {}

    def __new__(cls, app, app_db=DB, prefix="", **kwargs):
        if not isinstance(app, Flask):
            raise TypeError("'app' should be Flask.")

        cls.app = app
        cls.db = app_db

        app.json_encoder = SAFRSJSONEncoder
        app.request_class = SAFRSRequest
        app.response_class = SAFRSResponse
        app.url_map.strict_slashes = False

        if app.config.get("DEBUG", False):
            LOGGER.setLevel(logging.DEBUG)

        # Register the API blueprint
        swaggerui_blueprint = kwargs.get("swaggerui_blueprint", None)
        if swaggerui_blueprint is None:
            swaggerui_blueprint = get_swaggerui_blueprint(prefix, "/swagger.json")
            app.register_blueprint(swaggerui_blueprint, url_prefix=prefix)
            swaggerui_blueprint.json_encoder = JSONEncoder

        for conf_name, conf_val in kwargs.items():
            setattr(cls, conf_name, conf_val)

        for conf_name, conf_val in app.config.items():
            setattr(cls, conf_name, conf_val)

        cls.config.update(app.config)

        # pylint: disable=unused-argument,unused-variable
        @app.teardown_appcontext
        def shutdown_session(exception=None):
            """cfr. http://flask.pocoo.org/docs/0.12/patterns/sqlalchemy/"""
            cls.db.session.remove()

        return object.__new__(object)

    @classmethod
    def init_logging(cls, loglevel=logging.WARNING):
        """
            Specify the log format used in the webserver logs
            The webserver will catch stdout so we redirect eveything to sys.stdout
        """
        log = logging.getLogger(__name__)
        if log.level == logging.NOTSET:
            handler = logging.StreamHandler(sys.stderr)
            formatter = logging.Formatter(
                "[%(asctime)s] %(module)s:%(lineno)d %(levelname)s: %(message)s"
            )
            handler.setFormatter(formatter)
            log.setLevel(loglevel)
            log.addHandler(handler)
        return log


def dict_merge(dct, merge_dct):
    """ 
    Recursive dict merge used for creating the swagger spec.
    Inspired by :meth:``dict.update()``, instead of updating only
    top-level keys, dict_merge recurses down into dicts nested
    to an arbitrary depth, updating keys. The ``merge_dct`` is merged into ``dct``.
    :param dct: dict onto which the merge is executed
    :param merge_dct: dct merged into dct
    :return: None
    """
    for k in merge_dct:
        if k in dct and isinstance(dct[k], dict):
            dict_merge(dct[k], merge_dct[k])
        else:
            # convert to string, for ex. http return codes
            dct[str(k)] = merge_dct[k]


try:
    DEBUG = os.getenv("DEBUG", str(logging.WARNING))
    LOGLEVEL = int(DEBUG)
except ValueError:
    print('Invalid LogLevel in DEBUG Environment Variable! "{}"'.format(DEBUG))
    LOGLEVEL = logging.WARNING

log = LOGGER = SAFRS.init_logging(LOGLEVEL)

#
# Following objects will be exported by safrs
#
# We put them at the bottom to avoid circular dependencies
# introduced by .config, though we keep it for backwards compatibility
# pylint: disable=wrong-import-position
from ._api import Api
from .db import SAFRSBase
from .jsonapi import jsonapi_format_response, SAFRSFormattedResponse, paginate
from .json_encoder import SAFRSJSONEncoder
from .api_methods import search, startswith
from .swagger_doc import jsonapi_rpc


__all__ = (
    "__version__",
    "__description__",
    #
    "SAFRSAPI",
    # db:
    "SAFRSBase",
    "jsonapi_rpc",
    # jsonapi:
    "SAFRSJSONEncoder",
    "paginate",
    "jsonapi_format_response",
    "SAFRSFormattedResponse",
    # api_methods:
    "search",
    "startswith",
    # Errors:
    "ValidationError",
    "GenericError",
    # request
    "SAFRSRequest",
)
