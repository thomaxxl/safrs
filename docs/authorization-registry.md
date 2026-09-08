# Lightweight authorization registry

SAFRS provides an optional sparse, SQL-backed authorization registry for
applications that need per-user or per-group row and field permissions. It
reuses application authentication and the request's existing SQLAlchemy
session. When no registry is configured, SAFRS behaves as before and performs
no grant queries.

The registry is allow-only and default-deny for registered models. A resource
grant permits the row identifier; a separate field grant permits an attribute
or relationship. Both gates must match the request scope and one effective
subject. User and group grants combine by union. Existing SAFRS exposure,
HTTP-method, read-only, query-scope, decorator/dependency, and object-policy
restrictions remain additional limits.

## Grant table and registration

Create the registry against the same metadata Alembic uses, register every
protected model with a stable application-owned key, then construct the API:

```python
from safrs import AuthContext, AuthorizationRegistry, SafrsApi

authz = AuthorizationRegistry(metadata=db.metadata)
authz.register(Invoice, key="billing.invoice", tenant_column=Invoice.tenant_id)

def principal():
    identity = current_user  # resolved by the application
    return AuthContext(
        scope_key=f"tenant:{identity.tenant_id}",
        subject_keys=(f"user:{identity.id}", *identity.group_keys),
        tenant_id=str(identity.tenant_id),
    )

api = SafrsApi(
    app,
    app_db=db,
    authorization=authz,
    principal_provider=principal,
)
api.expose_object(Invoice)
```

FastAPI uses a normal dependency so authentication, overrides, async code, and
dependency cleanup retain native behavior:

```python
async def principal(user=Depends(authenticated_user)):
    return AuthContext("billing", (f"user:{user.id}", *user.group_keys))

api = SafrsFastAPI(
    app,
    app_db=db,
    authorization=authz,
    principal_dependency=principal,
)
```

The adapter freezes registrations at startup. Do not reuse one registry across
different SQLAlchemy metadata objects. V1 accepts one integer or text primary
key; composite, UUID, custom-collation, and other identities fail registration
until an explicit tested identity adapter is added.

`AuthorizationRegistry.bind()` declares `safrs_auth_grant` in the supplied
metadata but never executes DDL. Include that metadata in Alembic autogenerate,
or create an equivalent migration with these non-null columns:

```text
id Integer primary key
scope_key String(255)
subject_key String(255)
model_key String(255)
object_key String(1024)
field_key String(255)
action String(16)
```

Preserve the generated unique constraint over scope, subject, model, action,
object, and field; the resource lookup index; and the action/create/delete
CHECK constraints. Empty strings are internal model/resource markers. Public
helpers use `object_id=None` and `field=None`.

## Seeding and administration

Grant and revoke are trusted application operations. They validate registered
models, fields, actions, and exact targets, use the caller's session, and never
commit:

```python
authz.grant(
    db.session,
    scope_key="tenant:7",
    subject_key="group:finance",
    Model=Invoice,
    action="read",
    object_id=42,       # omit for all rows
)
authz.grant(
    db.session,
    scope_key="tenant:7",
    subject_key="group:finance",
    Model=Invoice,
    action="read",
    field="amount",
)
db.session.commit()
```

Create grants are model-scoped. Delete grants are resource-only. There is no
field wildcard, implicit owner, administrator bypass, role hierarchy, or grant
management HTTP API. Subject membership is resolved once by the application
and bounded by `max_subjects`.

An optional `after_create(registry, session, context, instance)` callback may
seed exact grants in the same request transaction. A failure or denied write
response rolls back both the object and bootstrap grants.

## Enforcement behavior

- Correlated `EXISTS` predicates scope rows before filters, sorting, counts, and
  pagination. Query fields add their field-read predicate to that relation.
- A previously loaded ORM instance is checked with a fresh SQL authorization
  query; the identity map never counts as authorization.
- Unreadable scalar getters are not evaluated. Relationships are omitted when
  their parent field grant is missing, and targets use their own scoped query.
- Single-object GET uses the same 404 for absent and unreadable rows. A denied
  representation returned by POST/PATCH is 403 and rolls back the write.
- Create authorizes the original fields before construction. Existing-row POST
  upsert requires UPDATE resource and field grants, regardless of HTTP method.
- Identity and tenant fields are immutable through generic update. A generic
  tenant create must submit the trusted tenant value.
- Exact grants are deleted in the same transaction as the row. PostgreSQL uses
  target-row locking; SQLite lifecycle helpers acquire an immediate write
  reservation before checking the target.

The first release deliberately rejects relationship mutations, nested writes,
client-supplied foreign keys involving protected models, deletes with detected
cross-row effects, and RPC calls owned by registered models. Integrate and
review their complete physical effects before enabling those paths. Writable
`jsonapi_attr` aliases on models participating in protected relationships are
also rejected because SAFRS cannot prove that an arbitrary setter does not
assign a hidden foreign key. Relationship
reads and includes are supported and do not spread target policy to unrelated
parent routes.

This boundary covers SAFRS-managed operations. It does not sandbox trusted
Python, arbitrary ORM/raw SQL, custom serializers, or other application routes.
Custom collection hooks for protected models must return a composable,
unpaginated SQLAlchemy query; SAFRS rejects Python lists rather than performing
an unbounded authorization scan.
