# Security hardening

SAFRS treats authorization and resource limits as request-boundary contracts.
Applications still provide the actual identity and policy logic: Flask uses
decorators and `_s_check_perm`, while FastAPI uses dependencies.

## Authorization contracts

- Field metadata is evaluated for each request. Caller-dependent
  `_s_check_perm` results are not cached across requests, and POST rechecks
  write permission on the initialized instance before it is persisted.
- A relationship endpoint can expose only methods allowed by its relationship,
  parent model, and target model. Nested creates/updates and ORM cascade
  deletes enforce the target model's corresponding `http_methods` restriction.
- Authorization on a related model also protects parent traversal, includes,
  nested writes, cascades, and relationship responses.
- Flask `HEAD` inherits `GET` authorization unless an explicit `head`
  `method_decorators` entry is configured.
- POST and PATCH apply the Flask `GET` policy before returning a resource
  representation. A denied read policy rolls the write back rather than
  returning data the caller cannot fetch directly.
- Decorators are deduplicated by identity without changing their configured
  order. A disabled Flask method returns `405 Method Not Allowed`.

POST upserts remain upserts. When a client-generated id resolves to an existing
row, SAFRS authorizes the update with the explicit Flask `upsert` policy or the
`patch` policy fallback. New rows use the POST policy. Creation is protected
against lookup/insert races: a row inserted after the lookup produces `409
Conflict` and is never silently updated. See the wiki's Upserts page for the
complete policy mapping.

## Request-complexity limits

The following defaults apply to Flask and FastAPI:

| Setting | Default | Scope |
| --- | ---: | --- |
| `DEFAULT_PAGE_LIMIT` | `250` | Page size when omitted |
| `MAX_PAGE_LIMIT` | `1000` | Maximum collection and relationship page size |
| `MAX_BULK_ITEMS` | `1000` | Bulk documents and relationship arrays |
| `MAX_INCLUDE_DEPTH` | `5` | Segments in one include path |
| `MAX_INCLUDE_PATHS` | `25` | Include paths, including `+all` expansion |
| `MAX_INCLUDED_RESOURCES` | `1000` | Total resources in the top-level `included` array |

Set these in `app.config` before initializing Flask SAFRS. Flask keeps an
application-local snapshot, so one Flask application's values do not change
another application's settings. FastAPI currently reads the `SAFRS` class
settings; configure them before constructing `SafrsFastAPI`.

A non-positive request-complexity limit disables that individual limit. This
is not recommended for an internet-facing API.

## Multi-application schema isolation

Flask API operation ids, exposed ALS resources, configuration, and copied
Swagger definitions are isolated per API/application. Only schema definitions
reachable from the current API's paths are published; a model exposed by a
different Flask app in the same process is not copied into this app's
`swagger.json`.
