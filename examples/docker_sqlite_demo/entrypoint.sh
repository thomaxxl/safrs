#!/usr/bin/env sh
set -eu

# Defaults (override in docker-compose.yml or `docker run -e ...`)
: "${FLASK_ENV:=development}"
: "${SQLITE_PATH:=/data/safrs_demo.db}"
: "${SWAGGER_HOST:=localhost}"
: "${SWAGGER_PORT:=1237}"
: "${GUNICORN_WORKERS:=1}"

# Ensure the db directory exists
mkdir -p "$(dirname "$SQLITE_PATH")"

# Gunicorn loads the WSGI app from this folder
CHDIR="/app/examples/docker_sqlite_demo"

COMMON_ARGS="--chdir ${CHDIR} --bind :80 --access-logfile - --error-logfile -"

# SQLite is simplest with a single worker process. If you bump workers, expect "database is locked"
# errors during concurrent writes.
if [ "$FLASK_ENV" = "development" ]; then
  exec gunicorn ${COMMON_ARGS} \
    --reload \
    --graceful-timeout 2 \
    --timeout 10 \
    "demo_wsgi:run_app()"
else
  exec gunicorn ${COMMON_ARGS} \
    --workers "$GUNICORN_WORKERS" \
    --graceful-timeout 10 \
    --timeout 120 \
    "demo_wsgi:run_app()"
fi
