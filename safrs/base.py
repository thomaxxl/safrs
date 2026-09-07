# base.py: implements the SAFRSBase SQLAlchemy db Mixin and related operations
#
# pylint: disable=logging-format-interpolation,no-self-argument,no-member,line-too-long,fixme,protected-access
#
"""
SAFRSBase class customizable attributes and methods, override these to customize the behavior of the SAFRSBase class.

http_methods:
Type: List[str]
A list of HTTP methods that are allowed for this class when exposed in the API.
Common methods include 'GET', 'POST', 'PUT', 'DELETE', etc.
This property controls the types of operations that can be performed on instances
of the class via the API.
             
             
_s_post:
Type: classmethod
Description: Called when a new item is created with a POST to the JSON:API.


_s_patch:
Type: method
Description: Updates the object attributes.


_s_delete:
Type: method
Description: Deletes the instance from the database.


_s_get:
Type: classmethod
Description: Called when a collection is requested with an HTTP GET to the JSON:API.


_s_expose:
Type: bool
Description: Indicates whether this class should be exposed in the API.


_s_upsert:
Type: bool
Description: Indicates whether to look up and use existing objects during creation.


_s_allow_add_rels:
Type: bool
Description: Allows relationships to be added in POST requests.


_s_pk_delimiter:
Type: str
Description: Delimiter used for primary keys.


_s_url_root:
Type: Optional[str]
Description: URL prefix shown in the "links" field. If not set, request.url_root will be used.


_s_columns:
Type: classproperty
Description: List of columns that are exposed by the API.


_s_relationships:
Type: hybrid_property
Description: Dictionary of relationships used for JSON:API (de)serialization.


_s_jsonapi_attrs:
Type: hybrid_property
Description: Dictionary of exposed attribute names and values.


_s_auto_commit:
Type: classproperty
Description: Indicates whether the instance should be automatically committed.


_s_check_perm:
Type: hybrid_method
Description: Checks the (instance-level) column permission.


_s_jsonapi_encode:
Type: hybrid_method
Description: Encodes the object according to the JSON:API specification.


_s_get_related:
Type: method
Description: Returns a dictionary of relationship names to related instances.


_s_count:
Type: classmethod
Description: Returns the count of instances in the table.


_s_sample_dict:
Type: classmethod
Description: Returns a sample dictionary to be used as an example "attributes" payload in the Swagger example.


_s_object_id:
Type: classproperty
Description: Returns the Flask URL parameter name of the object.


_s_get_jsonapi_rpc_methods:
Type: classmethod
Description: Returns a list of JSON:API RPC methods for this class.


_s_get_swagger_doc:
Type: classmethod
Description: Returns the Swagger body and response dictionaries for the specified HTTP method.


_s_sample_id:
Type: classmethod
Description: Returns a sample ID for the API documentation.


_s_url:
Type: hybrid_property
Description: Returns the endpoint URL of this instance.


_s_meta:
Type: classmethod
Description: Returns the "meta" part of the response.


_s_query:
Type: classproperty
Description: Returns the SQLAlchemy query object.


_s_class_name:
Type: classproperty
Description: Returns the name of the instances.


_s_collection_name:
Type: classproperty
Description: Returns the name of the collection, used to construct the endpoint.


_s_type:
Type: classproperty
Description: Returns the JSON:API "type", i.e., the table name if this is a DB model, the class name otherwise.


_s_expunge:
Type: method
Description: Expunges an object from its session.


_s_get_instance_by_id:
Type: classmethod
Description: Returns the query object for the specified JSON:API ID.


_s_parse_attr_value:
Type: method
Description: Parses the given JSON:API attribute value so it can be stored in the DB.

_s_clone:
Type: method
Description: Clones an object by copying the parameters and creating a new ID.


_s_filter:
Type: classmethod
Description: Applies filters to the query.
"""
from __future__ import annotations
from contextvars import ContextVar, Token
from typing import Any, cast, Callable, Optional
import inspect
import datetime
import sqlalchemy
import json
from http import HTTPStatus
from urllib.parse import urljoin, quote
from flask import request, url_for, has_request_context, has_app_context, current_app, g
from flask_sqlalchemy.model import Model
from sqlalchemy.orm.session import make_transient
from sqlalchemy import inspect as sqla_inspect
from sqlalchemy.orm.interfaces import ONETOMANY, MANYTOONE, MANYTOMANY
from sqlalchemy.ext.hybrid import hybrid_method, hybrid_property
from sqlalchemy.sql.schema import Column
from functools import lru_cache

# safrs dependencies:
import safrs
from werkzeug.exceptions import HTTPException
from .errors import GenericError, IntegerOverflowError, JsonapiError, NotFoundError, UnAuthorizedError, ValidationError, SystemValidationError
from .safrs_types import get_id_type
from .attr_parse import parse_attr
from .config import get_config
from .jsonapi_filters import jsonapi_filter
from .jsonapi_attr import (
    get_jsonapi_attrs,
    is_jsonapi_attr,
    jsonapi_attr_is_read_only,
    jsonapi_attr_is_write_only,
    lookup_jsonapi_attr,
)
from .api_doc import get_doc
from .util import ClassPropertyDescriptor, classproperty
from .model_config import SAFRSModelConfig
from .jsonapi_context import maybe_jsonapi_context
from .filtering import apply_filter_json, materialize_for_authorization
from .authorization import (
    apply_authorization_scope,
    begin_current_protected_write,
    current_model_is_registered,
    current_query_fields,
    current_readable_fields,
    prepare_current_readable_fields,
    prepare_current_delete,
    require_current_create,
    require_current_instance,
    reject_current_relationship_fields,
    reject_current_relationship_mutation,
    reject_current_rpc,
    reject_current_foreign_key_fields,
    run_current_after_create,
)
from . import tx
from .runtime import get_db

_MISSING_FLASK_ADAPTER_DEPS = {"flask_restful", "flask_restful_swagger_2"}
_safrs_jsonapi: Any = None
_POST_UPSERT_PRECHECKED: ContextVar[Any] = ContextVar("safrs_post_upsert_prechecked", default=None)

try:
    from . import jsonapi as _loaded_safrs_jsonapi
except ModuleNotFoundError as exc:
    if exc.name not in _MISSING_FLASK_ADAPTER_DEPS:
        raise
else:
    _safrs_jsonapi = _loaded_safrs_jsonapi


# Mapping of legacy "_s_" class attributes to SAFRSModelConfig field names.
_LEGACY_SAFRS_CONFIG_MAP = {
    "_s_expose": "expose",
    "_s_upsert": "upsert",
    "_s_allow_add_rels": "allow_add_rels",
    "_s_pk_delimiter": "pk_delimiter",
    "_s_url_root": "url_root",
    "_s_stateless": "stateless",
}


def _request_uow_active() -> bool:
    if tx.in_request():
        return True
    try:
        session_info = getattr(get_db().session, "info", None)
    except Exception:
        return False
    return isinstance(session_info, dict) and bool(session_info.get("_safrs_uow_active", False))


def _has_id_value(value: Any) -> bool:
    return value is not None and (not isinstance(value, str) or value != "")


@lru_cache(maxsize=1024)
def _resolve_safrs_model_config(model_cls: type) -> SAFRSModelConfig:
    """Resolve a model's SAFRS configuration.

    Resolution order is MRO-based: base classes first, subclasses last.

    Supported override styles per class:
    - ``class SAFRSConfig: ...`` nested class with attributes matching config fields.
    - ``__safrs_config__`` attribute containing a SAFRSModelConfig or a dict of overrides.
    - legacy ``_s_*`` class attributes.

    Notes:
    - The result is cached. If you mutate overrides at runtime, call
      ``SAFRSBase._s_clear_config_cache()``.
    """
    cfg = SAFRSModelConfig()
    field_names = set(cfg.__dataclass_fields__.keys())

    for base in reversed(getattr(model_cls, "__mro__", ())):
        if base is object:
            continue

        # Full config / dict overrides
        raw_cfg = getattr(base, "__dict__", {}).get("__safrs_config__", None)
        if isinstance(raw_cfg, SAFRSModelConfig):
            cfg = raw_cfg
        elif isinstance(raw_cfg, dict):
            cfg = cfg.with_overrides(raw_cfg)

        # Nested class overrides: class SAFRSConfig: expose = ...
        cfg_cls = getattr(base, "__dict__", {}).get("SAFRSConfig", None)
        if cfg_cls is not None:
            overrides = {}
            for name in field_names:
                if hasattr(cfg_cls, name):
                    overrides[name] = getattr(cfg_cls, name)
            cfg = cfg.with_overrides(overrides)

        # Legacy overrides: _s_expose, _s_pk_delimiter, ...
        legacy_overrides = {}
        base_dict = getattr(base, "__dict__", {})
        for legacy_attr, field_name in _LEGACY_SAFRS_CONFIG_MAP.items():
            if legacy_attr not in base_dict:
                continue
            value = base_dict[legacy_attr]
            # SAFRSBase defines some of these as classproperties.
            # Only treat concrete values (bool/str/None/...) as legacy overrides.
            if isinstance(value, ClassPropertyDescriptor):
                continue
            legacy_overrides[field_name] = value
        cfg = cfg.with_overrides(legacy_overrides)

    return cfg

#
# Map SQLA types to swagger2 json types
# json supports only a couple of basic data types, which makes our job pretty easy :)
# If a type isn't found in the table, "string" will be used
# (because of this we could actually remove all the "string" types as well)
#
SQLALCHEMY_SWAGGER2_TYPE = {
    "INTEGER": "integer",
    "SMALLINT": "integer",
    "NUMERIC": "number",
    "DECIMAL": "integer",
    "VARCHAR": "string",
    "TEXT": "string",
    "DATE": "string",
    "BOOLEAN": "boolean",
    "BLOB": "string",
    "BYTEA": "string",
    "BINARY": "string",
    "VARBINARY": "string",
    "FLOAT": "number",
    "REAL": "number",
    "DATETIME": "string",
    "BIGINT": "integer",
    "ENUM": "string",
    "INTERVAL": "string",
    "CHAR": "string",
    "TIMESTAMP": "string",
    "TINYINT": "integer",
    "MEDIUMINT": "integer",
    "NVARCHAR": "string",
    "YEAR": "integer",
    "SET": "string",
    "LONGBLOB": "string",
    "TINYTEXT": "string",
    "LONGTEXT": "string",
    "MEDIUMTEXT": "string",
    "UUID": "string",
    "TIME": "string",
}
# casting of swagger types to python types
SWAGGER2_TYPE_CAST = {"integer": int, "string": str, "number": float, "boolean": bool}


def _instance_route_decorators(model: Any, action: str = "read") -> list[Any]:
    """Route decorators protecting the model operation for ``action``.

    Combines the decorators configured when the model was exposed
    (``method_decorators`` recorded by the SafrsApi instance) and the
    model's class-level ``decorators``/``custom_decorators``.
    """
    decorators: list[Any] = []
    safrs_api = None
    if has_app_context():
        safrs_api = current_app.extensions.get("safrs_api")
    if safrs_api is None:
        safrs_api = getattr(model, "_safrs_api", None)
    if safrs_api is not None:
        configured = getattr(safrs_api, "_model_method_decorators", {}).get(model, [])
        if isinstance(configured, dict):
            operation = {
                "read": "get",
                "link": "patch",
                "unlink": "patch",
                "update": "patch",
                "cascade_delete": "delete",
            }.get(action, "get")
            configured = configured.get(operation, [])
        decorators.extend(list(configured or []))
    decorators.extend(list(getattr(model, "custom_decorators", []) or []))
    decorators.extend(list(getattr(model, "decorators", []) or []))
    seen: set[int] = set()
    result: list[Any] = []
    for decorator in decorators:
        if id(decorator) in seen:
            continue
        seen.add(id(decorator))
        result.append(decorator)
    return result


def run_instance_access_check(
    model: Any,
    instance: Any,
    action: str = "read",
    quiet: bool = False,
) -> bool:
    """SEC-02: authorize a row loaded through a relationship payload, an
    include traversal, a nested write or a cascade operation.

    Two policies are evaluated against the concrete row:

    1. the model's object-level hook ``_s_check_instance_access(action)``;
    2. for reads, explicitly registered ``response_authorizer`` callbacks.

    Ordinary Flask route decorators run once at the route/operation boundary;
    they are never replayed once per returned read resource.  Legacy write
    target checks continue to use their operation-specific decorators.

    Fail closed: an unexpected error in either policy denies access. With
    ``quiet=True`` (non-mutating include traversal) a denied row is reported
    as ``False`` instead of raising so it can be omitted from the response.
    """
    if instance is None:
        return True

    cache_key: Optional[tuple[Any, str, str]] = None
    flask_cache: Optional[set[tuple[Any, str, str]]] = None
    if has_request_context():
        cache_key = (model, str(getattr(instance, "jsonapi_id", "")), action)
        flask_cache = getattr(g, "_safrs_instance_access_cache", None)
        if flask_cache is None:
            flask_cache = set()
            g._safrs_instance_access_cache = flask_cache
        if cache_key in flask_cache:
            return True

    registry_action = {
        "link": "update",
        "unlink": "update",
        "cascade_delete": "delete",
    }.get(action, action)
    require_current_instance(instance, registry_action)

    ctx = maybe_jsonapi_context()
    if ctx is not None and ctx.resource_authorizer is not None:
        # Explicit response policies reject the whole document, even for
        # includes: quietly dropping a row would leave counts/links observable.
        ctx.resource_authorizer(model, instance, action)

    def deny() -> None:
        if not quiet:
            raise UnAuthorizedError(
                f"{getattr(model, '_s_type', model)} instance is not authorized for '{action}'"
            )

    hook = getattr(instance, "_s_check_instance_access", None)
    if not callable(hook):
        hook = None
    if hook is not None:
        try:
            allowed = hook(action)
        except JsonapiError:
            if quiet:
                return False
            raise
        except Exception as exc:
            safrs.log.debug(
                "Instance access check failed for %s (%s)",
                getattr(model, "__name__", model),
                type(exc).__name__,
            )
            deny()
            return False
        if not allowed:
            deny()
            return False

    if action == "read" and has_request_context():
        safrs_api = current_app.extensions.get("safrs_api")
        callbacks = getattr(safrs_api, "_response_authorizers", {}).get(model, [])
        for callback in callbacks:
            try:
                allowed = callback(model, instance, request)
            except JsonapiError:
                if quiet:
                    return False
                raise
            except Exception as exc:
                safrs.log.debug(
                    "Response authorization failed for %s: %s",
                    getattr(model, "__name__", model),
                    type(exc).__name__,
                )
                deny()
                return False
            if allowed is False:
                deny()
                return False

    if not has_request_context():
        return True
    if action == "read":
        if flask_cache is not None and cache_key is not None:
            flask_cache.add(cache_key)
        return True
    decorators = _instance_route_decorators(model, action)
    if not decorators:
        if flask_cache is not None and cache_key is not None:
            flask_cache.add(cache_key)
        return True

    object_id_name = str(getattr(model, "_s_object_id", "id"))

    def _authorized_view(*args: Any, **kwargs: Any) -> Any:
        return instance

    _authorized_view.__name__ = {
        "read": "get",
        "link": "patch",
        "unlink": "patch",
        "update": "patch",
        "cascade_delete": "delete",
    }.get(action, "get")
    setattr(_authorized_view, "SAFRSObject", model)
    decorated = _authorized_view
    for decorator in decorators:
        decorated = decorator(decorated)
    try:
        decorated(**{object_id_name: quote(str(getattr(instance, "jsonapi_id", "")), safe="")})
    except (JsonapiError, HTTPException):
        if quiet:
            return False
        raise
    except Exception as exc:
        safrs.log.debug(
            "Instance policy check failed for %s (%s)",
            getattr(model, "__name__", model),
            type(exc).__name__,
        )
        deny()
        return False
    if flask_cache is not None and cache_key is not None:
        flask_cache.add(cache_key)
    return True


def run_model_operation_access_check(model: Any, action: str) -> None:
    """Run a Flask model's ordinary decorators once for a routed operation."""
    if not has_request_context():
        return
    cache = getattr(g, "_safrs_operation_access_cache", None)
    if cache is None:
        cache = set()
        g._safrs_operation_access_cache = cache
    cache_key = (model, action)
    if cache_key in cache:
        return
    decorators = _instance_route_decorators(model, action)
    if not decorators:
        cache.add(cache_key)
        return

    def authorized_operation(*_args: Any, **_kwargs: Any) -> bool:
        return True

    authorized_operation.__name__ = {
        "read": "get",
        "create": "post",
        "update": "patch",
        "delete": "delete",
    }.get(action, "get")
    setattr(authorized_operation, "SAFRSObject", model)
    decorated = authorized_operation
    for decorator in decorators:
        decorated = decorator(decorated)
    decorated()
    cache.add(cache_key)


def run_relationship_read_access_check(relationship: Any) -> None:
    """Run direct relationship decorators when that relationship is included."""
    if not has_request_context():
        return
    decorators = list(getattr(relationship, "decorators", []) or [])
    if not decorators:
        return
    cache = getattr(g, "_safrs_relationship_access_cache", None)
    if cache is None:
        cache = set()
        g._safrs_relationship_access_cache = cache
    cache_key = id(relationship)
    if cache_key in cache:
        return

    def authorized_relationship(*_args: Any, **_kwargs: Any) -> bool:
        return True

    authorized_relationship.__name__ = "get"
    decorated = authorized_relationship
    for decorator in decorators:
        decorated = decorator(decorated)
    decorated()
    cache.add(cache_key)


def check_relationship_write_permission(instance: Any, relationship_name: str) -> None:
    """Authorize mutation of a relationship on its concrete parent row.

    Relationship endpoints and nested JSON:API writes must check the
    relationship's ``"w"`` permission explicitly.  Looking the relationship
    up through ``_s_relationships`` is insufficient because that property is
    filtered using read permission.
    """
    try:
        allowed = bool(instance._s_check_perm(relationship_name, "w"))
    except Exception as exc:
        safrs.log.debug(
            "Relationship write permission check failed for %s.%s: %s",
            instance.__class__.__name__,
            relationship_name,
            type(exc).__name__,
        )
        allowed = False
    if not allowed:
        resource_type = getattr(instance.__class__, "_s_type", instance.__class__.__name__)
        raise UnAuthorizedError(
            f"{resource_type}.{relationship_name} is not writable"
        )
    mapper = sqlalchemy.inspect(instance.__class__, raiseerr=False)
    relationship = mapper.relationships.get(relationship_name) if mapper is not None else None
    if relationship is not None:
        reject_current_relationship_mutation(instance.__class__, relationship.mapper.class_)


def model_has_resource_authorization(model: Any) -> bool:
    """Return whether collection metadata requires per-resource checks."""
    hook_owner = next(
        (
            base
            for base in getattr(model, "__mro__", ())
            if "_s_check_instance_access" in getattr(base, "__dict__", {})
        ),
        None,
    )
    callbacks: list[Any] = []
    if has_app_context():
        safrs_api = current_app.extensions.get("safrs_api")
        callbacks = getattr(safrs_api, "_response_authorizers", {}).get(model, [])
    return hook_owner is not SAFRSBase or bool(callbacks)


def authorize_collection_before_metadata(model: Any, resources: Any) -> Any:
    """Authorize every candidate before count, sorting, and pagination.

    Arbitrary Python object policies cannot be translated to SQL safely.  For
    models that define one, materialization is the secure fallback: a denied
    row rejects the document before its existence can leak through metadata.
    Applications with large collections should enforce the same policy in
    their query hook so the database can scope rows efficiently.
    """
    resources = apply_authorization_scope(
        model, resources, fields=current_query_fields(model)
    )
    if not model_has_resource_authorization(model):
        return resources
    items = materialize_for_authorization(resources)
    for item in items:
        run_instance_access_check(model, item, "read")
    return items


#
# SAFRSBase superclass
#
class SAFRSBase(Model):
    """This SQLAlchemy mixin implements json:api serialization for SAFRS SQLalchemy Persistent Objects
    Serialization itself is performed by the ``to_dict`` method
    Initialization and instantiation are quite complex because we rely on the DB schema

    The jsonapi id is generated from the primary keys of the columns

    This class is mostly used as a sqla model mixin therefore the object attributes should not
    match column names or sqla attribute names, this is why most of the methods & properties have
    (or should have, hindsight is great :/) the distinguishing `_s_` prefix
    """

    # Per-model request-boundary auto-commit switch (default on). This flag is
    # evaluated by safrs.tx on each write and only concrete-class values are
    # honored (inherited values are intentionally ignored).
    db_commit = True
    url_prefix = ""
    allow_client_generated_ids = False  # Indicates whether the client is allowed to create the id
    exclude_attrs: list[str] = []  # list of attribute names that should not be serialized
    exclude_rels: list[str] = []  # list of relationship names that should not be serialized
    supports_includes = True  # Set to False if you don't want this class to return included items

    # The swagger models are kept here, this lookup table will be used when the api swagger is generated
    # on startup
    swagger_models = {"instance": None, "collection": None}
    jsonapi_filter = jsonapi_filter  # filtering implementation

    # Cached lookup tables
    _col_attr_name_map = None
    _attr_col_name_map = None

    # Resource classes for the collections, relationships and methods
    # overriding these allows you to extend the Resource http methods: get(), post(), patch(), delete()
    _rest_api = _safrs_jsonapi.SAFRSRestAPI if _safrs_jsonapi is not None else None
    _relationship_api = _safrs_jsonapi.SAFRSRestRelationshipAPI if _safrs_jsonapi is not None else None
    _rpc_api = _safrs_jsonapi.SAFRSJSONRPCAPI if _safrs_jsonapi is not None else None

    @classproperty
    def safrs_config(cls: Any) -> SAFRSModelConfig:
        """Resolved configuration for this SAFRS model class."""
        return _resolve_safrs_model_config(cls)

    @classmethod
    def _s_clear_config_cache(cls: Any) -> None:
        """Clear the SAFRS model config cache.

        Use this if you mutate configuration overrides at runtime.
        """
        _resolve_safrs_model_config.cache_clear()

    @classproperty
    def _s_expose(cls: Any) -> bool:
        """Indicates whether this class should be exposed in the API."""
        return bool(cls.safrs_config.expose)

    @classproperty
    def _s_upsert(cls: Any) -> bool:
        """Indicates whether to look up and use existing objects during creation."""
        return bool(cls.safrs_config.upsert)

    @classproperty
    def _s_allow_add_rels(cls: Any) -> bool:
        """Allows relationships to be added in POST requests."""
        return bool(cls.safrs_config.allow_add_rels)

    @classproperty
    def _s_pk_delimiter(cls: Any) -> str:
        """Delimiter used to concatenate primary key values in jsonapi ids."""
        return str(cls.safrs_config.pk_delimiter)

    @classproperty
    def _s_url_root(cls: Any) -> Any:
        """URL prefix shown in the JSON:API "links" field."""
        return cls.safrs_config.url_root

    # ---------------------------------------------------------------------
    # Phase 2: Hook infrastructure (no behavior changes yet)
    # ---------------------------------------------------------------------
    @classmethod
    def _s_get_class_hook(cls: Any, name: str) -> Optional[Callable[..., Any]]:
        """Return a class-level hook override by name, if configured."""
        hooks = getattr(cls.safrs_config, "hooks", None)
        if not hooks:
            return None
        return hooks.get(name)

    def _s_get_hook(self: Any, name: str) -> Optional[Callable[..., Any]]:
        """Return an instance-level hook override by name.

        Instance hooks take precedence over class hooks.
        """
        inst_hooks = cast(Optional[dict[str, Callable[..., Any]]], getattr(self, "__safrs_instance_hooks__", None))
        if inst_hooks and name in inst_hooks:
            return inst_hooks[name]
        return self.__class__._s_get_class_hook(name)

    def _s_set_hook(self: Any, name: str, fn: Callable[..., Any]) -> None:
        """Set an instance-level hook override."""
        inst_hooks = cast(Optional[dict[str, Callable[..., Any]]], getattr(self, "__safrs_instance_hooks__", None))
        if inst_hooks is None:
            inst_hooks = {}
            setattr(self, "__safrs_instance_hooks__", inst_hooks)
        inst_hooks[name] = fn

    included_list = None

    def __new__(cls: Any, *args: Any, **kwargs: Any) -> Any:
        """
        If an object with given arguments already exists, this object is instantiated
        """
        if _POST_UPSERT_PRECHECKED.get() is cls or "id" not in kwargs or not cls._s_upsert:
            return object.__new__(cls)
        # Fetch the PKs from the kwargs so we can lookup the corresponding object
        primary_keys = cls.id_type.extract_pks(kwargs)

        # Lookup the object with the PKs
        instance = None
        try:
            instance = cls._s_query.filter_by(**primary_keys).one_or_none()
        except Exception as exc:  # pragma: no cover
            safrs.log.warning("Upsert lookup failed (%s)", type(exc).__name__)

        if instance is None:
            instance = object.__new__(cls)

        return instance

    def __init__(self: Any, *args: Any, **kwargs: Any) -> None:
        """
        Object initialization, called from backend or `_s_post`
        - set the named attributes and add the object to the database
        - create relationships
        :param args:
        :param kwargs: model attributes (column & relationship values)
        """
        # All SAFRSBase subclasses have a jsonapi id, passed as "id" in web requests
        # if no id is supplied, generate a new safrs id (uuid4)
        # instantiate the id with the "id_type", this will validate the id if
        # validation is implemented
        kwargs["id"] = self.id_type(kwargs.get("id", None))

        # Initialize the attribute values: these have been passed as key-value pairs in the
        # kwargs dictionary (from json in case of a web request).
        # Retrieve the values from each attribute (== class table column)
        db_args = {}
        column_names = [c.key for c in self._s_columns]
        for name, val in kwargs.items():
            if name in self._s_relationships:
                # Add the related instances
                db_args[name] = val
            elif is_jsonapi_attr(lookup_jsonapi_attr(self.__class__, name)):
                # Set jsonapi attributes
                attr_val = self._s_parse_attr_value(name, val)
                self._s_set_jsonapi_attr(name, attr_val)
            elif name in column_names:
                # Set columns
                attr_val = self._s_parse_attr_value(name, val)
                db_args[name] = attr_val
            elif name in self.__class__._s_jsonapi_attrs:
                db_args[name] = self._s_parse_attr_value(name, val)

        # db_args now contains the class attributes. Initialize the DB model with them
        # All subclasses should have the DB.Model as superclass.
        # (SQLAlchemy doesn't work when using DB.Model as SAFRSBase superclass)
        try:
            get_db().Model.__init__(self, **db_args)
        except (TypeError, ValueError) as exc:
            # Never retry with an empty constructor.  Doing so can turn a
            # rejected client value into a privileged database default.
            raise ValidationError("Invalid model attributes") from exc

    def __setattr__(self: Any, attr_name: Any, attr_val: Any) -> Any:
        """
        setattr behaves differently for `jsonapi_attr` decorated attributes
        """
        if attr_name == "Type" and hasattr(self, "type"):
            # check "Type" property for details
            attr_name = "type"
        attr = lookup_jsonapi_attr(self.__class__, attr_name)
        if jsonapi_attr_is_read_only(attr):
            raise AttributeError(f"Attribute '{attr_name}' is read-only")
        return super().__setattr__(attr_name, attr_val)

    def _s_set_jsonapi_attr(self: Any, attr_name: str, attr_val: Any) -> None:
        """
        Assign a jsonapi_attr and normalize common client-input failures.
        """
        try:
            setattr(self, attr_name, attr_val)
        except ValidationError:
            raise
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"Invalid value for attribute '{attr_name}'") from exc

    def _s_ignore_unchanged_readonly_jsonapi_attr(self: Any, attr_name: str, attr_val: Any) -> bool:
        """
        Allow PATCH round-trips that echo existing read-only computed values unchanged.
        """
        attr = self.__class__._s_jsonapi_attrs.get(attr_name)
        if not jsonapi_attr_is_read_only(attr):
            return False
        try:
            return getattr(self, attr_name) == attr_val
        except Exception:
            return False

    @staticmethod
    def _s_run_jsonapi_attr_parser(attr_name: str, attr: Any, attr_val: Any) -> Any:
        parser = getattr(attr, "parser", None)
        if not callable(parser):
            return attr_val
        try:
            return parser(attr_val)
        except ValidationError:
            raise
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"Invalid value for attribute '{attr_name}'") from exc

    @staticmethod
    def _s_run_jsonapi_attr_validator(attr_name: str, attr: Any, attr_val: Any) -> Any:
        validator = getattr(attr, "validator", None)
        if not callable(validator):
            return attr_val
        try:
            is_valid = validator(attr_val)
        except ValidationError:
            raise
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"Invalid value for attribute '{attr_name}'") from exc
        if is_valid is False:
            raise ValidationError(f"Invalid value for attribute '{attr_name}'")
        return attr_val

    @classmethod
    def _s_parse_attr_value_for_request(cls: Any, attr_name: str, attr_val: Any) -> Any:
        """
        Apply the canonical SAFRS request parsing rules to one attribute.

        Framework adapters should establish a JSON:API request context and let
        ``_s_post``/``_s_patch`` call this path instead of implementing their
        own coercion rules.
        """
        if attr_name == "id":
            return attr_val

        attr = cls._s_jsonapi_writable_attrs.get(attr_name)

        if attr is None:
            if attr_name in cls._s_jsonapi_attrs:
                raise ValidationError(f"Attribute '{attr_name}' is read-only")
            raise SystemValidationError(f"Unknown attribute: {attr_name}")

        if is_jsonapi_attr(attr):
            if jsonapi_attr_is_read_only(attr):
                raise ValidationError(f"Attribute '{attr_name}' is read-only")
            attr_val = cls._s_run_jsonapi_attr_parser(attr_name, attr, attr_val)
            attr_val = cls._s_run_jsonapi_attr_validator(attr_name, attr, attr_val)
            return attr_val

        # attr is a sqlalchemy.sql.schema.Column now
        if not isinstance(attr, Column):  # pragma: no cover
            raise SystemValidationError(f"Not a column: {attr}")

        return parse_attr(attr, attr_val)

    def _s_parse_attr_value(self: Any, attr_name: str, attr_val: Any) -> Any:
        """
        Parse the given jsonapi attribute value so it can be stored in the db
        :param attr_name: attribute name
        :param attr_val: attribute value
        :return: parsed value
        """
        # Don't allow attributes from web requests that are not specified in _s_jsonapi_attrs
        if not has_request_context() and maybe_jsonapi_context() is None:
            # Programmatic model construction remains unchanged; Flask and
            # FastAPI requests both activate the canonical request parser.
            return attr_val

        return self.__class__._s_parse_attr_value_for_request(attr_name, attr_val)

    @classmethod
    def _s_get(cls: Any, **kwargs: Any) -> Any:
        """
        This method is called when a collection is requested with a HTTP GET to the json api
        """
        return cls._s_query_scope(cls.jsonapi_filter())

    @classmethod
    def _s_query_scope(cls: Any, query_or_items: Any) -> Any:
        """Return rows whose existence the current caller may observe.

        Override this hook with a SQLAlchemy predicate whenever authorization
        varies by principal or row.  It runs before sorting, counting, and
        pagination in both adapters.  Per-object authorization remains a final
        fail-closed safety check.
        """
        return query_or_items

    @classmethod
    def _s_get_upsert_target(cls: Any, jsonapi_id: Any=None, **params: Any) -> Optional[SAFRSBase]:
        """Return the existing row selected by an explicitly supplied POST id.

        This lookup does not authorize or mutate the row. HTTP adapters must
        authorize the upsert operation before calling ``_s_update_from_post``.
        ``_s_post`` also uses it for trusted programmatic calls.
        """
        if not cls._s_upsert or not cls.allow_client_generated_ids:
            return None

        has_concrete_pks = all(_has_id_value(params.get(pk)) for pk in cls.id_type.column_names)
        if not _has_id_value(jsonapi_id) and not _has_id_value(params.get("id")) and not has_concrete_pks:
            return None

        lookup_params = dict(params)
        if _has_id_value(jsonapi_id):
            lookup_params["id"] = jsonapi_id
        try:
            primary_keys = cls.id_type.extract_pks(lookup_params)
        except KeyError:
            return None
        return cls._s_query.filter_by(**primary_keys).one_or_none()

    def _s_update_from_post(self: Any, **params: Any) -> SAFRSBase:
        """Apply the update branch of an authorized POST upsert.

        Reusing ``_s_patch`` preserves PATCH parsing, field permissions, hooks,
        and validation instead of re-running the SQLAlchemy constructor on a
        persistent instance. Authorization is performed by the HTTP adapter.
        """
        relationships = {name: value for name, value in params.items() if name in self._s_relationships}
        attributes = {name: value for name, value in params.items() if name not in self._s_relationships}
        self._s_patch(**attributes)
        self._add_rels(**relationships)
        return self

    @classmethod
    def _s_post_prechecked(cls: Any, jsonapi_id: Any=None, **params: Any) -> SAFRSBase:
        """Create after an HTTP adapter has already resolved the upsert id.

        The context flag suppresses both lookup sites used by the historical
        programmatic upsert path: ``_s_post`` and ``__new__``. If another
        transaction inserts the id after the adapter's lookup, the insert now
        fails with a constraint conflict instead of silently updating a row
        without update authorization.
        """
        token: Token[Any] = _POST_UPSERT_PRECHECKED.set(cls)
        try:
            return cls._s_post(jsonapi_id=jsonapi_id, **params)
        finally:
            _POST_UPSERT_PRECHECKED.reset(token)

    @classmethod
    def _s_post(cls: Any, jsonapi_id: Any=None, **params: Any) -> SAFRSBase:
        """
        This method is called when a new item is created with a POST to the json api

        :param attributes: the jsonapi "data" attributes
        :return: new `cls` instance

        `_s_post` performs attribute sanitization and calls `cls.__init__`
        The attributes may contain an "id" if `cls.allow_client_generated_ids` is True

        When upsert is enabled and the explicit id already exists, trusted
        programmatic calls update it through ``_s_patch``. HTTP adapters detect
        and authorize this branch before invoking it.
        """
        if _POST_UPSERT_PRECHECKED.get() is not cls:
            upsert_target = cls._s_get_upsert_target(jsonapi_id, **params)
            if upsert_target is not None:
                return upsert_target._s_update_from_post(**params)

        mapper = sqlalchemy.inspect(cls)
        relationship_names = {str(relationship.key) for relationship in mapper.relationships}
        reject_current_relationship_fields(cls, params.keys())
        submitted_fields = [
            name for name in params if name not in relationship_names and name != "id"
        ]
        reject_current_foreign_key_fields(cls, submitted_fields)
        require_current_create(cls, submitted_fields, params)

        readonly_jsonapi_attrs = {
            attr_name
            for attr_name, attr in get_jsonapi_attrs(cls).items()
            if jsonapi_attr_is_read_only(attr)
        }
        for attr_name in params:
            if attr_name in readonly_jsonapi_attrs:
                raise ValidationError(f"Attribute '{attr_name}' is read-only")

        # Only accept attributes that are explicitly writable.  ``_s_jsonapi_attrs``
        # is the response/read set and may contain read-only columns.
        attributes = {attr_name: params[attr_name] for attr_name in params if attr_name in cls._s_jsonapi_writable_attrs}

        # Remove 'id' (or other primary keys) from the attributes, unless it is allowed by the
        # SAFRSObject allow_client_generated_ids attribute
        if cls.allow_client_generated_ids:
            # Prefer JSON:API resource id and map it to concrete PK column names.
            # This prevents KeyError crashes when PK columns are named differently
            # (for example "Id" or composite keys).
            client_generated_id = jsonapi_id if jsonapi_id is not None else params.get("id", None)
            if _has_id_value(client_generated_id):
                parsed_pks = cls.id_type.get_pks(client_generated_id)
                missing_pk = [pk for pk in cls.id_type.column_names if not _has_id_value(parsed_pks.get(pk))]
                if missing_pk:
                    raise ValidationError("Missing resource id", HTTPStatus.BAD_REQUEST.value)
                attributes["id"] = client_generated_id
                attributes.update(parsed_pks)
            else:
                missing_pk = [pk for pk in cls.id_type.column_names if not _has_id_value(attributes.get(pk))]
                if missing_pk:
                    raise ValidationError("Missing resource id", HTTPStatus.BAD_REQUEST.value)
                synthesized_id = cls.id_type.delimiter.join(str(attributes[pk]) for pk in cls.id_type.column_names)
                attributes["id"] = synthesized_id
        else:
            for attr_name in attributes.copy():
                if attr_name in cls.id_type.column_names:
                    safrs.log.warning(f"Client generated IDs are not allowed ('allow_client_generated_ids' not set for {cls})")
                    del attributes[attr_name]

        # Create the object instance with the specified id and json data
        # If the instance (id) already exists, it will be updated with the data
        # pylint: disable=not-callable
        instance = cls(**attributes)

        # Class-level permission checks select the candidate constructor
        # fields. Re-check them on the initialized instance because documented
        # permission hooks may make caller- or row-dependent decisions. PATCH
        # already performs this instance check before assigning each field.
        protected_id_names = {"id", *cls.id_type.column_names}
        denied_attributes = [
            attr_name
            for attr_name in attributes
            if attr_name not in protected_id_names and not instance._s_check_perm(attr_name, "w")
        ]
        if denied_attributes:
            denied_csv = ", ".join(sorted(denied_attributes))
            raise ValidationError(
                f"Write access denied for attribute(s): {denied_csv}",
                HTTPStatus.FORBIDDEN.value,
            )

        # Nested resources need their own lookup/authorization decision. Do
        # not let this create's precheck suppress an upsert lookup for a
        # relationship payload (including a self-referential relationship).
        relationship_token: Optional[Token[Any]] = None
        if _POST_UPSERT_PRECHECKED.get() is cls:
            relationship_token = _POST_UPSERT_PRECHECKED.set(None)
        try:
            instance._add_rels(**params)
        finally:
            if relationship_token is not None:
                _POST_UPSERT_PRECHECKED.reset(relationship_token)

        if not instance in get_db().session:
            get_db().session.add(instance)
        tx.note_write(cls)
        if _request_uow_active():
            try:
                get_db().session.flush()
            except sqlalchemy.exc.IntegrityError:
                get_db().session.rollback()
                raise ValidationError("Database constraint violation", HTTPStatus.CONFLICT.value)
            except (sqlalchemy.exc.DataError, sqlalchemy.exc.StatementError):
                get_db().session.rollback()
                raise ValidationError("Invalid attribute value")
            except OverflowError:
                get_db().session.rollback()
                raise ValidationError("Invalid attribute value")
            except sqlalchemy.exc.SQLAlchemyError as exc:  # pragma: no cover
                # Keep true server/database failures as 500 responses.
                get_db().session.rollback()
                safrs.log.warning("Database write failed (%s)", type(exc).__name__)
                raise GenericError(str(exc))

        run_current_after_create(instance)

        return instance

    def _s_patch(self: Any, **attributes: Any) -> SAFRSBase:
        """
        Update the object attributes
        :param **attributes:
        """
        reject_current_foreign_key_fields(self.__class__, attributes.keys())
        require_current_instance(self, "update", attributes.keys())
        for attr_name, attr_val in attributes.items():
            if (
                attr_name not in self.__class__._s_jsonapi_attrs
                and attr_name not in self.__class__._s_jsonapi_writable_attrs
            ):
                continue
            # check if we have permission to write
            if not self._s_check_perm(attr_name, "w"):
                continue
            if self._s_ignore_unchanged_readonly_jsonapi_attr(attr_name, attr_val):
                continue
            attr_val = self._s_parse_attr_value(attr_name, attr_val)
            if is_jsonapi_attr(self.__class__._s_jsonapi_attrs.get(attr_name)):
                self._s_set_jsonapi_attr(attr_name, attr_val)
            else:
                setattr(self, attr_name, attr_val)

        tx.note_write(self.__class__)
        if _request_uow_active():
            try:
                get_db().session.flush()
            except sqlalchemy.exc.IntegrityError:
                get_db().session.rollback()
                raise ValidationError("Database constraint violation", HTTPStatus.CONFLICT.value)
            except (sqlalchemy.exc.DataError, sqlalchemy.exc.StatementError, OverflowError):
                get_db().session.rollback()
                raise ValidationError("Invalid attribute value")
        # query ourself, this will also execute sqla hooks
        return self.get_instance(self.jsonapi_id)

    def _s_delete(self: Any) -> None:
        """
        Delete the instance from the database
        """
        prepare_current_delete(self)
        if _request_uow_active():
            self.__class__._s_validate_cascade_delete_methods(self)
        tx.note_write(self.__class__)
        get_db().session.delete(self)
        if _request_uow_active():
            get_db().session.flush()

    def _add_rels(self: Any, **params: Any) -> None:
        """
        Add relationship data provided in a POST, cfr. https://jsonapi.org/format/#crud-creating
        **params contains the (HTTP POST) parameters

        only works if self._s_allow_add_rels was set.
        """

        def data2inst(data: Any, target_class: Any) -> Any:
            if not isinstance(data, dict) or "id" not in data or "type" not in data:
                raise ValidationError("Invalid relationship resource identifier")
            if data["type"] != target_class._s_type:
                raise ValidationError("Invalid relationship resource type")
            attributes = data.get("attributes", {})
            relationships = data.get("relationships", {})
            if not isinstance(attributes, dict) or not isinstance(relationships, dict):
                raise ValidationError("Invalid relationship resource payload")
            if _request_uow_active():
                upsert_target = target_class._s_get_upsert_target(data["id"], **attributes)
                if upsert_target is not None:
                    if not target_class._s_supports_http_method("PATCH"):
                        raise ValidationError(
                            f"PATCH is not allowed for related resource {target_class.__name__}",
                            HTTPStatus.METHOD_NOT_ALLOWED.value,
                        )
                    # SEC-02: the nested upsert reads and rewrites an existing
                    # target row; enforce its object-level policy first.
                    run_instance_access_check(target_class, upsert_target, "link")
                    return upsert_target._s_update_from_post(**attributes, **relationships)
                if not target_class._s_supports_http_method("POST"):
                    raise ValidationError(
                        f"POST is not allowed for related resource {target_class.__name__}",
                        HTTPStatus.METHOD_NOT_ALLOWED.value,
                    )
                ctx = maybe_jsonapi_context()
                if ctx is not None and ctx.operation_authorizer is not None:
                    ctx.operation_authorizer(target_class, "create")
                return target_class._s_post_prechecked(data["id"], **attributes, **relationships)
            existing = target_class._s_get_upsert_target(data["id"], **attributes)
            if existing is not None:
                # SEC-02: the nested payload rewrites an existing row; the
                # target row's object-level policy must authorize it.
                run_instance_access_check(target_class, existing, "link")
            return target_class._s_post(data["id"], **attributes, **relationships)

        reject_current_relationship_fields(self.__class__, params.keys())
        for rel_name, rel_val in params.items():
            rel = self.__mapper__.relationships.get(rel_name)
            if not rel:
                continue
            check_relationship_write_permission(self, rel_name)
            if not self._s_allow_add_rels:
                raise ValidationError("Cannot add relationships (_s_allow_add_rels not set)")
            if not isinstance(rel_val, dict) or not "data" in rel_val:
                raise ValidationError("Invalid relationship payload")
            target_class = rel.mapper.class_
            if not self.included_list:
                self.included_list = []
            self.included_list += [rel_name]
            rel_data = rel_val["data"]
            if isinstance(rel_data, list) and rel.direction in (ONETOMANY, MANYTOMANY):
                max_items_config = get_config("MAX_BULK_ITEMS")
                max_items = int(
                    max_items_config if max_items_config is not None else safrs.SAFRS.MAX_BULK_ITEMS
                )
                if _request_uow_active() and max_items > 0 and len(rel_data) > max_items:
                    raise ValidationError(
                        f"Nested relationship POST exceeds maximum item count {max_items}"
                    )
                rel_inst = [data2inst(rd, target_class) for rd in rel_data]
                setattr(self, rel_name, rel_inst)
            elif isinstance(rel_data, dict) and rel.direction == MANYTOONE:
                inst = data2inst(rel_data, target_class)
                setattr(self, rel_name, inst)
            else:
                raise ValidationError("Invalid relationship payload")

    @staticmethod
    @lru_cache(maxsize=4)
    def _safrs_subclasses() -> Any:
        """
        return a dict containing all SAFRSBase subclasses
        """
        subclasses = {c._s_type: c for c in SAFRSBase.__subclasses__()}
        while True:
            cont = False
            for subclass in [sc for r in subclasses.values() for sc in r.__subclasses__()]:
                if hasattr(subclass, "_s_type") and subclass._s_type not in subclasses and Model in inspect.getmro(subclass):
                    cont = True
                    subclasses[subclass._s_type] = subclass
            if not cont:
                break
        return subclasses

    @hybrid_property
    def http_methods(self: Any) -> list[str]:  # type: ignore[no-redef]
        """
        :return: list of allowed HTTP methods
        """
        return self.__class__.http_methods

    @http_methods.expression  # type: ignore[no-redef]
    def http_methods(self: Any) -> list[str]:
        """
        :return: list of allowed HTTP methods
        """
        return ["GET", "POST", "PATCH", "DELETE", "PUT", "HEAD", "OPTIONS"]

    @classmethod
    def _s_supports_http_method(cls: Any, method: str) -> bool:
        """Return whether the model exposes an HTTP operation."""
        return str(method).upper() in {str(item).upper() for item in cls.http_methods}

    @classmethod
    def _s_validate_cascade_delete_methods(cls: Any, instance: Any = None) -> None:
        """Prevent a parent DELETE from bypassing target DELETE restrictions
        and target object-level policies (SEC-02).

        With ``instance`` given, every row doomed by the cascade is also
        checked against its model's ``_s_check_instance_access`` hook.
        """
        visited: set[Any] = {cls}

        def visit(current_model: Any) -> None:
            mapper = getattr(current_model, "__mapper__", None)
            if mapper is None:
                return
            for relationship in mapper.relationships:
                cascade = getattr(relationship, "cascade", None)
                cascades_delete = bool(
                    cascade is not None
                    and (getattr(cascade, "delete", False) or getattr(cascade, "delete_orphan", False))
                )
                if not cascades_delete:
                    continue
                target_model = relationship.mapper.class_
                if target_model in visited:
                    continue
                visited.add(target_model)
                supports_method = getattr(target_model, "_s_supports_http_method", None)
                if callable(supports_method) and not supports_method("DELETE"):
                    raise ValidationError(
                        f"DELETE is not allowed for cascaded resource {target_model.__name__}",
                        HTTPStatus.METHOD_NOT_ALLOWED.value,
                    )
                visit(target_model)

        visit(cls)
        if instance is None:
            return

        # SEC-02: object-level check for every row the cascade will delete.
        visited_rows: set[Any] = {instance}

        def visit_row(current: Any) -> None:
            mapper = getattr(current, "__mapper__", None)
            if mapper is None:
                return
            for relationship in mapper.relationships:
                cascade = getattr(relationship, "cascade", None)
                cascades_delete = bool(
                    cascade is not None
                    and (getattr(cascade, "delete", False) or getattr(cascade, "delete_orphan", False))
                )
                if not cascades_delete:
                    continue
                related = getattr(current, relationship.key, None)
                if related is None:
                    continue
                if hasattr(related, "__iter__") and not isinstance(related, (str, bytes)):
                    items = list(related)
                else:
                    items = [related]  # to-one relationship
                for item in items:
                    if item is None or id(item) in visited_rows:
                        continue
                    visited_rows.add(id(item))
                    run_instance_access_check(
                        relationship.mapper.class_, item, "cascade_delete"
                    )
                    visit_row(item)

        visit_row(instance)

    @classproperty
    def _s_columns(cls: Any) -> list:
        """
        :return: list of columns that are exposed by the api
        """
        if not hasattr(cls, "__mapper__"):
            return []

        result = cls.__mapper__.columns

        if has_request_context():
            # In the web context we only return the attributes that are exposable and readable
            # i.e. where the "expose" attribute is set on the db.Column instance
            # and the "r" flag is in the permissions
            result = [c for c in result if cls._s_check_perm(cls.colname_to_attrname(c.name))]
        return result

    @hybrid_property
    def _s_relationships(self: Any) -> dict:
        """
        :return: the relationships used for jsonapi (de/)serialization
        """
        rels = {rel.key: rel for rel in self.__mapper__.relationships if self._s_check_perm(rel.key)}
        return rels

    @_s_relationships.expression  # type: ignore[no-redef]
    def _s_relationships(cls: Any) -> Any:  # type: ignore[no-redef]
        """
        :return: the relationships used for jsonapi (de/)serialization
        """
        rels = {rel.key: rel for rel in cls.__mapper__.relationships if cls._s_check_perm(rel.key)}
        return rels

    @classmethod
    def colname_to_attrname(cls: Any, col_name: Any) -> Any:
        """
        Map column name to model attribute name

        We want this:
        ```
            for attr_name, attr_val in cls.__dict__.items():
                if col_name == getattr(attr_val, "name", None):
                    return attr_name
            return col_name
        ```
        To avoid executing this loop over and over, we create a lookup table when performing the first lookup
        (this is slightly faster than using lru_cache)
        """

        if cls._col_attr_name_map is None:
            # create lookup tables for attr <-> col mapping
            cls._col_attr_name_map = {}
            cls._attr_col_name_map = {}
            for attr_name, attr_val in cls.__dict__.items():
                if attr_name.startswith("__") and attr_name.endswith("__"):
                    # skip dunder attributes
                    continue
                _col_name = getattr(attr_val, "name", attr_name)
                if attr_name == "type":
                    attr_name = "Type"
                cls._col_attr_name_map[_col_name] = attr_name
                cls._attr_col_name_map[attr_name] = _col_name

        return cls._col_attr_name_map[col_name]

    @hybrid_method
    def _s_check_perm(self: Any, property_name: Any, permission: Any='r') -> bool:
        """
        Check the (instance-level) column permission
        :param column_name: column name
        :param permission: permission string (read/write)
        :return: Boolean indicating whether access is allowed
        """

        return self.__class__._s_check_perm(property_name, permission)

    @_s_check_perm.expression  # type: ignore[no-redef]
    @lru_cache(maxsize=256)
    def _s_check_perm(cls: Any, property_name: Any, permission: Any='r') -> bool:  # type: ignore[no-redef]
        """
        Check the (class-level) column permission
        :param column_name: column name
        :param permission: permission string (read/write)
        :return: Boolean indicating whether access is allowed
        """
        if property_name.startswith("_"):
            return False

        if property_name in cls.exclude_attrs:
            return False

        if is_jsonapi_attr(lookup_jsonapi_attr(cls, property_name)):
            return True

        if not hasattr(cls, "__mapper__"):
            # Stateless objects
            return False

        for rel in cls.__mapper__.relationships:
            if not cls.supports_includes:
                continue
            if rel.key != property_name:
                continue
            if rel.key in cls.exclude_rels:
                # relationship name has been set in exclude_rels
                return False
            if not getattr(rel.mapper.class_, "_s_expose", False):
                # only SAFRSBase instances can be exposed
                return False
            if not getattr(rel, "expose", True):
                # relationship `expose` attribute has explicitly been set to False
                return False
            return True

        for column in cls.__mapper__.columns:
            # don't expose attributes starting with an underscore
            if cls.colname_to_attrname(column.name) != property_name:
                continue
            if getattr(column, "expose", True) and permission in getattr(column, "permissions", "rw"):
                return True
            return False

        raise SystemValidationError(f"Invalid property {property_name}")

    def _s_check_instance_access(self: Any, action: str = "read") -> bool:
        """
        Object-level (per-row) access check, used when this row is loaded
        through a relationship payload, an include traversal, a nested write
        or a cascade operation (SEC-02).

        :param action: one of ``read``, ``link``, ``unlink``, ``cascade_delete``.
        :return: True when the row may be used. Deny by returning False or by
            raising a :class:`safrs.errors.JsonapiError` (e.g. 401/403).
            Unexpected exceptions fail closed as 403.
        """
        return True

    @hybrid_property
    def _s_jsonapi_attrs(self: Any) -> Any:
        """
        :return: dictionary of exposed attribute names and values

        ---
        The `fields` variable is used to implement jsonapi "Sparse Fieldsets"
        https://jsonapi.org/format/#fetching-sparse-fieldsets:
            client MAY request that an endpoint return only specific fields in the response on a per-type basis by including a fields[TYPE] parameter.
            The value of the fields parameter MUST be a comma-separated (U+002C COMMA, “,”) list that refers to the name(s) of the fields to be returned.
            If a client requests a restricted set of fields for a given resource type, an endpoint MUST NOT include additional fields in resource objects
            of that type in its response.
        Therefore we extract the required fieldnames from the request args, eg. Users/?Users[name] => [name]
        """
        fields = self.__class__._s_jsonapi_attrs.keys()
        ctx = maybe_jsonapi_context()
        if ctx is not None:
            context_fields = ctx.sparse_fields_for_model(self.__class__)
            if context_fields:
                fields = context_fields
        elif has_request_context():
            fields = request.fields.get(self._s_class_name, fields)

        readable_fields = current_readable_fields(self)
        if readable_fields is not None:
            fields = [field for field in fields if field in readable_fields]

        result = {}
        ja_attr_names = [
            name
            for name, attr in self.__class__._s_jsonapi_attrs.items()
            if self._s_check_perm(name) and not jsonapi_attr_is_write_only(attr)
        ]

        for attr in fields:
            if attr not in ja_attr_names:
                continue
            attr_val = ""
            attr_name = attr
            if hasattr(self, attr):
                attr_val = getattr(self, attr)
            else:
                col_name = self.colname_to_attrname(attr)
                attr_val = getattr(self, col_name)
            try:
                # Use Flask's app-level JSON encoder when an app context exists.
                if has_app_context():
                    json_encoder = getattr(cast(Any, current_app), "json_encoder", None)
                    if json_encoder is not None:
                        result[attr_name] = json.loads(json.dumps(attr_val, cls=json_encoder))
                    else:
                        result[attr_name] = attr_val
                else:
                    result[attr_name] = attr_val
            except UnicodeDecodeError:  # pragma: no cover
                safrs.log.warning("Unicode decode failed for %s.%s", type(self).__name__, attr)
                result[attr] = ""
            except Exception as exc:
                safrs.log.warning(
                    "Attribute fetch failed for %s.%s (%s)",
                    type(self).__name__,
                    attr,
                    type(exc).__name__,
                )

        return result

    @_s_jsonapi_attrs.expression  # type: ignore[no-redef]
    def _s_jsonapi_attrs(cls: Any) -> Any:  # type: ignore[no-redef]
        """
        :return: dict of jsonapi attributes
        At the moment we expect the column name to be equal to the column name
        Things will go south if this isn't the case and we should use
        the cls.__mapper__._polymorphic_properties instead
        """
        # Preserve an explicit class-level override used by extensions. SAFRS
        # no longer populates this value automatically because doing so would
        # cache caller-dependent permission results across requests.
        cached_attrs = cls.__dict__.get("_cached_jsonapi_attrs")
        if cached_attrs is not None:
            return cached_attrs

        result = {}
        for column in cls._s_columns:
            attr_name = cls.colname_to_attrname(column.name)
            if not cls._s_check_perm(attr_name):
                continue
            # jsonapi schema prohibits the use of the fields 'id' and 'type' in the attributes
            # http://jsonapi.org/format/#document-resource-object-fields
            if attr_name == "type":
                # translate type to Type
                result["Type"] = column
            elif not attr_name == "id" and attr_name not in cls._s_relationships:
                result[attr_name] = column

        for attr_name, attr_val in get_jsonapi_attrs(cls).items():
            result[attr_name] = attr_val

        return result

    @classproperty
    def _s_jsonapi_writable_attrs(cls: Any) -> dict[str, Any]:
        """Return JSON:API attributes accepted from POST/PATCH requests."""
        if "__mapper__" not in cls.__dict__:
            return {
                attr_name: attr_val
                for attr_name, attr_val in cls._s_jsonapi_attrs.items()
                if not is_jsonapi_attr(attr_val) or not jsonapi_attr_is_read_only(attr_val)
            }

        result: dict[str, Any] = {}
        for column in cls.__mapper__.columns:
            attr_name = cls.colname_to_attrname(column.name)
            # Column permissions historically describe the exposed JSON:API
            # surface.  A write-only column is hidden completely; write-only
            # request fields should be implemented with ``jsonapi_attr``.
            if not cls._s_check_perm(attr_name, "r") or not cls._s_check_perm(attr_name, "w"):
                continue
            if attr_name == "type":
                result["Type"] = column
            elif attr_name != "id" and attr_name not in cls._s_relationships:
                result[attr_name] = column

        for attr_name, attr_val in get_jsonapi_attrs(cls).items():
            if not jsonapi_attr_is_read_only(attr_val):
                result[attr_name] = attr_val

        return result

    def _s_expunge(self: Any) -> Any:
        """
        expunge an object from its session
        """
        session = sqla_inspect(self).session
        session.expunge(self)

    @classproperty
    def _s_auto_commit(self: Any) -> Any:
        """
        :return: whether the instance should be automatically commited.
        :rtype: boolen
        fka db_commit: auto_commit is a beter name, but keep db_commit for backwards compatibility
        """
        return self.db_commit

    @_s_auto_commit.setter  # type: ignore[no-redef]
    def _s_auto_commit(self: Any, value: Any) -> Any:  # type: ignore[no-redef]
        """
        :param value:
        auto_commit setter
        """
        self.db_commit = value

    def _s_clone(self: Any, **kwargs: Any) -> Any:
        """
        Clone an object: copy the parameters and create a new id
        :param *kwargs: TBD
        """
        make_transient(self)
        # pylint: disable=attribute-defined-outside-init
        self.id = self.id_type()
        for parameter in self._s_jsonapi_attrs:
            value = kwargs.get(parameter, None)
            if value is not None:
                setattr(self, parameter, value)
        get_db().session.add(self)
        tx.note_write(self.__class__)
        if _request_uow_active():
            get_db().session.flush()
        return self

    @classmethod
    def get_instance(cls: Any, item: Any=None, failsafe: Any=False) -> Any:
        """
        :param item: instance id or dict { "id" : .. "type" : ..}
        :param failsafe: indicates whether we want an exception to be raised in case the id is not found
        :return: Instance or None. An error is raised if an invalid id is used
        """
        instance = None
        # pylint: disable=invalid-name,redefined-builtin
        if isinstance(item, dict):
            id = item.get("id", None)
            if id is None:
                raise ValidationError("Invalid id")
            if item.get("type") != cls._s_type:
                raise ValidationError("Invalid item type")
        else:
            id = item
        try:
            primary_keys = cls.id_type.get_pks(id)
        except AttributeError:  # pragma: no cover
            # This happens when we request a sample from a class that is not yet loaded
            # when we're creating the swagger models
            safrs.log.debug(f'AttributeError for class "{cls.__name__}"')
            return instance  # instance is None!

        if id is not None or not failsafe:
            try:
                instance = cls._s_query.filter_by(**primary_keys).first()
            except OverflowError as exc:
                safrs.log.warning("Integer overflow while resolving resource identifier")
                raise IntegerOverflowError("Invalid integer value in id filter") from exc
            except Exception as exc:  # pragma: no cover
                safrs.log.error("Resource lookup failed (%s)", type(exc).__name__)
                raise GenericError("Resource lookup failed") from exc

            if not instance and not failsafe:
                raise NotFoundError()
        return instance

    @classmethod
    def _s_get_instance_by_id(cls: Any, jsonapi_id: Any) -> Any:
        """
        :param jsonapi_id: jsonapi_id
        :return: query obj
        """
        primary_keys = cls.id_type.get_pks(jsonapi_id)
        return cls._s_query.filter_by(**primary_keys)

    @property
    def jsonapi_id(self: Any) -> Any:
        """
        :return: json:api id
        :rtype: str

        if the table/object has a single primary key "id", it will return this id.
        In the other cases, the jsonapi "id" will be generated by the cls.id_type (typically by combining the PKs)

        The id has to be of type string according to the jsonapi json validation schema
        """
        return str(self.id_type.get_id(self))

    @classproperty
    @lru_cache(maxsize=32)
    # pylint: disable=method-hidden
    def id_type(obj: Any) -> Any:
        """
        :return: the object's id type
        """
        id_type = get_id_type(obj, delimiter=obj._s_pk_delimiter)
        # monkey patch so we don't have to look it up next time
        obj.id_type = id_type
        return id_type

    @classproperty
    def _s_query(cls_or_self: Any) -> Any:
        """
        :return: sqla query object
        """
        result = None
        _table = getattr(cls_or_self, "_table", None)
        try:
            result = get_db().session.query(cls_or_self)
        except (sqlalchemy.exc.InvalidRequestError, sqlalchemy.exc.ArgumentError) as exc:
            # this may happen when exposing a stateless object, in which case
            # the warning can be ignored.
            if getattr(cls_or_self, "_s_stateless", None):
                safrs.log.warning("Invalid SQLA request")
        except Exception as exc:
            safrs.log.error("Query failed for %s (%s)", cls_or_self, type(exc).__name__)

        if _table is not None:
            result = get_db().session.query(_table)

        return result

    query = _s_query

    def to_dict(self: Any, *args: Any, **kwargs: Any) -> Any:
        """
        Create a dictionary with all the instance "attributes"
        this method will be called by SAFRSJSONEncoder to serialize objects

        :return: dictionary with jsonapi attributes
        """
        return self._s_jsonapi_attrs

    @classproperty
    def _s_class_name(cls: Any) -> Any:
        """
        :return: the name of the instances
        """
        return cls.__name__

    @classproperty
    def _s_collection_name(cls: Any) -> Any:
        """
        :return: the name of the collection, this will be used to construct the endpoint
        """
        return getattr(cls, "__tablename__", cls.__name__)

    @classproperty
    def _s_type(cls: Any) -> Any:
        """
        :return: the jsonapi "type", i.e. the tablename if this is a db model, the classname otherwise
        """
        return cls.__name__

    @hybrid_method
    def _s_jsonapi_encode(self: Any) -> Any:
        """
        :return: Encoded object according to the jsonapi specification:
        `data = {
                "attributes": { ... },
                "id": "...",
                "links": { ... },
                "relationships": { ... },
                "type": "..."
                }`
        """
        require_current_instance(self, "read")
        ctx = maybe_jsonapi_context()
        if ctx is not None:
            if ctx.resource_authorizer is not None:
                ctx.resource_authorizer(self.__class__, self, "read")
            self_link = ctx.instance_path(self.__class__, self)
        else:
            if has_request_context():
                run_instance_access_check(self.__class__, self, "read")
            self_link = self._s_url
        attributes = self.to_dict()
        relationships = self._s_get_related()
        if ctx is not None:
            ctx.ja_data.add(self)
        elif has_request_context():
            g.ja_data.add(self)
        data = dict(attributes=attributes, id=self.jsonapi_id, links={"self": self_link}, type=self._s_type, relationships=relationships)

        return data

    def _s_get_include_settings(self: Any) -> tuple[list[str], set[str], list[str]]:
        included_list = getattr(self, "included_list", None)
        ctx = maybe_jsonapi_context()
        default_included = str(get_config("DEFAULT_INCLUDED") or "")
        if included_list is None:
            if ctx is not None:
                included_csv = ctx.get_include_csv(default_included)
            elif has_request_context():
                included_csv = request.args.get("include", default_included)
            else:
                included_csv = default_included
            included_list = [inc for inc in included_csv.split(",") if inc]

        max_paths_config = get_config("MAX_INCLUDE_PATHS")
        max_include_paths = int(
            max_paths_config
            if max_paths_config is not None
            else safrs.SAFRS.MAX_INCLUDE_PATHS
        )
        effective_path_count = len(included_list)
        include_all = str(get_config("INCLUDE_ALL") or safrs.SAFRS.INCLUDE_ALL)
        if include_all in included_list:
            effective_path_count += max(0, len(self._s_relationships) - 1)
        if max_include_paths > 0 and effective_path_count > max_include_paths:
            raise ValidationError(f"Too many include paths (maximum {max_include_paths})")
        max_depth_config = get_config("MAX_INCLUDE_DEPTH")
        max_include_depth = int(
            max_depth_config
            if max_depth_config is not None
            else safrs.SAFRS.MAX_INCLUDE_DEPTH
        )
        for include_path in included_list:
            include_depth = len([segment for segment in str(include_path).split(".") if segment])
            if max_include_depth > 0 and include_depth > max_include_depth:
                raise ValidationError(f"Include path exceeds maximum depth {max_include_depth}")

        if ctx is not None:
            excluded_csv = ctx.get_exclude_csv("")
        elif has_request_context():
            excluded_csv = request.args.get("exclude", "")
        else:
            excluded_csv = ""
        excluded_list = excluded_csv.split(",")
        included_rels = {item.split(".")[0] for item in included_list}
        return included_list, included_rels, excluded_list

    def _s_validate_included_relationships(self: Any, included_rels: set[str], included_list: list[str]) -> None:
        include_all = str(get_config("INCLUDE_ALL") or safrs.SAFRS.INCLUDE_ALL)
        for rel_name in included_rels:
            if rel_name != include_all and rel_name not in self._s_relationships:
                raise GenericError(f"Invalid Relationship '{rel_name}'", status_code=400)

    @staticmethod
    def _s_nested_included_list(included_list: list[str], rel_name: str) -> list[list[str]]:
        return [inc_item.split(".")[1:] for inc_item in included_list if inc_item.startswith(rel_name + ".")]

    @staticmethod
    def _s_relationship_result(rel_url: str, data: Any, meta: dict[str, Any]) -> dict[str, Any]:
        rel_data: dict[str, Any] = {"links": {"self": rel_url}, "data": data}
        if meta:
            rel_data["meta"] = meta
        return rel_data

    def _s_related_collection_data(self: Any, rel_name: str, next_included_list: list[list[str]]) -> tuple[list[Any], dict[str, Any]]:
        data: list[Any] = []
        meta: dict[str, Any] = {}
        rel_query = getattr(self, rel_name)
        target_model = self._s_relationships[rel_name].mapper.class_
        if current_model_is_registered(target_model):
            rel_query = get_db().session.query(target_model).with_parent(
                self, property=self._s_relationships[rel_name]
            )
        rel_query = target_model._s_query_scope(rel_query)
        rel_query = authorize_collection_before_metadata(target_model, rel_query)
        ctx = maybe_jsonapi_context()
        if ctx is not None:
            limit = ctx.get_relationship_page_limit(rel_name)
        elif has_request_context():
            limit = cast(Any, request).get_page_limit(rel_name)
        else:
            raw_limit = get_config("DEFAULT_PAGE_LIMIT")
            try:
                limit = int(raw_limit) if raw_limit is not None else int(safrs.SAFRS.DEFAULT_PAGE_LIMIT)
            except (TypeError, ValueError):
                limit = int(safrs.SAFRS.DEFAULT_PAGE_LIMIT)
        if not get_config("ENABLE_RELATIONSHIPS"):
            meta["warning"] = "ENABLE_RELATIONSHIPS set to false in config.py"
            return data, meta
        if not rel_query:
            return data, meta

        if getattr(rel_query, "limit", False):
            count = rel_query.count()
            rel_query = rel_query.limit(limit)
            if rel_query.count() >= get_config("BIG_QUERY_THRESHOLD"):
                warning = f'Truncated result for relationship "{rel_name}",consider paginating this request'
                safrs.log.warning(warning)
                meta["warning"] = warning
            items = rel_query.all()
        else:  # rel_query is an 'InstrumentedList'
            authorized_items = list(rel_query)
            count = len(authorized_items)
            items = authorized_items[:limit]

        prepare_current_readable_fields(target_model, items)
        meta["count"] = meta["total"] = count
        meta["limit"] = limit
        for rel_item in items:
            data.append(Included(rel_item, next_included_list))
        return data, meta

    def _s_get_related(self: Any) -> Any:
        """
        :return: dict of relationship names -> [related instances]

        http://jsonapi.org/format/#fetching-includes

        Inclusion of Related Resources
        Multiple related resources can be requested in a comma-separated list:
        An endpoint MAY return resources related to the primary data by default.
        An endpoint MAY also support an include request parameter to allow
        the client to customize which related resources should be returned.
        In order to request resources related to other resources,
        a dot-separated path for each relationship name can be specified

        All related instances are stored in the `Included` class so we don't have to walk
        the relationships twice

        Request parameter example:
            include=friends.books_read,friends.books_written
        """
        # included_list contains a list of relationships to include
        # it may have been set previously by Included() when called recursively
        # if it's not set, parse the include= request param here
        # included_list example: ['friends.books_read', 'friends.books_written']
        included_list, included_rels, excluded_list = self._s_get_include_settings()
        relationships = {}
        self._s_validate_included_relationships(included_rels, included_list)
        include_all = str(get_config("INCLUDE_ALL") or safrs.SAFRS.INCLUDE_ALL)

        readable_fields = current_readable_fields(self)
        for rel_name, relationship in self._s_relationships.items():
            """
            http://jsonapi.org/format/#document-resource-object-relationships:

            The value of the relationships key MUST be an object (a “relationships object”).
            Members of the relationships object (“relationships”) represent
            references from the resource object in which it’s defined to other resource objects.

            Relationships may be to-one or to-many.

            A “relationship object” MUST contain at least one of the following:

            - links: a links object containing at least one of the following:
                - self: a link for the relationship itself (a “relationship link”).
                This link allows the client to directly manipulate the relationship.
                - related: a related resource link
            - data: resource linkage
            - meta: a meta object that contains non-standard meta-information
                    about the relationship.
            A relationship object that represents a to-many relationship
            MAY also contain pagination links under the links member, as described below.
            SAFRS currently implements links with self
            """
            meta: dict[str, Any] = {}
            rel_name = relationship.key
            if readable_fields is not None and rel_name not in readable_fields:
                continue
            data: Any = [] if relationship.direction in (ONETOMANY, MANYTOMANY) else None
            if rel_name in excluded_list:
                # TODO: document this
                # continue
                pass
            if rel_name in included_rels or include_all in included_list:
                ctx = maybe_jsonapi_context()
                run_relationship_read_access_check(relationship)
                if ctx is not None and ctx.operation_authorizer is not None:
                    ctx.operation_authorizer(relationship.mapper.class_, "read")
                # next_included_list contains the recursive relationship names
                next_included_list = self._s_nested_included_list(included_list, rel_name)
                if relationship.direction == MANYTOONE:
                    # manytoone relationship contains a single instance
                    rel_item = getattr(self, rel_name)
                    target_visible = False
                    try:
                        target_visible = bool(
                            rel_item
                            and run_instance_access_check(
                                relationship.mapper.class_, rel_item, "read"
                            )
                        )
                    except NotFoundError:
                        if not current_model_is_registered(relationship.mapper.class_):
                            raise
                    if target_visible:
                        # create an Included instance that will be used for serialization eventually
                        data = Included(rel_item, next_included_list)
                elif relationship.direction in (ONETOMANY, MANYTOMANY):
                    data, meta = self._s_related_collection_data(rel_name, next_included_list)
                else:  # pragma: no cover
                    # should never happen
                    safrs.log.error(f"Unknown relationship direction for relationship {rel_name}: {relationship.direction}")

            ctx = maybe_jsonapi_context()
            if ctx is not None:
                rel_link = ctx.relationship_path(self.__class__, self, rel_name)
            else:
                rel_link = urljoin(self._s_url, rel_name)
            relationships[rel_name] = self._s_relationship_result(rel_link, data, meta)

        return relationships

    def __unicode__(self: Any) -> Any:
        """"""
        name = getattr(self, "name", self.jsonapi_id)
        return name if name is not None else ""

    __str__ = __unicode__

    @classmethod
    def _s_count(cls: Any) -> Any:
        """
        returning None will cause our jsonapi to perform a count() on the result
        this can be overridden with a cached value for performance on large tables (>1G)
        """
        max_table_count = get_config("MAX_TABLE_COUNT")

        try:
            count = cls.jsonapi_filter().count()
        except Exception as exc:
            # May happen for custom types, for ex. the psycopg2 extension
            safrs.log.warning("Count failed for %s (%s)", cls, type(exc).__name__)
            count = -1

        if count > max_table_count:
            safrs.log.warning(
                f"Large table count detected ({count}>{max_table_count}), performance may be impacted, consider '{cls.__name__}._s_count' override"
            )

        return count

    #
    # Following methods are used to create the swagger2 API documentation
    #
    @classmethod
    def _s_sample_id(cls: Any) -> Any:
        """
        :return: a sample id for the API documentation

        Derived from static column metadata only. Live database rows are
        never read so public API documentation cannot leak application
        data (SEC-06).
        """
        try:
            sample_id = cls.id_type.sample_id(cls)
        except Exception as exc:
            safrs.log.debug("Failed to build sample identifier (%s)", type(exc).__name__)
            sample_id = ""
        return str(sample_id)  # jsonapi ids must always be strings

    @classmethod
    def _s_sample_dict(cls: Any) -> Any:
        """
        :return: a sample to be used as an example "attributes" payload in the swagger example
        """
        # create a swagger example based on the jsonapi attributes (reflecting the database column schema)
        sample = {}
        for attr_name, attr in cls._s_jsonapi_attrs.items():
            if is_jsonapi_attr(attr):
                arg = getattr(attr, "default", "")
            else:
                column = attr
                arg = None
                if hasattr(column, "sample"):
                    arg = getattr(column, "sample")
                elif hasattr(column, "default") and column.default:
                    if callable(column.default.arg):
                        # We're not executing the default when it's a callable to avoid side-effects,
                        # user may add a sample attribute to the column to have it show up in the swagger
                        safrs.log.debug(f"No OAS sample implemented for column default '{column.name}.{column.default.arg}'")
                        arg = ""
                    elif isinstance(column.type, sqlalchemy.sql.sqltypes.JSON):
                        arg = column.default.arg
                    else:
                        python_type = SWAGGER2_TYPE_CAST.get(column.type, str)
                        arg = python_type(column.default.arg)
                else:
                    # No default column value speciefd => infer one by type
                    try:
                        if column.type.python_type == int:
                            arg = 0
                        if column.type.python_type == datetime.datetime:
                            arg = str(datetime.datetime.min)
                        elif column.type.python_type == datetime.date:
                            arg = str(datetime.datetime.min.date())
                        else:
                            arg = column.type.python_type()
                    except NotImplementedError:
                        # This may happen for custom columns
                        safrs.log.debug(f"Failed to get python type for column {column} (NotImplementedError)")
                        arg = None
                    except Exception as exc:
                        safrs.log.debug(
                            "Failed to get python type for column %s (%s)", column, type(exc).__name__
                        )
                        # use an empty string when no type is matched, otherwise we may get json encoding
                        # errors for the swagger generation
                        arg = ""

            sample[attr_name] = arg

        return sample

    @classproperty
    def _s_object_id(cls: Any) -> Any:
        """
        :return: the Flask url parameter name of the object, e.g. UserId
        :rtype: string
        """
        # pylint: disable=no-member
        return cls.__name__ + get_config("OBJECT_ID_SUFFIX")

    @classmethod
    def _s_get_jsonapi_rpc_methods(cls: Any) -> Any:
        """
        :return: a list of jsonapi_rpc methods for this class
        :rtype: list
        """
        result: list[Any] = []
        try:
            cls_member_names = dir(cls)
        except sqlalchemy.exc.InvalidRequestError as exc:
            # This may happen if there's no sqlalchemy superclass
            safrs.log.warning("Member inspection failed for %s (%s)", cls, type(exc).__name__)
            return result

        for member_name in cls_member_names:
            try:
                method = inspect.getattr_static(cls, member_name)
            except Exception as exc:
                safrs.log.debug(
                    "Skipping rpc inspection for %s.%s (%s)", cls, member_name, type(exc).__name__
                )
                continue
            if isinstance(method, (classmethod, staticmethod)):
                method = method.__func__
            rest_doc = get_doc(method)
            if rest_doc is not None:
                result.append(method)
        return result

    @classmethod
    def _s_get_swagger_doc(cls: Any, http_method: Any) -> Any:
        """
        :param http_method: the http method for which to retrieve the documentation
        :return: swagger `body` and `response` dictionaries
        :rtype: tuple
        Create a swagger api model based on the sqlalchemy schema.
        """
        body: dict[str, Any] = {}
        responses: dict[Any, Any] = {}

        if http_method.upper() in cls.http_methods:
            responses = {HTTPStatus.NOT_FOUND.value: {"description": HTTPStatus.NOT_FOUND.description}}

            if http_method in ("post"):
                responses = {HTTPStatus.CREATED.value: {"description": HTTPStatus.CREATED.description}}

        return body, responses

    @classmethod
    def get_endpoint(cls: Any, url_prefix: Any=None, type: Any=None) -> Any:
        """
        :param url_prefix: URL prefix used by the app
        :param type: endpoint type, e.g. "instance"
        :return: the API endpoint
        :rtype: str
        """
        if url_prefix is None:
            safrs_api = current_app.extensions.get("safrs_api") if has_app_context() else None
            prefixes = getattr(safrs_api, "_model_url_prefix", {}) if safrs_api is not None else {}
            url_prefix = prefixes.get(cls, cls.url_prefix)
        if type == "instance":
            INSTANCE_ENDPOINT_FMT = cast(str, get_config("INSTANCE_ENDPOINT_FMT"))
            endpoint = INSTANCE_ENDPOINT_FMT.format(url_prefix, cls._s_type)
        else:  # type = 'collection'
            endpoint = f"{url_prefix}api.{cls._s_type}"
        return endpoint

    @hybrid_property
    def _s_url(self: Any, url_prefix: Any='') -> Any:
        """
        :param url_prefix:
        :return: endpoint url of this instance
        """
        try:
            params = {self._s_object_id: self.jsonapi_id}
            instance_url = url_for(self.get_endpoint(type="instance"), **params)
            result = urljoin(self._s_url_root, instance_url)
        except RuntimeError:
            # This happens when creating the swagger doc and there is no application registered
            result = ""
        return result

    @_s_url.expression  # type: ignore[no-redef]
    def _s_url(cls: Any, url_prefix: Any='') -> Any:  # type: ignore[no-redef]
        try:
            collection_url = url_for(cls.get_endpoint())
            result = urljoin(cls._s_url_root, collection_url)
        except RuntimeError:
            # This happens when creating the swagger doc and there is no application registered
            result = ""
        return result

    @classmethod
    def _s_meta(cls: Any) -> Any:
        """
        What is returned in the "meta" part
        may be implemented by the app
        """
        return {}

    @property
    def Type(self: Any) -> Any:
        """
        jsonapi spec doesn't allow "type" as an attribute nmae, but this is a pretty common column name
        we rename type to Type so we can support it. A bit hacky but better than not supporting "type" at all
        This may cause other errors too, for ex when sorting
        :return: renamed type
        """
        safrs.log.debug(f'({self}): attribute name "type" is reserved, renamed to "Type"')
        return self.type

    @Type.setter
    def Type(self: Any, value: Any) -> Any:
        """
        Type property setter, see comment in the type property
        """
        if not self.Type == value:
            self.type = value

    @classmethod
    def _s_filter(cls: Any, *filter_args: Any, **filter_kwargs: Any) -> Any:
        """
        Apply a filter to this model
        :param filter_args: A list of filters information to apply, passed as a request URL parameter.
        Each filter object has the following fields:
        - name: The name of the field you want to filter on.
        - op: The operation you want to use (all sqlalchemy operations are available). The valid values are:
            - like: Invoke SQL like (or "ilike", "match", "notilike")
            - eq: check if field is equal to something
            - ge: check if field is greater than or equal to something
            - gt: check if field is greater than to something
            - ne: check if field is not equal to something
            - is_: check if field is a value
            - is_not: check if field is not a value
            - le: check if field is less than or equal to something
            - lt: check if field is less than to something
        - val: The value that you want to compare.
        :return: sqla query object
        """
        if not filter_args:
            raise ValidationError("Invalid filter format (see https://github.com/thomaxxl/safrs/wiki)")
        raw_filter = str(filter_args[0])
        return apply_filter_json(cls, raw_filter, cls._s_query)


class Included:
    """
    This class is used to serialize instances that will be included in the jsonapi response
    we keep a set of instances in `flask.g.ja_included` to avoid storing duplicates
    """

    instance = None

    def __init__(self: Any, instance: Any, included_list: Any) -> None:
        """
        :param instance: the instance to be included
        :param included_list: the list of relationships that should be included for `instance` (from the url query param)
        """
        self.instance = instance
        instance.included_list = [".".join(inc_rel) for inc_rel in included_list] if included_list else []
        ctx = maybe_jsonapi_context()
        if ctx is not None:
            ctx.ja_included.add(instance)
        elif has_request_context():
            g.ja_included.add(instance)

    @hybrid_method
    def encode(self: Any) -> Any:
        """
        jsonapi encoding of the instance in the included relationship dictionary
        """
        return {"id": str(self.instance.jsonapi_id), "type": self.instance._s_type}

    @encode.expression  # type: ignore[no-redef]
    def encode(cls: Any) -> Any:  # type: ignore[no-redef]
        """
        encoding of all included instances (in the included[] part of the jsonapi response)
        """
        ctx = maybe_jsonapi_context()
        if ctx is not None:
            ja_included = ctx.ja_included
            ja_data = ctx.ja_data
        elif has_request_context():
            ja_included = getattr(g, "ja_included", set())
            ja_data = getattr(g, "ja_data", set())
        else:
            ja_included = set()
            ja_data = set()
        already_included = set()
        result = []
        max_included_config = get_config("MAX_INCLUDED_RESOURCES")
        max_included = int(
            max_included_config
            if max_included_config is not None
            else safrs.SAFRS.MAX_INCLUDED_RESOURCES
        )
        while True:
            if not ja_included:
                break
            instance = ja_included.pop()
            if instance in already_included or instance in ja_data:
                continue
            if max_included > 0 and len(result) >= max_included:
                raise ValidationError(
                    f"Included resources exceed maximum item count {max_included}"
                )
            already_included.add(instance)
            included = instance._s_jsonapi_encode()
            result.append(included)

        return result
