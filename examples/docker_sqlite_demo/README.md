# SQLite-only SAFRS demo container

This folder adds a **single-container** Docker setup to run a SAFRS demo using **SQLite only**.

It is inspired by `thomaxxl/safrs-example` (same `run_app()` + gunicorn pattern), but:
- **no Postgres/MySQL containers**
- no migrations (the demo uses `db.create_all()`)

## Quick start

From the SAFRS repo root:

```bash
cd examples/docker_sqlite_demo
docker compose up --build
```

Then open:

- API (Swagger UI): http://localhost:1237/api/
- Swagger JSON: http://localhost:1237/api/swagger.json

Optional frontends (only work if assets exist in the repo root):
- jsonapi-admin: http://localhost:1237/ja/
- swagger-editor: http://localhost:1237/swagger_editor/

## How it works

- `demo_app.py`: models + `create_app()` + `start_api()` + seeding
- `demo_wsgi.py`: provides `run_app()` for gunicorn (factory)
- `entrypoint.sh`: runs gunicorn (defaults to 1 worker for SQLite)
- `docker-compose.yml`: one service + a named volume for `/data` (SQLite file)

## Resetting the database

```bash
cd examples/docker_sqlite_demo
docker compose down -v
docker compose up --build
```

This deletes the named volume (`safrs_demo_data`) so the demo will seed fresh data on the next start.

## Changing the external port

If you change the port mapping in `docker-compose.yml`, also change `SWAGGER_PORT` so swagger.json points at the right place.

Example (run on port 8080):

```yaml
ports:
  - "8080:80"
environment:
  SWAGGER_PORT: 8080
```

## SQLite concurrency note

SQLite works best with a single gunicorn worker process.
If you increase `GUNICORN_WORKERS`, concurrent writes may trigger `database is locked`.
Keep it at `1` for the cleanest demo experience.
