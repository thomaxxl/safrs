"""Optional sparse, SQL-backed authorization for SAFRS resources.

The registry is deliberately independent from authentication.  Applications
resolve their own users and groups into :class:`AuthContext`, while SAFRS uses
one grant table to enforce row and field gates.  Registry helpers never commit
and never expose the grant table as an HTTP resource.
"""

from __future__ import annotations

from dataclasses import dataclass
import inspect
import re
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence

import sqlalchemy
from sqlalchemy import (
    CheckConstraint,
    Column,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    and_,
    cast,
    delete,
    exists,
    false,
    insert,
    literal,
    or_,
    select,
)

import safrs
from .errors import NotFoundError, SystemValidationError, UnAuthorizedError, ValidationError


AUTHORIZATION_ACTIONS = frozenset({"create", "read", "update", "delete"})
_RESOURCE_FIELD = ""
_MODEL_OBJECT = ""


def authorization_safe(function: Any) -> Any:
    """Mark a custom serializer/meta hook as registry-aware.

    The application remains responsible for using the request's authorized
    field contract and for not copying hidden values into arbitrary metadata.
    """
    target = getattr(function, "__func__", function)
    setattr(target, "safrs_authorization_safe", True)
    return function


@dataclass(frozen=True)
class AuthContext:
    """Trusted request identity supplied by the host application."""

    scope_key: str
    subject_keys: tuple[str, ...]
    tenant_id: Optional[str] = None


@dataclass(frozen=True)
class _ModelRegistration:
    model: type[Any]
    key: str
    pk_attribute: str
    pk_column: Any
    identity_kind: str
    tenant_column: Any
    fields: frozenset[str]
    table_key: str


class AuthorizationRegistry:
    """Sparse allow-only authorization registry.

    Register every protected model before constructing a SAFRS adapter.  The
    adapter binds the registry table to the application's metadata and freezes
    registrations.  Creating the physical table remains the application's
    migration responsibility.
    """

    def __init__(
        self,
        *,
        metadata: Optional[MetaData] = None,
        table_name: str = "safrs_auth_grant",
        max_subjects: int = 100,
        after_create: Optional[
            Callable[["AuthorizationRegistry", Any, AuthContext, Any], None]
        ] = None,
    ) -> None:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(table_name)):
            raise ValueError("table_name must be a simple SQL identifier")
        if max_subjects <= 0:
            raise ValueError("max_subjects must be positive")
        self.table_name = str(table_name)
        self.max_subjects = int(max_subjects)
        self.after_create = after_create
        self._registrations: dict[type[Any], _ModelRegistration] = {}
        self._registrations_by_table: dict[str, _ModelRegistration] = {}
        self._table: Optional[Table] = None
        self._frozen = False
        if metadata is not None:
            self.bind(metadata)

    @property
    def table(self) -> Table:
        if self._table is None:
            raise RuntimeError("AuthorizationRegistry is not bound to SQLAlchemy metadata")
        return self._table

    @property
    def registrations(self) -> Mapping[type[Any], str]:
        return {model: registration.key for model, registration in self._registrations.items()}

    def bind(self, metadata: MetaData) -> Table:
        """Declare or reuse the grant table in application metadata.

        This does not execute DDL.  Applications must create the table through
        their normal migration process.
        """
        if self._table is not None:
            if self._table.metadata is not metadata:
                raise RuntimeError("An authorization registry cannot span different metadata objects")
            return self._table
        existing = metadata.tables.get(self.table_name)
        if existing is not None:
            self._validate_existing_table(existing)
            self._table = existing
            return existing
        self._table = Table(
            self.table_name,
            metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("scope_key", String(255), nullable=False),
            Column("subject_key", String(255), nullable=False),
            Column("model_key", String(255), nullable=False),
            Column("object_key", String(1024), nullable=False, default=_MODEL_OBJECT),
            Column("field_key", String(255), nullable=False, default=_RESOURCE_FIELD),
            Column("action", String(16), nullable=False),
            UniqueConstraint(
                "scope_key",
                "subject_key",
                "model_key",
                "action",
                "object_key",
                "field_key",
                name=f"uq_{self.table_name}_grant",
            ),
            CheckConstraint(
                "action IN ('create', 'read', 'update', 'delete')",
                name=f"ck_{self.table_name}_action",
            ),
            CheckConstraint(
                "action != 'create' OR object_key = ''",
                name=f"ck_{self.table_name}_create_scope",
            ),
            CheckConstraint(
                "action != 'delete' OR field_key = ''",
                name=f"ck_{self.table_name}_delete_resource",
            ),
        )
        Index(
            f"ix_{self.table_name}_resource",
            self._table.c.scope_key,
            self._table.c.model_key,
            self._table.c.object_key,
        )
        return self._table

    @staticmethod
    def _validate_existing_table(table: Table) -> None:
        required = {
            "id",
            "scope_key",
            "subject_key",
            "model_key",
            "object_key",
            "field_key",
            "action",
        }
        missing = required - set(table.c.keys())
        if missing:
            raise RuntimeError(f"Authorization grant table is missing columns: {sorted(missing)}")

    def register(
        self,
        Model: type[Any],
        *,
        key: str,
        tenant_column: Any = None,
    ) -> None:
        """Register a model using a stable application-owned key.

        V1 intentionally supports only one integer or text primary key.
        Unsupported identities fail during startup instead of falling back to
        Python-side collection filtering.
        """
        if self._frozen:
            raise RuntimeError("AuthorizationRegistry registrations are frozen")
        if Model in self._registrations:
            raise ValueError(f"Model {getattr(Model, '__name__', Model)!r} is already registered")
        normalized_key = str(key).strip()
        if not normalized_key:
            raise ValueError("A stable non-empty model key is required")
        if any(registration.key == normalized_key for registration in self._registrations.values()):
            raise ValueError(f"Duplicate authorization model key: {normalized_key}")
        try:
            mapper = sqlalchemy.inspect(Model)
        except Exception as exc:
            raise TypeError("Authorization models must be SQLAlchemy mapped classes") from exc
        primary_keys = list(mapper.primary_key)
        if len(primary_keys) != 1:
            raise TypeError("Authorization V1 supports only single-column primary keys")
        pk_column = primary_keys[0]
        try:
            python_type = pk_column.type.python_type
        except Exception as exc:
            raise TypeError("Authorization primary-key type is unsupported") from exc
        if python_type is int:
            identity_kind = "integer"
        elif python_type is str:
            identity_kind = "text"
        else:
            raise TypeError("Authorization V1 supports only integer or text primary keys")
        try:
            pk_attribute = str(mapper.get_property_by_column(pk_column).key)
        except Exception as exc:
            raise TypeError("Authorization primary key must map to one model attribute") from exc

        resolved_tenant_column = None
        if tenant_column is not None:
            candidate = getattr(tenant_column, "property", None)
            columns = list(getattr(candidate, "columns", ()) or ())
            if len(columns) != 1 or columns[0].table is not mapper.local_table:
                raise TypeError("tenant_column must be a mapped scalar column on the registered model")
            resolved_tenant_column = tenant_column

        fields = self._model_fields(Model, mapper)
        self._validate_custom_serializers(Model)
        table_key = str(getattr(mapper.local_table, "fullname", mapper.local_table.name))
        registration = _ModelRegistration(
            model=Model,
            key=normalized_key,
            pk_attribute=pk_attribute,
            pk_column=pk_column,
            identity_kind=identity_kind,
            tenant_column=resolved_tenant_column,
            fields=frozenset(fields),
            table_key=table_key,
        )
        self._registrations[Model] = registration
        self._registrations_by_table[table_key] = registration

    @staticmethod
    def _validate_custom_serializers(Model: type[Any]) -> None:
        from .base import SAFRSBase

        for member_name in ("to_dict", "_s_meta"):
            owner = next(
                (base for base in Model.__mro__ if member_name in getattr(base, "__dict__", {})),
                None,
            )
            if owner in {None, SAFRSBase}:
                continue
            member = inspect.getattr_static(Model, member_name)
            target = getattr(member, "__func__", member)
            if not bool(getattr(target, "safrs_authorization_safe", False)):
                raise TypeError(
                    f"Protected model custom {member_name} must be marked @authorization_safe"
                )

    @staticmethod
    def _model_fields(Model: type[Any], mapper: Any) -> set[str]:
        fields: set[str] = set()
        for column in mapper.columns:
            try:
                fields.add(str(mapper.get_property_by_column(column).key))
            except Exception:
                fields.add(str(column.key))
        fields.update(str(relationship.key) for relationship in mapper.relationships)
        try:
            fields.update(str(name) for name in getattr(Model, "_s_jsonapi_attrs", {}).keys())
        except Exception:
            pass
        fields.discard("id")
        return fields

    def freeze(self) -> None:
        if self._table is None:
            raise RuntimeError("Bind AuthorizationRegistry before freezing registrations")
        self._frozen = True

    def is_registered(self, Model: type[Any]) -> bool:
        if Model in self._registrations:
            return True
        inspected = sqlalchemy.inspect(Model, raiseerr=False)
        if not bool(getattr(inspected, "is_aliased_class", False)):
            return False
        return inspected.mapper.class_ in self._registrations

    def validate_context(self, context: Any) -> Optional[AuthContext]:
        if context is None:
            return None
        if not isinstance(context, AuthContext):
            raise TypeError("principal provider must return AuthContext or None")
        if isinstance(context.subject_keys, (str, bytes)):
            raise TypeError("AuthContext.subject_keys must be a tuple of subject keys")
        scope_key = str(context.scope_key).strip()
        subjects = tuple(dict.fromkeys(str(subject).strip() for subject in context.subject_keys))
        if not scope_key or any(not subject for subject in subjects):
            raise ValueError("Authorization scope and subject keys must be non-empty")
        if len(scope_key) > 255 or any(len(subject) > 255 for subject in subjects):
            raise ValueError("Authorization scope and subject keys must not exceed 255 characters")
        if len(subjects) > self.max_subjects:
            raise UnAuthorizedError("Too many effective authorization subjects")
        return AuthContext(scope_key, subjects, context.tenant_id)

    def _registration(self, Model: type[Any]) -> _ModelRegistration:
        registered_model = Model
        if registered_model not in self._registrations:
            inspected = sqlalchemy.inspect(Model, raiseerr=False)
            if bool(getattr(inspected, "is_aliased_class", False)):
                registered_model = inspected.mapper.class_
        try:
            return self._registrations[registered_model]
        except KeyError as exc:
            raise KeyError(f"Model {getattr(Model, '__name__', Model)!r} is not registered") from exc

    @staticmethod
    def _validate_action(action: str) -> str:
        normalized = str(action).lower().strip()
        if normalized not in AUTHORIZATION_ACTIONS:
            raise ValueError(f"Unsupported authorization action: {action}")
        return normalized

    def _validate_field(self, registration: _ModelRegistration, field: Optional[str]) -> str:
        if field is None:
            return _RESOURCE_FIELD
        normalized = str(field).strip()
        if not normalized or normalized not in registration.fields:
            raise ValidationError(f"Unknown authorization field '{normalized}'")
        return normalized

    @staticmethod
    def _canonical_value(registration: _ModelRegistration, raw_value: Any) -> Any:
        if registration.identity_kind == "integer":
            try:
                return int(raw_value)
            except (TypeError, ValueError) as exc:
                raise ValidationError("Invalid authorization object id") from exc
        if raw_value is None:
            raise ValidationError("Invalid authorization object id")
        return str(raw_value)

    def _pk_value(self, registration: _ModelRegistration, instance_or_id: Any) -> Any:
        if isinstance(instance_or_id, registration.model):
            value = getattr(instance_or_id, registration.pk_attribute)
        else:
            id_type = getattr(registration.model, "id_type", None)
            validate = getattr(id_type, "validate_id", None)
            value = validate(instance_or_id) if callable(validate) else instance_or_id
        return self._canonical_value(registration, value)

    def object_key(self, Model: type[Any], instance_or_id: Any) -> str:
        registration = self._registration(Model)
        return "id:" + str(self._pk_value(registration, instance_or_id))

    @staticmethod
    def _identity_expression(
        registration: _ModelRegistration, entity: Optional[type[Any]] = None
    ) -> Any:
        model_pk = getattr(entity or registration.model, registration.pk_attribute)
        return literal("id:") + cast(model_pk, String)

    @staticmethod
    def _tenant_python_value(registration: _ModelRegistration, context: AuthContext) -> Any:
        if registration.tenant_column is None:
            return None
        if context.tenant_id is None:
            raise UnAuthorizedError("Tenant context is required")
        try:
            python_type = registration.tenant_column.property.columns[0].type.python_type
            return python_type(context.tenant_id)
        except UnAuthorizedError:
            raise
        except Exception as exc:
            raise UnAuthorizedError("Tenant context is invalid") from exc

    def _grant_exists_expression(
        self,
        context: Optional[AuthContext],
        registration: _ModelRegistration,
        action: str,
        field_key: str,
        *,
        object_expression: Any,
    ) -> Any:
        if context is None or not context.subject_keys:
            return false()
        grant = self.table
        return exists(
            select(literal(1)).select_from(grant).where(
                grant.c.scope_key == context.scope_key,
                grant.c.subject_key.in_(context.subject_keys),
                grant.c.model_key == registration.key,
                grant.c.action == action,
                grant.c.field_key == field_key,
                or_(grant.c.object_key == _MODEL_OBJECT, grant.c.object_key == object_expression),
            )
        )

    def predicate(
        self,
        context: Optional[AuthContext],
        Model: type[Any],
        action: str,
        field: Optional[str] = None,
    ) -> Any:
        """Return the SQL row predicate for an authorization gate."""
        registration = self._registration(Model)
        normalized_action = self._validate_action(action)
        if normalized_action == "create":
            raise ValueError("Create authorization has no row predicate; use require_create")
        field_key = self._validate_field(registration, field)
        identity_expression = self._identity_expression(registration, Model)
        resource_gate = self._grant_exists_expression(
            context,
            registration,
            normalized_action,
            _RESOURCE_FIELD,
            object_expression=identity_expression,
        )
        conditions = [resource_gate]
        if field_key:
            conditions.append(
                self._grant_exists_expression(
                    context,
                    registration,
                    normalized_action,
                    field_key,
                    object_expression=identity_expression,
                )
            )
        if registration.tenant_column is not None:
            if context is None:
                conditions.append(false())
            else:
                conditions.append(
                    getattr(Model, str(registration.tenant_column.key))
                    == self._tenant_python_value(registration, context)
                )
        return and_(*conditions)

    def scope_query(
        self,
        context: Optional[AuthContext],
        Model: type[Any],
        query: Any,
        *,
        action: str = "read",
        fields: Iterable[str] = (),
    ) -> Any:
        """Apply row, tenant, and query-field gates to a composable query."""
        if not self.is_registered(Model):
            return query
        if not hasattr(query, "filter") or not callable(query.filter):
            raise UnAuthorizedError("Protected models require a composable SQLAlchemy query")
        if (
            getattr(query, "_limit_clause", None) is not None
            or getattr(query, "_offset_clause", None) is not None
        ):
            raise UnAuthorizedError(
                "Protected custom queries must be unpaginated before authorization"
            )
        scoped = query.filter(self.predicate(context, Model, action))
        for field in dict.fromkeys(str(name) for name in fields if name and name != "id"):
            scoped = scoped.filter(self.predicate(context, Model, action, field))
        return scoped

    def require(
        self,
        session: Any,
        context: Optional[AuthContext],
        instance: Any,
        action: str,
        fields: Iterable[str] = (),
        *,
        response_check: bool = False,
    ) -> None:
        """Require a row gate and every requested field gate using SQL."""
        Model = instance.__class__
        if not self.is_registered(Model):
            return
        registration = self._registration(Model)
        normalized_action = self._validate_action(action)
        if normalized_action == "create":
            raise ValueError("Use require_create for create authorization")
        field_names = tuple(dict.fromkeys(str(field) for field in fields if field and field != "id"))
        self._ensure_update_fields_supported(registration, field_names)
        self._ensure_foreign_key_fields_supported(registration, field_names)
        conditions = [
            getattr(Model, registration.pk_attribute) == self._pk_value(registration, instance),
            self.predicate(context, Model, normalized_action),
        ]
        conditions.extend(
            self.predicate(context, Model, normalized_action, field) for field in field_names
        )
        statement = select(registration.pk_column).select_from(Model).where(*conditions).limit(1)
        if normalized_action == "delete":
            statement = statement.with_for_update()
        if session.execute(statement).first() is None:
            if normalized_action == "read" and not response_check:
                # Missing and unreadable objects deliberately share one result.
                raise NotFoundError()
            raise UnAuthorizedError("Resource operation is not authorized")

    def require_create(
        self,
        session: Any,
        context: Optional[AuthContext],
        Model: type[Any],
        fields: Iterable[str] = (),
        values: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """Require model-scope create and submitted-field grants."""
        _ = session
        if not self.is_registered(Model):
            return
        registration = self._registration(Model)
        field_names = tuple(dict.fromkeys(str(field) for field in fields if field and field != "id"))
        self._ensure_foreign_key_fields_supported(registration, field_names)
        if registration.tenant_column is not None:
            if context is None:
                raise UnAuthorizedError("Tenant context is required")
            tenant_value = self._tenant_python_value(registration, context)
            tenant_name = str(registration.tenant_column.key)
            if values is None or tenant_name not in values:
                raise UnAuthorizedError("Tenant field is required for protected resource creation")
            if tenant_name in values:
                try:
                    python_type = registration.tenant_column.property.columns[0].type.python_type
                    submitted_tenant = python_type(values[tenant_name])
                except Exception as exc:
                    raise UnAuthorizedError("Submitted tenant is invalid") from exc
                if submitted_tenant != tenant_value:
                    raise UnAuthorizedError("Submitted tenant does not match authorization context")
        for field_name in field_names:
            self._validate_field(registration, field_name)
        required_fields = (_RESOURCE_FIELD, *field_names)
        for field_key in required_fields:
            if not self._model_scope_grant_exists(session, context, registration, "create", field_key):
                raise UnAuthorizedError("Resource creation is not authorized")

    def _model_scope_grant_exists(
        self,
        session: Any,
        context: Optional[AuthContext],
        registration: _ModelRegistration,
        action: str,
        field_key: str,
    ) -> bool:
        if context is None or not context.subject_keys:
            return False
        grant = self.table
        statement = select(literal(1)).select_from(grant).where(
            grant.c.scope_key == context.scope_key,
            grant.c.subject_key.in_(context.subject_keys),
            grant.c.model_key == registration.key,
            grant.c.action == action,
            grant.c.object_key == _MODEL_OBJECT,
            grant.c.field_key == field_key,
        ).limit(1)
        return session.execute(statement).first() is not None

    def readable_fields(
        self,
        session: Any,
        context: Optional[AuthContext],
        Model: type[Any],
        instances: Sequence[Any],
    ) -> dict[str, frozenset[str]]:
        """Batch-load readable field names for already row-authorized objects."""
        if not self.is_registered(Model):
            return {}
        registration = self._registration(Model)
        object_keys = [self.object_key(Model, instance) for instance in instances]
        if not object_keys or context is None or not context.subject_keys:
            return {object_key: frozenset() for object_key in object_keys}
        grant = self.table
        rows = session.execute(
            select(grant.c.object_key, grant.c.field_key).where(
                grant.c.scope_key == context.scope_key,
                grant.c.subject_key.in_(context.subject_keys),
                grant.c.model_key == registration.key,
                grant.c.action == "read",
                grant.c.field_key != _RESOURCE_FIELD,
                grant.c.object_key.in_([_MODEL_OBJECT, *object_keys]),
            )
        ).all()
        model_fields = {str(field_key) for object_key, field_key in rows if object_key == _MODEL_OBJECT}
        exact: dict[str, set[str]] = {object_key: set(model_fields) for object_key in object_keys}
        for object_key, field_key in rows:
            if object_key in exact:
                exact[str(object_key)].add(str(field_key))
        return {key: frozenset(value) for key, value in exact.items()}

    def _ensure_update_fields_supported(
        self, registration: _ModelRegistration, fields: Sequence[str]
    ) -> None:
        immutable = {registration.pk_attribute}
        if registration.tenant_column is not None:
            immutable.add(str(registration.tenant_column.key))
        if immutable.intersection(fields):
            raise UnAuthorizedError("Identity and tenant fields are immutable")

    def _ensure_foreign_key_fields_supported(
        self, registration: _ModelRegistration, fields: Sequence[str]
    ) -> None:
        mapper = sqlalchemy.inspect(registration.model)
        for field in fields:
            try:
                prop = mapper.attrs[field]
            except KeyError:
                continue
            columns = list(getattr(prop, "columns", ()) or ())
            for column in columns:
                for foreign_key in column.foreign_keys:
                    target_table = str(getattr(foreign_key.column.table, "fullname", foreign_key.column.table.name))
                    if registration.model in self._registrations or target_table in self._registrations_by_table:
                        raise UnAuthorizedError(
                            "Foreign-key assignments involving protected models require explicit integration"
                        )

    def ensure_foreign_key_fields_supported_for_model(
        self, Model: type[Any], fields: Iterable[str]
    ) -> None:
        try:
            mapper = sqlalchemy.inspect(Model)
        except Exception:
            return
        protected_relationship = self.is_registered(Model) or any(
            self.is_registered(relationship.mapper.class_)
            for relationship in mapper.relationships
        )
        for field in fields:
            # A writable jsonapi_attr is arbitrary Python and SAFRS cannot
            # prove that its setter does not assign a hidden FK. Keep these
            # aliases fail-closed on models participating in protected
            # relationships; an explicit reviewed operation is required.
            from .jsonapi_attr import is_jsonapi_attr, lookup_jsonapi_attr

            jsonapi_attribute = lookup_jsonapi_attr(Model, str(field))
            if (
                protected_relationship
                and is_jsonapi_attr(jsonapi_attribute)
                and getattr(jsonapi_attribute, "fset", None) is not None
            ):
                raise UnAuthorizedError(
                    "Writable aliases involving protected models require explicit integration"
                )
            try:
                prop = mapper.attrs[str(field)]
            except KeyError:
                continue
            for column in list(getattr(prop, "columns", ()) or ()):
                for foreign_key in column.foreign_keys:
                    target_table = str(
                        getattr(foreign_key.column.table, "fullname", foreign_key.column.table.name)
                    )
                    if self.is_registered(Model) or target_table in self._registrations_by_table:
                        raise UnAuthorizedError(
                            "Foreign-key assignments involving protected models require explicit integration"
                        )

    def reject_relationship_mutation(self, parent_model: type[Any], target_model: type[Any]) -> None:
        if self.is_registered(parent_model) or self.is_registered(target_model):
            raise UnAuthorizedError(
                "Relationship mutations involving protected models are not supported by the registry"
            )

    def ensure_delete_supported(self, instance: Any) -> None:
        Model = instance.__class__
        mapper = sqlalchemy.inspect(Model)
        for relationship in mapper.relationships:
            target_model = relationship.mapper.class_
            if not self.is_registered(Model) and not self.is_registered(target_model):
                continue
            changes_other_rows = (
                relationship.secondary is not None
                or str(getattr(relationship.direction, "name", "")) == "ONETOMANY"
                or bool(getattr(relationship.cascade, "delete", False))
                or bool(getattr(relationship.cascade, "delete_orphan", False))
            )
            if not changes_other_rows:
                continue
            value = getattr(instance, relationship.key)
            if value is not None and (not hasattr(value, "__len__") or len(value) > 0):
                raise UnAuthorizedError(
                    "Deleting protected resources with relationship side effects requires explicit integration"
                )

    def delete_requires_protection(self, Model: type[Any]) -> bool:
        if self.is_registered(Model):
            return True
        try:
            mapper = sqlalchemy.inspect(Model)
        except Exception:
            return False
        return any(self.is_registered(relationship.mapper.class_) for relationship in mapper.relationships)

    def delete_instance_grants(self, session: Any, instance: Any) -> None:
        Model = instance.__class__
        if not self.is_registered(Model):
            return
        registration = self._registration(Model)
        session.execute(
            delete(self.table).where(
                self.table.c.model_key == registration.key,
                self.table.c.object_key == self.object_key(Model, instance),
            )
        )
        self._clear_current_request_cache()

    @staticmethod
    def serialize_sqlite_write(session: Any) -> None:
        """Acquire SQLite's database write reservation before lifecycle reads.

        PostgreSQL serializes grant/delete through target-row locks. SQLite has
        no row locks, so grant creation and SAFRS delete handlers begin an
        IMMEDIATE transaction before checking the target. If the connection is
        already in a DBAPI transaction, a prior write already owns the needed
        reservation.
        """
        if str(session.get_bind().dialect.name) != "sqlite":
            return
        connection = session.connection()
        proxy = getattr(connection, "connection", None)
        driver_connection = getattr(proxy, "driver_connection", proxy)
        if not bool(getattr(driver_connection, "in_transaction", False)):
            connection.exec_driver_sql("BEGIN IMMEDIATE")

    def _validate_grant_arguments(
        self,
        Model: type[Any],
        action: str,
        object_id: Any,
        field: Optional[str],
    ) -> tuple[_ModelRegistration, str, str, str]:
        registration = self._registration(Model)
        normalized_action = self._validate_action(action)
        field_key = self._validate_field(registration, field)
        if normalized_action == "create" and object_id is not None:
            raise ValueError("Create grants must use model scope")
        if normalized_action == "delete" and field_key:
            raise ValueError("Delete grants cannot target fields")
        object_key = _MODEL_OBJECT if object_id is None else self.object_key(Model, object_id)
        return registration, normalized_action, object_key, field_key

    def _require_administration_target(
        self,
        session: Any,
        registration: _ModelRegistration,
        object_id: Any,
        tenant_id: Optional[str],
    ) -> None:
        if object_id is None:
            return
        conditions = [
            getattr(registration.model, registration.pk_attribute)
            == self._pk_value(registration, object_id)
        ]
        if registration.tenant_column is not None:
            if tenant_id is None:
                raise ValueError("tenant_id is required for an exact grant on a tenant model")
            try:
                python_type = registration.tenant_column.property.columns[0].type.python_type
                conditions.append(registration.tenant_column == python_type(tenant_id))
            except Exception as exc:
                raise ValueError("Invalid tenant_id") from exc
        statement = (
            select(registration.pk_column)
            .select_from(registration.model)
            .where(*conditions)
            .with_for_update()
            .limit(1)
        )
        if session.execute(statement).first() is None:
            raise ValueError("Authorization grant target does not exist")

    def grant(
        self,
        session: Any,
        *,
        scope_key: str,
        subject_key: str,
        Model: type[Any],
        action: str,
        object_id: Any = None,
        field: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> bool:
        """Stage an idempotent grant in the caller's transaction."""
        scope = str(scope_key).strip()
        subject = str(subject_key).strip()
        if not scope or not subject:
            raise ValueError("scope_key and subject_key are required")
        registration, normalized_action, object_key, field_key = self._validate_grant_arguments(
            Model, action, object_id, field
        )
        if object_id is not None:
            self.serialize_sqlite_write(session)
        self._require_administration_target(session, registration, object_id, tenant_id)
        values = {
            "scope_key": scope,
            "subject_key": subject,
            "model_key": registration.key,
            "action": normalized_action,
            "object_key": object_key,
            "field_key": field_key,
        }
        conflict_columns = [
            "scope_key",
            "subject_key",
            "model_key",
            "action",
            "object_key",
            "field_key",
        ]
        dialect_name = str(session.get_bind().dialect.name)
        if dialect_name == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert

            result = session.execute(
                sqlite_insert(self.table).values(**values).on_conflict_do_nothing(
                    index_elements=conflict_columns
                )
            )
            created = bool(getattr(result, "rowcount", 0))
        elif dialect_name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as postgresql_insert

            result = session.execute(
                postgresql_insert(self.table).values(**values).on_conflict_do_nothing(
                    index_elements=conflict_columns
                )
            )
            created = bool(getattr(result, "rowcount", 0))
        else:
            present = session.execute(select(self.table.c.id).where(
                *(self.table.c[name] == value for name, value in values.items())
            ).limit(1)).first()
            if present is not None:
                return False
            session.execute(insert(self.table).values(**values))
            created = True
        if not created:
            return False
        self._clear_current_request_cache()
        safrs.log.info(
            "Authorization grant staged for model=%s action=%s field=%s",
            registration.key,
            normalized_action,
            field_key or "resource",
        )
        return True

    def revoke(
        self,
        session: Any,
        *,
        scope_key: str,
        subject_key: str,
        Model: type[Any],
        action: str,
        object_id: Any = None,
        field: Optional[str] = None,
    ) -> int:
        """Stage a precise grant revocation in the caller's transaction."""
        scope = str(scope_key).strip()
        subject = str(subject_key).strip()
        if not scope or not subject:
            raise ValueError("scope_key and subject_key are required")
        registration, normalized_action, object_key, field_key = self._validate_grant_arguments(
            Model, action, object_id, field
        )
        result = session.execute(delete(self.table).where(
            self.table.c.scope_key == scope,
            self.table.c.subject_key == subject,
            self.table.c.model_key == registration.key,
            self.table.c.action == normalized_action,
            self.table.c.object_key == object_key,
            self.table.c.field_key == field_key,
        ))
        count = int(getattr(result, "rowcount", 0) or 0)
        self._clear_current_request_cache()
        safrs.log.info(
            "Authorization revoke staged for model=%s action=%s field=%s",
            registration.key,
            normalized_action,
            field_key or "resource",
        )
        return count

    @staticmethod
    def _clear_current_request_cache() -> None:
        from .jsonapi_context import maybe_jsonapi_context

        context = maybe_jsonapi_context()
        if context is not None:
            context.authorization_field_masks.clear()
            context.authorization_decisions.clear()


def _current_state() -> tuple[Optional[AuthorizationRegistry], Optional[AuthContext], Any]:
    from .jsonapi_context import maybe_jsonapi_context

    jsonapi_context = maybe_jsonapi_context()
    if jsonapi_context is None:
        return None, None, None
    registry = getattr(jsonapi_context, "authorization_registry", None)
    context = getattr(jsonapi_context, "authorization_context", None)
    return registry, context, jsonapi_context


def apply_authorization_scope(
    Model: type[Any],
    query: Any,
    *,
    action: str = "read",
    fields: Iterable[str] = (),
) -> Any:
    registry, context, _jsonapi_context = _current_state()
    if registry is None or not registry.is_registered(Model):
        return query
    return registry.scope_query(context, Model, query, action=action, fields=fields)


def current_query_fields(Model: type[Any]) -> tuple[str, ...]:
    """Return fields whose values influence the current filter or sort."""
    registry, _context, jsonapi_context = _current_state()
    if registry is None or not registry.is_registered(Model) or jsonapi_context is None:
        return ()
    names: list[str] = []
    for key, _value in jsonapi_context.query_multi_items():
        if key.startswith("filter[") and key.endswith("]"):
            names.append(key[len("filter[") : -1])
    raw_filter = None
    getter = getattr(jsonapi_context.query_params, "get", None)
    if callable(getter):
        raw_filter = getter("filter")
    if raw_filter:
        from .filtering import (
            custom_filter_read_fields,
            filter_attribute_names,
            uses_builtin_json_filter,
        )

        if "filter" in Model.__dict__ and callable(getattr(Model, "filter")):
            names.extend(custom_filter_read_fields(Model, getattr(Model, "filter")))
        elif uses_builtin_json_filter(Model):
            names.extend(filter_attribute_names(str(raw_filter)))
        else:
            names.extend(custom_filter_read_fields(Model, getattr(Model, "_s_filter")))
    raw_sort = getter("sort") if callable(getter) else None
    for term in str(raw_sort or "id").split(","):
        name = term.strip().lstrip("-")
        if name and name != "id":
            names.append(name)
    registration = registry._registration(Model)
    for name in names:
        registry._validate_field(registration, name)
    return tuple(dict.fromkeys(names))


def require_current_instance(
    instance: Any,
    action: str,
    fields: Iterable[str] = (),
    *,
    response_check: Optional[bool] = None,
) -> None:
    registry, context, jsonapi_context = _current_state()
    Model = instance.__class__
    if registry is None or not registry.is_registered(Model):
        return
    is_response_check = (
        bool(getattr(jsonapi_context, "authorization_response_check", False))
        if response_check is None
        else response_check
    )
    cache_key = (
        Model,
        registry.object_key(Model, instance),
        action,
        tuple(sorted(fields)),
        is_response_check,
    )
    decision_cache = getattr(jsonapi_context, "authorization_decisions", None)
    if decision_cache is not None and cache_key in decision_cache:
        return
    from .runtime import get_db

    registry.require(
        get_db().session,
        context,
        instance,
        action,
        fields,
        response_check=is_response_check,
    )
    if decision_cache is not None:
        decision_cache.add(cache_key)


def require_current_create(
    Model: type[Any], fields: Iterable[str], values: Optional[Mapping[str, Any]] = None
) -> None:
    registry, context, _jsonapi_context = _current_state()
    if registry is None or not registry.is_registered(Model):
        return
    from .runtime import get_db

    registry.require_create(get_db().session, context, Model, fields, values)


def run_current_after_create(instance: Any) -> None:
    registry, context, _jsonapi_context = _current_state()
    if (
        registry is None
        or context is None
        or not registry.is_registered(instance.__class__)
        or registry.after_create is None
    ):
        return
    from .runtime import get_db

    registry.after_create(registry, get_db().session, context, instance)
    registry._clear_current_request_cache()


def prepare_current_readable_fields(Model: type[Any], instances: Iterable[Any]) -> None:
    registry, context, jsonapi_context = _current_state()
    if registry is None or not registry.is_registered(Model) or jsonapi_context is None:
        return
    items = [item for item in instances if isinstance(item, Model)]
    missing = [
        item
        for item in items
        if (Model, registry.object_key(Model, item)) not in jsonapi_context.authorization_field_masks
    ]
    if not missing:
        return
    from .runtime import get_db

    masks = registry.readable_fields(get_db().session, context, Model, missing)
    for object_key, fields in masks.items():
        jsonapi_context.authorization_field_masks[(Model, object_key)] = fields


def current_readable_fields(instance: Any) -> Optional[frozenset[str]]:
    registry, _context, jsonapi_context = _current_state()
    Model = instance.__class__
    if registry is None or not registry.is_registered(Model) or jsonapi_context is None:
        return None
    prepare_current_readable_fields(Model, [instance])
    return jsonapi_context.authorization_field_masks.get(
        (Model, registry.object_key(Model, instance)), frozenset()
    )


def reject_current_relationship_mutation(parent_model: type[Any], target_model: type[Any]) -> None:
    registry, _context, _jsonapi_context = _current_state()
    if registry is not None:
        registry.reject_relationship_mutation(parent_model, target_model)


def current_model_is_registered(Model: type[Any]) -> bool:
    registry, _context, _jsonapi_context = _current_state()
    return bool(registry is not None and registry.is_registered(Model))


def reject_current_rpc(Model: type[Any]) -> None:
    if current_model_is_registered(Model):
        raise UnAuthorizedError(
            "RPC operations on protected models require explicit application integration"
        )


def reject_current_relationship_fields(Model: type[Any], fields: Iterable[str]) -> None:
    registry, _context, _jsonapi_context = _current_state()
    if registry is None:
        return
    try:
        mapper = sqlalchemy.inspect(Model)
    except Exception:
        return
    relationships = {str(relationship.key): relationship for relationship in mapper.relationships}
    for field in fields:
        relationship = relationships.get(str(field))
        if relationship is not None:
            registry.reject_relationship_mutation(Model, relationship.mapper.class_)


def reject_current_foreign_key_fields(Model: type[Any], fields: Iterable[str]) -> None:
    registry, _context, _jsonapi_context = _current_state()
    if registry is not None:
        registry.ensure_foreign_key_fields_supported_for_model(Model, fields)


def prepare_current_delete(instance: Any) -> None:
    registry, _context, _jsonapi_context = _current_state()
    if registry is None:
        return
    from .runtime import get_db

    registry.ensure_delete_supported(instance)
    if registry.is_registered(instance.__class__):
        require_current_instance(instance, "delete")
        registry.delete_instance_grants(get_db().session, instance)


def begin_current_protected_write(Model: type[Any]) -> None:
    registry, _context, _jsonapi_context = _current_state()
    if registry is None or not registry.delete_requires_protection(Model):
        return
    from .runtime import get_db

    registry.serialize_sqlite_write(get_db().session)
