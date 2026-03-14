# SAFRS Examples

Examples are grouped by purpose so it is clear where to start.

- Python target: `>=3.9`
- Install base deps: `pip install -r examples/requirements.txt`

## Start Here

1. `mini_app.py`
   - What it does: smallest Flask + SAFRS + SQLAlchemy API.
   - Run: `python examples/mini_app.py`
2. `demo_relationship.py`
   - What it does: adds to-one and to-many relationship endpoints.
   - Run: `python examples/demo_relationship.py [HOST]`
3. `mini_fastapi_app.py`
   - What it does: smallest FastAPI + SAFRS API setup.
   - Run: `python examples/mini_fastapi_app.py`
4. `demo_fastapi.py`
   - What it does: full FastAPI showcase with docs, filtering, relationships, and seed data.
   - Run: `python examples/demo_fastapi.py [HOST] [PORT]`
5. `demo_pythonanywhere_com.py`
   - What it does: canonical full Flask showcase used as the main large demo.
   - Run: `python examples/demo_pythonanywhere_com.py [HOST] [PORT]`

## Top-Level Demo Index

- `mini_app.py`: minimal Flask starter with one simple SQLAlchemy model.
- `mini_fastapi_app.py`: minimal FastAPI starter with one exposed model.
- `demo_relationship.py`: relationship basics (`User` -> `Book`) and includes behavior.
- `demo_pythonanywhere_com.py`: full Flask demo with RPC methods, custom attrs, and richer model graph.
- `demo_full.py`: compatibility wrapper that forwards to `demo_pythonanywhere_com.py`.
- `demo_fastapi.py`: FastAPI equivalent of the full demo with OpenAPI generation.
- `demo_stateless.py`: exposes a non-SQLAlchemy SAFRS resource using custom query/relationship hooks.
- `demo_http_get.py`: demonstrates custom HTTP method exposure (`GET`) on resource endpoints.
- `demo_http_method.py`: demonstrates JSON:API response validation and custom method handling.
- `demo_flaskrestjsonapi.py`: side-by-side integration-style demo against `flask-rest-jsonapi`.
- `demo_geoalchemy.py`: spatial model demo (GeoAlchemy/PostGIS).
- `demo_devto.py`: older compact Flask demo variant.
- `demo_rel2.py`: older advanced relationship/auth-focused Flask demo variant.

## Authentication Demos

- `authentication/demo_auth.py`: protects all API methods using HTTP Basic auth decorators.
- `authentication/demo_post_auth.py`: applies auth checks only to write methods (`POST`/`PATCH`/`DELETE`).
- `authentication/demo_jwt.py`: JWT login endpoint plus token-protected SAFRS resources.

## Mini Cookbook Demos

- `mini_examples/ex01_to_dict.py`: override `to_dict` serialization.
- `mini_examples/ex02_column_type.py`: custom SQLAlchemy column/type conversion behavior.
- `mini_examples/ex03_jsonapi_attr.py`: computed attributes with `@jsonapi_attr`.
- `mini_examples/ex04_relationship.py`: compact relationship example.
- `mini_examples/ex05_secret_relationship.py`: hide/limit relationship exposure.
- `mini_examples/ex06_filtering.py`: custom filtering strategy override.
- `mini_examples/ex07_logicbank.py`: integrate LogicBank rules with SAFRS models.
- `mini_examples/ex08_rpc.py`: JSON:API RPC methods (`@jsonapi_rpc`) on resources.
- `mini_examples/ex09_stateless.py`: stateless resource behavior in a mini setup.
- `mini_examples/ex10_jabase.py`: `JABase` behavior and method exposure.
- `mini_examples/ex11_search.py`: search helper method exposure.
- `mini_examples/ex12_swagger.py`: custom swagger/openapi metadata and overrides.
- `mini_examples/ex13_prefix.py`: mount API with a custom URL prefix.
- `mini_examples/ex14_flask_dispatch.py`: custom Flask dispatch/routing integration.
- `mini_examples/ex15_http_hook.py`: HTTP lifecycle hooks around resource operations.
- `mini_examples/ex16_perm.py`: permission checks with `_s_check_perm`.
- `mini_examples/custom_swagger.json`: sample custom swagger payload used by mini examples.

## `jsonapi_attr` Notes

- Getter-only `@jsonapi_attr` fields are read-only; request writes are rejected with a validation error.
- Getter+setter `@jsonapi_attr` fields receive raw request values; setter `ValueError` and `TypeError` are surfaced as client validation errors.
- Setter code owns parsing and validation for computed attrs; SAFRS does not coerce request values for `@jsonapi_attr` the way it does for SQLAlchemy columns.
- `@jsonapi_attr` defined on mixins or base classes is inherited by SAFRS subclasses.
- Docstring YAML placed before `---` can provide request-schema metadata such as `description`, `default`, `swagger_type`, and `swagger_format`.
- FastAPI request docs include writable `@jsonapi_attr` fields and omit getter-only ones.
- Sorting and filtering are not implemented automatically for `@jsonapi_attr`; use stored columns or explicit custom hooks when you need query semantics.

## Docker Example

- `docker_sqlite_demo/`: SQLite-only containerized demo.
- See `examples/docker_sqlite_demo/README.md` for details.

## Optional Dependencies

- FastAPI demos: `pip install fastapi uvicorn`
- Auth demos: `pip install flask-httpauth flask-jwt-extended`
- GeoAlchemy demo: `pip install geoalchemy2` (plus PostGIS database)
- LogicBank mini demo: `pip install logicbank`

## Persistence Notes

- Most Flask demos use in-memory sqlite or local sqlite files.
- `demo_fastapi.py` uses `./demo_fastapi.db`.
- `mini_fastapi_app.py` uses `./mini_fastapi.db`.
- Auth demos use sqlite files in `/tmp`.

## Missing Docs References

Project docs still reference paths that are not present in this tree:

- `examples/models.py`
- `examples/employees.py`
- `examples/expose_existing/expose_models.py`

Treat these as missing/restoration-needed until docs or examples are reconciled.
