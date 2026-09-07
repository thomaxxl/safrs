# FastAPI authorization

Ordinary `dependencies=[...]` retain FastAPI's route-local meaning. They can
authenticate a request, consume a rate limit, record an audit event, or manage a
client. SAFRS never copies them to related models or replays them to authorize a
response. Constructor dependencies apply to all generated routes; per-model
dependencies apply only to that model's generated routes, including its RPCs
and relationship routes.

Use explicit operation policies for access that must also apply when another
route accesses the model:

```python
from fastapi import Depends, HTTPException, Request

async def authenticate(request: Request):
    request.state.user = await authenticate_request(request)

def require_read(request: Request):
    if not request.state.user.can_read_books:
        raise HTTPException(403, "Book reads are forbidden")

def require_update(request: Request):
    if not request.state.user.can_edit_books:
        raise HTTPException(403, "Book updates are forbidden")

def authorize_book(model, instance, request):
    return instance.tenant_id == request.state.user.tenant_id

api = SafrsFastAPI(app, dependencies=[Depends(authenticate)])
api.expose_object(
    Book,
    read_dependencies=[Depends(require_read)],
    update_dependencies=[Depends(require_update)],
    response_authorizer=authorize_book,
)
```

Both `SafrsFastAPI(...)` and `expose_object(...)` accept `read_dependencies`,
`create_dependencies`, `update_dependencies`, `delete_dependencies`, and
`response_authorizer`. Global and model-specific policies are additive. The
dependency lists accept callables, `Depends`, and `Security`.

| Operation | Explicit policies |
| --- | --- |
| Collection or instance GET | Model read policy; object checks on returned rows |
| POST creating a row | Create before mutation, read before its representation |
| POST upsert of an existing row | Update before mutation, read before its representation |
| PATCH | Update before mutation, read before its representation |
| DELETE | Delete; cascade target delete policies and object hooks |
| Relationship GET | Parent and target read policies; target object checks |
| Relationship mutation | Parent and affected target update policies; link/unlink object hooks; read checks if a representation is returned |
| Requested include | Read policy for each traversed target; object checks on included rows |
| GET RPC | RPC model read policy, plus policies for resource results |
| Write RPC | RPC model update policy, plus policies for resource results |

Exposing a restricted child does not change access to plain parent reads,
writes, deletes, or unrelated RPCs. Its policy applies when that child is
actually accessed. A denied response check rejects the document and rolls back
the request's write before commit. It does not silently filter rows using
`response_authorizer`; that would leave response counts and links ambiguous.

`response_authorizer(model, instance, request)` is a sync or async callback.
Return `False` or raise an exception to deny; `None` and `True` allow. It is
called for concrete returned resources, including lists, includes and resource
RPC results. Successful checks for the same object are reused during response
serialization. `_s_check_instance_access(action)` remains the object hook for
link, unlink and cascade decisions. Neither route policies nor response checks
replace a database query scoped to the current principal: scope queries before
pagination/counting when rows must be hidden, not merely denied on retrieval.
Arbitrary scalar RPC payloads are application-owned and cannot be recognized as
protected model representations by the framework.

Override `Model._s_query_scope(query_or_items)` to apply the current
principal's SQL predicate. SAFRS invokes it before ordering, totals, page
links, and slicing for collections, relationships, and includes. If a model
has a per-object policy but no database scope, SAFRS performs a bounded
fail-closed scan (`MAX_AUTHORIZATION_SCAN`) and rejects a document containing a
denied row. This fallback is safe but intentionally not a substitute for an
efficient tenant/owner predicate.

## Request and dependency lifecycle

Explicit policies receive the **original request**, with its original method,
URL, body, path parameters and `request.state`. A read policy for a POST response
sees POST. Select read/create/update/delete behavior through the registration
arguments, not by inferring it from `request.method`. Use the object callback
for a target ID; the URL of a relationship request contains the parent's ID.

Only explicitly declared policies enter the authorization dependency graph.
They support nested dependencies, Security scopes, dependency overrides and
sync/async generators. The graph has one dependency cache per request and its
yield resources close before SAFRS commits the unit of work. Native route
dependencies keep their native cache and lifetimes; the two graphs deliberately
do not share a hidden FastAPI cache. Use `request.state` for a principal or
client initialized by an ordinary dependency, rather than declaring that
side-effecting dependency again inside a policy.

An operation policy runs once per model and operation within a request.
Dependency `use_cache=False` applies within each such evaluation; it does not
turn a coarse model policy into a per-object check. Per-resource decisions
belong in `response_authorizer` or `_s_check_instance_access`.

SAFRS uses a separate bounded worker limiter for synchronous authorization
dependencies. It never changes AnyIO's shared worker capacity. Async policies
run on the application's event loop. A body-reading dependency observes the
original cached body, never a POST stream relabelled as GET.

`docs_dependencies` are installed as native FastAPI route dependencies for
`/docs`, `/redoc`, `/openapi.json`, and `/swagger.json`. Nested `Depends` and
`Security`, overrides, caching, and generator cleanup therefore work normally.
Configured documentation protection is never disabled by DEBUG logging. SAFRS
warns once if model authorization is configured while documentation remains
public.

## Migration from PR #200's implicit replay

Keep auditing, rate limiting, client setup, and ordinary route authentication in
`dependencies`. Move cross-resource read checks to `read_dependencies`. Replace
method-switching authorization dependencies with separate create/update/delete
checks, and move URL-ID-based response policies to `response_authorizer`.
Applications that depended on implicit propagation must migrate explicitly;
ordinary dependencies alone do not protect access through other model routes.

Upsert remains upsert: the existing-row branch requires update permission and
does not require create permission. The new-row branch requires create
permission. Disabling the PATCH route does not disable POST upsert. A bulk POST
may require both permissions, and denial rolls back the entire request.
GET route availability and permission to return a representation are distinct;
write-only APIs can set a read policy for their write responses.

Request bodies are limited by `MAX_REQUEST_BODY_BYTES`; JSON nesting and total
resource objects are limited by `MAX_JSON_DEPTH` and
`MAX_REQUEST_RESOURCES`. Set these before constructing `SafrsFastAPI` when an
application needs different bounds.

Pass `app_db=` to bind an API instance to its database explicitly. Requests
activate that binding automatically. For a background task or script, use
`with api.runtime_context():` so model operations cannot select another API's
session after multiple applications have been initialized. If `app_db` is
omitted, the current legacy `safrs.DB` value is captured once at adapter
construction; it is never looked up again during a request.
