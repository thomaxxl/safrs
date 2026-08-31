# Security TODO

This file tracks security work that remains open after the authorization,
upsert, request-limit, and built-in filter hardening completed through commit
`069cdb4`. Items are ordered by likely impact. Severity assumes an
internet-facing API containing data with per-user or per-row access controls.

Do not close an item based only on a code change. Each item needs a regression
test for both Flask and FastAPI where the behavior exists in both adapters, plus
the full container test run described in `AGENTS.md`.

## High priority

### SEC-01 — Apply read authorization to FastAPI write and RPC responses

- [ ] Define a FastAPI equivalent of Flask's `_run_read_authorized` contract.
- [ ] Before returning a resource representation from POST, PATCH, relationship
  mutation, or RPC, evaluate the authorization policy that would protect a GET
  of the same resource.
- [ ] Roll back the write when response-read authorization fails; do not commit
  a mutation and then replace its representation with an error.
- [ ] Cover method-aware dependencies where POST/PATCH is allowed but GET is
  denied, including upsert and relationship responses.

Evidence: Flask explicitly re-enters its GET policy in
`safrs/jsonapi.py`, while FastAPI write handlers in `safrs/fastapi/api.py`
serialize their result directly. A dependency that branches on
`request.method` therefore sees POST/PATCH, not the equivalent GET operation.

Done when no FastAPI non-GET endpoint can return a representation that the
same principal is forbidden to retrieve through GET.

### SEC-02 — Authorize every resource affected by relationship and cascade operations

- [ ] Add an object-level authorization hook for each target loaded from a
  relationship payload, rather than relying only on one route-level decorator
  or dependency invocation.
- [ ] Apply it to relationship linkage POST/PATCH/DELETE, nested create/upsert,
  include traversal, and cascaded delete.
- [ ] Authorize removals as well as additions, including every member of a
  to-many replacement.
- [ ] Define fail-closed behavior for policies that require a target id or
  loaded target instance.

Evidence: `_parse_target_data` in `safrs/jsonapi.py` and
`_lookup_related_instance` in `safrs/fastapi/api.py` load target rows directly.
Current target-model route policies protect the route as a whole, but are not
called once for every target row in a body or cascade.

Done when a caller who may edit a parent cannot link, unlink, traverse, update,
or cascade-delete a target row that its object-level policy denies.

### SEC-03 — Remove process-global database and model routing state

- [ ] Replace request-time use of the mutable `safrs.DB` global with an
  app/adapter-bound session provider.
- [ ] Stop mutating shared model routing state such as `url_prefix` when a model
  is exposed by an application.
- [ ] Test two simultaneously active Flask/FastAPI applications with different
  databases, prefixes, identities, and policies in both initialization orders.
- [ ] Verify background tasks and concurrent requests cannot select another
  application's session or URL configuration.

Evidence: `SAFRS.init_app` assigns the selected extension to `safrs.DB`, and
core model/write paths later use `safrs.DB.session`. Exposing a model also
stores routing configuration on that shared model class.

Done when application A cannot influence queries, writes, links, or policy
evaluation performed for application B in the same Python process.

## Medium priority

### SEC-04 — Define a safe contract for custom filters and filter-like RPCs

- [ ] Require custom `filter`/`_s_filter` implementations to declare the fields
  they inspect, or provide a framework helper that performs authorization
  before their result count is observable.
- [ ] Document that overriding the built-in structured filter transfers this
  responsibility to application code until that contract exists.
- [ ] Audit any additional bundled RPC/query helpers through the same field
  resolver used by built-in filters.
- [ ] Add negative tests for custom filters attempting to query class-hidden
  and instance-hidden fields.

Evidence: built-in bracket/JSON filters and bundled search helpers now use the
shared permission-aware resolver. Arbitrary custom filter syntax cannot yet be
introspected safely, so compatibility overrides remain application-owned.

Done when every framework-supported filter path either enforces field read
authorization or requires an explicit, documented trusted-code opt-in.

### SEC-05 — Bound filter complexity and permission-filter materialization

- [ ] Add configurable limits for structured-filter node count, nesting depth,
  number of bracket filters, values per membership filter, and sort terms.
- [ ] Reject over-limit requests with a stable 400 response before constructing
  SQL expressions.
- [ ] Provide a database-level authorization predicate/hook for row-dependent
  policies so filtering does not need to call `.all()` before pagination.
- [ ] Add stress tests for deeply nested filters, very wide filters, and large
  result sets with instance-level `_s_check_perm` overrides.

Evidence: include, bulk, and page sizes are bounded, but filter AST complexity
is not. Row-dependent field checks currently materialize all matching rows to
ensure denied rows cannot influence counts or pagination.

Done when attacker-controlled filters have predictable CPU, memory, SQL-size,
and result-materialization bounds.

### SEC-06 — Make schema and documentation exposure authorization-aware

- [ ] Provide supported protection/disable controls for Flask `swagger.json`,
  Swagger UI, ALS schema, and FastAPI OpenAPI/docs routes.
- [ ] Do not derive public schema examples from live database identifiers.
- [ ] Ensure caller-dependent field and relationship policies cannot become a
  schema-enumeration oracle or leak one caller's schema to another.
- [ ] Add tests showing protected data routes do not leave their schema public
  by default or without an explicit warning/opt-in.

Evidence: model dependencies/decorators are attached to generated data routes,
not automatically to documentation routes. `_s_sample_id` may select the first
live database row while building examples.

Done when deployments can apply the same authentication boundary to data and
schema endpoints, and generated examples contain no live identifiers.

## Low priority

### SEC-07 — Redact secrets from debug responses and logs

- [ ] Separate detailed server diagnostics from client-visible debug errors.
- [ ] Redact query strings, RPC arguments, SQL parameter values, authorization
  headers, cookies, tokens, passwords, and secret-like attribute names.
- [ ] Add structured redaction tests for Flask and FastAPI error paths.
- [ ] Document production-safe logging defaults and a startup warning for
  unsafe debug configuration.

Evidence: debug-mode exceptions may include their original message in the
response; integrity diagnostics log SQL parameters and request URLs; Flask RPC
logging records the complete argument dictionary.

Done when enabling diagnostic logging does not disclose request credentials or
application data to clients or ordinary logs.

## Recommended order

1. SEC-01 and SEC-02: close response and per-object authorization gaps.
2. SEC-03: make authorization and persistence isolation reliable in multi-app
   deployments.
3. SEC-04 and SEC-05: finish the filter security contract without introducing
   an unbounded availability cost.
4. SEC-06 and SEC-07: harden operational metadata and diagnostics.
