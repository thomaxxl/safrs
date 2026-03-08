# SAFRS Examples

Examples are organized by support level so it is clear where to start.

- Python target: `>=3.9`
- Install base deps from this folder: `pip install -r examples/requirements.txt`
- Some examples require extra dependencies (listed below)

## Start Here

These are the recommended entry points.

1. `mini_app.py` (Flask minimal starter)
   - Run: `python examples/mini_app.py`
2. `demo_relationship.py` (Flask relationships starter)
   - Run: `python examples/demo_relationship.py [HOST]`
3. `mini_fastapi_app.py` (FastAPI minimal starter)
   - Run: `python examples/mini_fastapi_app.py`
4. `demo_fastapi.py` (FastAPI full showcase)
   - Run: `python examples/demo_fastapi.py [HOST] [PORT]`
5. `demo_pythonanywhere_com.py` (canonical full Flask showcase)
   - Run: `python examples/demo_pythonanywhere_com.py [HOST] [PORT]`

## Categories

### Starter

- `mini_app.py`
- `mini_fastapi_app.py`
- `demo_relationship.py`
- `demo_fastapi.py`
- `demo_pythonanywhere_com.py`

### Cookbook

- `mini_examples/ex01_to_dict.py`
- `mini_examples/ex02_column_type.py`
- `mini_examples/ex03_jsonapi_attr.py`
- `mini_examples/ex04_relationship.py`
- `mini_examples/ex05_secret_relationship.py`
- `mini_examples/ex06_filtering.py`
- `mini_examples/ex07_logicbank.py`
- `mini_examples/ex08_rpc.py`
- `mini_examples/ex09_stateless.py`
- `mini_examples/ex10_jabase.py`
- `mini_examples/ex11_search.py`
- `mini_examples/ex12_swagger.py`
- `mini_examples/ex13_prefix.py`
- `mini_examples/ex14_flask_dispatch.py`
- `mini_examples/ex15_http_hook.py`
- `mini_examples/ex16_perm.py`

### Integration / Specialized

- `authentication/demo_auth.py` (HTTP Basic auth)
- `authentication/demo_post_auth.py` (method-specific auth decorators)
- `authentication/demo_jwt.py` (JWT)
- `demo_geoalchemy.py` (GeoAlchemy / PostGIS)
- `demo_flaskrestjsonapi.py` (comparison-oriented integration demo)
- `docker_sqlite_demo/` (containerized sqlite demo)

### Legacy / Compatibility

- `demo_full.py` is now a compatibility wrapper around `demo_pythonanywhere_com.py`.
- `demo_rel2.py` and `demo_devto.py` are older variants; keep for compatibility and reference.
- `demo_http_get.py` and `demo_http_method.py` are focused protocol demos.
- `demo_stateless.py` is an advanced non-SQLAlchemy model demo.

## Optional Dependencies

- FastAPI examples:
  - `pip install fastapi uvicorn`
- Auth examples:
  - `pip install flask-httpauth flask-jwt-extended`
- GeoAlchemy example:
  - `pip install geoalchemy2`
  - Requires a PostgreSQL/PostGIS database
- LogicBank mini example:
  - `pip install logicbank`

## Persistence Notes

- Most Flask demos use sqlite in-memory or local sqlite files.
- `demo_fastapi.py` uses `./demo_fastapi.db`.
- `mini_fastapi_app.py` uses `./mini_fastapi.db`.
- Auth demos use sqlite files in `/tmp` for convenience.

## Missing Docs References

Project docs still reference these paths which are not present in this tree:

- `examples/models.py`
- `examples/employees.py`
- `examples/expose_existing/expose_models.py`

Treat these as missing/restoration-needed items until docs or examples are reconciled.

