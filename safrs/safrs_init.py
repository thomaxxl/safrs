import logging
import os
import sys
from flask import Flask, g, request, url_for
from flask_sqlalchemy import SQLAlchemy
from .request import SAFRSRequest
from .response import SAFRSResponse
from .jsonapi_filters import FilteringStrategy
from .jsonapi_context import JsonApiContext, set_jsonapi_context, reset_jsonapi_context
from functools import wraps
import safrs
import flask.app
from typing import Any

try:
    from flask_swagger_ui import get_swaggerui_blueprint
except ModuleNotFoundError:
    get_swaggerui_blueprint = None


def _protect_blueprint_registration(deferred_functions: list[Any], decorators: list[Any]) -> Any:
    """Return a single blueprint registration function that runs all
    ``deferred_functions`` and then protects the view functions they register
    with ``decorators`` (SEC-06 documentation protection).

    Wrapping happens after all registrations so Flask's same-endpoint
    re-registration guard (view-function identity) keeps working.
    """
    originals = list(deferred_functions)

    def protected_register(state: Any) -> None:
        app = getattr(state, "app", state)  # blueprints pass a BlueprintSetupState
        registered_before = set(app.view_functions)
        for original in originals:
            original(state)
        for endpoint in set(app.view_functions) - registered_before:
            view = app.view_functions[endpoint]
            for decorator in reversed(decorators):
                view = decorator(view)
            app.view_functions[endpoint] = view

    return protected_register


def _is_truthy_env(value: Any) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _parse_loglevel_value(value: Any) -> int | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    try:
        return int(normalized)
    except ValueError:
        upper = normalized.upper()
        if upper in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            return int(getattr(logging, upper))
    return None


def _resolve_loglevel() -> int:
    loglevel_env = os.getenv("LOGLEVEL")
    parsed_loglevel = _parse_loglevel_value(loglevel_env)
    if parsed_loglevel is not None:
        return parsed_loglevel
    if loglevel_env is not None:
        print(f'Invalid LOGLEVEL Environment Variable! "{loglevel_env}"')

    debug_env = os.getenv("DEBUG")
    if debug_env is not None:
        parsed_debug = _parse_loglevel_value(debug_env)
        if parsed_debug is not None:
            return parsed_debug
        if _is_truthy_env(debug_env):
            return logging.DEBUG
        print(f'Invalid LogLevel in DEBUG Environment Variable! "{debug_env}"')
        return logging.INFO

    if _is_truthy_env(os.getenv("FLASK_DEBUG")):
        return logging.DEBUG

    return logging.WARNING


class SAFRS:
    """This class configures the Flask application to serve SAFRSBase instances
    :param app: a Flask application.
    :param prefix: URL prefix where the swagger should be hosted. Default is '/api'
    :param LOGLEVEL: loglevel configuration variable, values from logging module (0: trace, .. 50: critical)
    """

    # Configuration settings are stored as class variables
    MAX_PAGE_LIMIT = 1000
    DEFAULT_PAGE_LIMIT = 250
    MAX_PAGE_OFFSET = 2**31
    MAX_BULK_ITEMS = 1000
    MAX_INCLUDE_DEPTH = 5
    MAX_INCLUDE_PATHS = 25
    MAX_INCLUDED_RESOURCES = 1000
    ENABLE_RELATIONSHIPS = True
    ENABLE_METHODS = True
    LOGLEVEL = logging.WARNING
    OBJECT_ID_SUFFIX = None
    DEFAULT_INCLUDED = ""  # change to +all to include everything (slower because relationships will be fetched)
    INSTANCE_ENDPOINT_FMT = None
    INSTANCE_URL_FMT = None
    RESOURCE_URL_FMT = None
    INSTANCEMETHOD_URL_FMT = None
    CLASSMETHOD_URL_FMT = None
    RELATIONSHIP_URL_FMT = None
    ENDPOINT_FMT = None
    MAX_TABLE_COUNT = 10**7  # table counts will become really slow for large tables, inform the user about it using this
    INCLUDE_ALL = "+all"  # include= url query argument that tells us to include all related resources
    #
    config: dict[str, Any] = {}
    filtering_strategy = FilteringStrategy()

    OPTIMIZED_LOADING = True

    def __init__(self: Any, app: flask.app.Flask, *args: Any, **kwargs: Any) -> None:
        """
        Constructor
        """
        self.app = app
        if app is not None:
            self.init_app(app, *args, **kwargs)

    def init_app(self: Any, app: flask.app.Flask, host: str='localhost', port: int=5000, prefix: str='', app_db: Any=None, swaggerui_blueprint: bool=True, docs_decorators: Any=None, **kwargs: Any) -> None:
        """
        API and application initialization
        """
        if not isinstance(app, Flask):  # pragma: no cover
            raise TypeError("'app' should be Flask.")

        if app_db is None:
            app_db = app.extensions["sqlalchemy"]

        safrs.DB = self.db = app_db

        # SEC-06: documentation routes (swagger.json / swagger UI / ALS schema)
        # can be protected with the same decorators as data routes. In DEBUG
        # mode the docs stay publicly accessible so development is unaffected.
        from .config import is_debug

        requested_docs_decorators = list(docs_decorators or [])
        effective_docs_decorators: list[Any] = [] if is_debug() else requested_docs_decorators
        if requested_docs_decorators and not effective_docs_decorators:
            safrs.log.info("docs_decorators are ignored in DEBUG mode; API documentation stays public")
        app.extensions["safrs_docs_decorators"] = effective_docs_decorators

        app.request_class = SAFRSRequest
        app.response_class = SAFRSResponse
        app.url_map.strict_slashes = False

        if app.config.get("DEBUG", False) or _is_truthy_env(os.getenv("FLASK_DEBUG")):
            log.setLevel(logging.DEBUG)

        # Register the API blueprint
        if swaggerui_blueprint is True:
            if get_swaggerui_blueprint is None:
                raise RuntimeError(
                    "flask-swagger-ui is required for Flask Swagger UI. Install Flask adapter deps with "
                    "`pip install \"safrs[flask]\"`."
                )
            swagger_bp = get_swaggerui_blueprint(
                prefix, f"{prefix}/swagger.json", config={"docExpansion": "none", "defaultModelsExpandDepth": -1}
            )
            if effective_docs_decorators:
                swagger_bp.deferred_functions = [
                    _protect_blueprint_registration(
                        swagger_bp.deferred_functions, effective_docs_decorators
                    )
                ]
            app.register_blueprint(swagger_bp, url_prefix=prefix)

        # Snapshot SAFRS defaults per Flask application. ``get_config`` reads
        # this app-local mapping before the backward-compatible process-global
        # class attributes, preventing one app from inheriting another app's
        # pagination, CORS, or relationship configuration.
        app_safrs_config = {
            conf_name: conf_val
            for conf_name, conf_val in vars(SAFRS).items()
            if conf_name.isupper() and not callable(conf_val)
        }

        for conf_name, conf_val in kwargs.items():
            app_safrs_config[conf_name] = conf_val

        for conf_name, conf_val in app.config.items():
            app_safrs_config[conf_name] = conf_val

        app.extensions["safrs_config"] = app_safrs_config

        @app.before_request
        def handle_invalid_usage() -> Any:
            return

        @app.before_request
        def init_ja_data() -> Any:
            def _collection_path(Model: Any) -> str:
                return str(url_for(Model.get_endpoint()))

            def _instance_path(Model: Any, obj: Any) -> str:
                params = {Model._s_object_id: obj.jsonapi_id}
                return str(url_for(Model.get_endpoint(type="instance"), **params))

            def _relationship_path(Model: Any, obj: Any, rel_name: str) -> str:
                instance_path = _instance_path(Model, obj).rstrip("/")
                return f"{instance_path}/{rel_name}"

            context = JsonApiContext(
                query_params=request.args,
                prefix=prefix,
                collection_path_builder=_collection_path,
                instance_path_builder=_instance_path,
                relationship_path_builder=_relationship_path,
            )
            g._safrs_jsonapi_context_token = set_jsonapi_context(context)
            # Keep backward-compatible aliases for existing code paths.
            g.ja_data = context.ja_data
            g.ja_included = context.ja_included

        @app.teardown_request
        def reset_ja_data(_exception: Any=None) -> Any:
            token = getattr(g, "_safrs_jsonapi_context_token", None)
            if token is not None:
                reset_jsonapi_context(token)
            return None

        # pylint: disable=unused-argument,unused-variable
        @app.teardown_appcontext
        def shutdown_session(exception: Any=None) -> Any:
            """cfr. http://flask.pocoo.org/docs/0.12/patterns/sqlalchemy/"""
            self.db.session.remove()

    @staticmethod
    def init_logging(loglevel: int = logging.WARNING) -> logging.Logger:
        """
        Specify the log format used in the webserver logs
        The webserver will catch stdout so we redirect eveything to sys.stdout
        """
        log = logging.getLogger(__name__)
        if log.level == logging.NOTSET:
            handler = logging.StreamHandler(sys.stderr)
            formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")
            handler.setFormatter(formatter)
            log.setLevel(loglevel)
            log.addHandler(handler)
        return log


def dict_merge(dct: dict[str, Any], merge_dct: dict[Any, Any]) -> None:
    """Recursive dict merge used for creating the swagger spec.
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


def test_decorator(func: Any) -> Any:  # pragma: no cover
    """Example flask-restful decorator that can be used in the "decorators" Api argument
    cfr. https://flask-restful.readthedocs.io/en/latest/api.html#id1
    """

    @wraps(func)
    def api_wrapper(*args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)

    if func.__name__.lower() == "get":
        result = api_wrapper
        return result

    return func


#
# DB and logging initialization
#
DB = SQLAlchemy()

LOGLEVEL = _resolve_loglevel()

log = SAFRS.init_logging(LOGLEVEL)
