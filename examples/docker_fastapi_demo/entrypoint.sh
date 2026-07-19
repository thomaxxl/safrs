#!/bin/sh
set -eu

SOURCE_ROOT="/app"
if [ -f /demo/frontend/package.json ] && [ -f /demo/backend/run.py ]; then
  SOURCE_ROOT="/demo"
fi

is_true() {
  case "${1:-}" in
    1|true|TRUE|yes|YES|on|ON)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

PIDS=""

start_background() {
  "$@" &
  pid=$!
  PIDS="$PIDS $pid"
}

SEED_DB="$SOURCE_ROOT/backend/data/northwind.sqlite"
RUNTIME_DB="${NORTHWIND_DB_PATH:-/data/northwind.sqlite}"

if [ "$SOURCE_ROOT" = "/demo" ]; then
  export PYTHONPATH="/demo/backend/src:/demo/examples:/demo/examples/authentication:/demo/examples/mini_examples:/demo/vendor/safrs${PYTHONPATH:+:$PYTHONPATH}"
  cp /demo/nginx.conf /etc/nginx/sites-enabled/default
  rm -rf /usr/share/nginx/html
  ln -s /demo/site /usr/share/nginx/html
else
  export PYTHONPATH="/app/backend/src:/app/examples:/app/examples/authentication:/app/examples/mini_examples:/app/vendor/safrs${PYTHONPATH:+:$PYTHONPATH}"
fi

rm -f /srv/demo-code
ln -s "$SOURCE_ROOT/examples" /srv/demo-code

mkdir -p "$(dirname "$RUNTIME_DB")"

if [ ! -f "$RUNTIME_DB" ]; then
  cp "$SEED_DB" "$RUNTIME_DB"
fi

export NORTHWIND_DB_PATH="$RUNTIME_DB"
export NORTHWIND_ADMIN_YAML_PATH="$SOURCE_ROOT/reference/nw-admin.yaml"
export VITE_API_ROOT="/api"
export VITE_ADMIN_YAML_URL="/ui/admin/admin.yaml"
export VITE_BASE_PATH="/admin-app/"
export VITE_DEV_HOST="127.0.0.1"
export VITE_DEV_PORT="5173"
export VITE_HMR_CLIENT_PORT="${DEMO_EXTERNAL_PORT:-8000}"
export VITE_HMR_PATH="/admin-app/__vite_hmr"

USE_LOCAL_SAFRS_JSONAPI_CLIENT_DEFAULT=0
if [ "$SOURCE_ROOT" = "/demo" ] && [ -f "$SOURCE_ROOT/vendor/safrs-jsonapi-client/package.json" ]; then
  USE_LOCAL_SAFRS_JSONAPI_CLIENT_DEFAULT=1
fi

LOCAL_CLIENT_DIR=""
if is_true "${USE_LOCAL_SAFRS_JSONAPI_CLIENT:-$USE_LOCAL_SAFRS_JSONAPI_CLIENT_DEFAULT}"; then
  LOCAL_CLIENT_DIR="$SOURCE_ROOT/vendor/safrs-jsonapi-client"
  if [ ! -f "$LOCAL_CLIENT_DIR/package.json" ]; then
    echo "USE_LOCAL_SAFRS_JSONAPI_CLIENT is set, but $LOCAL_CLIENT_DIR is missing" >&2
    exit 1
  fi
fi

if [ "$SOURCE_ROOT" = "/demo" ]; then
  mkdir -p /demo/frontend/node_modules
  if [ ! -x /demo/frontend/node_modules/.bin/vite ]; then
    cp -a /app/frontend/node_modules/. /demo/frontend/node_modules/
  fi
elif [ ! -x /app/frontend/node_modules/.bin/vite ]; then
  (cd /app/frontend && npm install --no-audit --no-fund --package-lock=false)
fi

if [ -n "$LOCAL_CLIENT_DIR" ]; then
  rm -rf "$SOURCE_ROOT/frontend/node_modules/safrs-jsonapi-client"
  ln -s "$LOCAL_CLIENT_DIR" "$SOURCE_ROOT/frontend/node_modules/safrs-jsonapi-client"
fi

if is_true "${NORTHWIND_FASTAPI_RELOAD:-0}"; then
  start_background uvicorn northwind_backend.fastapi_app:create_fastapi_app \
    --factory \
    --host 127.0.0.1 \
    --port 5656 \
    --reload \
    --reload-dir "$SOURCE_ROOT/backend/src" \
    --reload-dir "$SOURCE_ROOT/vendor/safrs"
else
  start_background python "$SOURCE_ROOT/backend/run.py" fastapi --host 127.0.0.1 --port 5656
fi

if is_true "${DEMO_JWT_RELOAD:-0}"; then
  start_background uvicorn demo_jwt:create_app \
    --factory \
    --host 127.0.0.1 \
    --port 5001 \
    --reload \
    --reload-dir "$SOURCE_ROOT/examples/authentication" \
    --reload-dir "$SOURCE_ROOT/vendor/safrs"
else
  start_background python "$SOURCE_ROOT/examples/authentication/demo_jwt.py"
fi

if is_true "${DEMO_MINI_EXAMPLES_RELOAD:-0}"; then
  start_background uvicorn demo_relationship:create_app \
    --factory \
    --host 127.0.0.1 \
    --port 5005 \
    --reload \
    --reload-dir "$SOURCE_ROOT/examples" \
    --reload-dir "$SOURCE_ROOT/vendor/safrs"
else
  start_background python "$SOURCE_ROOT/examples/demo_relationship.py"
fi

if is_true "${DEMO_MINI_EXAMPLES_RELOAD:-0}"; then
  start_background uvicorn ex06_filtering:create_app \
    --factory \
    --host 127.0.0.1 \
    --port 5002 \
    --reload \
    --reload-dir "$SOURCE_ROOT/examples/mini_examples" \
    --reload-dir "$SOURCE_ROOT/vendor/safrs"
  start_background uvicorn ex08_rpc:create_app \
    --factory \
    --host 127.0.0.1 \
    --port 5003 \
    --reload \
    --reload-dir "$SOURCE_ROOT/examples/mini_examples" \
    --reload-dir "$SOURCE_ROOT/vendor/safrs"
  start_background uvicorn ex11_search:create_app \
    --factory \
    --host 127.0.0.1 \
    --port 5004 \
    --reload \
    --reload-dir "$SOURCE_ROOT/examples/mini_examples" \
    --reload-dir "$SOURCE_ROOT/vendor/safrs"
else
  start_background python "$SOURCE_ROOT/examples/mini_examples/ex06_filtering.py"
  start_background python "$SOURCE_ROOT/examples/mini_examples/ex08_rpc.py"
  start_background python "$SOURCE_ROOT/examples/mini_examples/ex11_search.py"
fi

start_background sh -c "cd \"$SOURCE_ROOT/frontend\" && npm run dev"

start_background nginx -g "daemon off;"

cleanup() {
  for pid in $PIDS; do
    kill "$pid" 2>/dev/null || true
  done
  for pid in $PIDS; do
    wait "$pid" 2>/dev/null || true
  done
}

all_running() {
  for pid in $PIDS; do
    if ! kill -0 "$pid" 2>/dev/null; then
      return 1
    fi
  done
  return 0
}

trap cleanup INT TERM

STARTUP_WAIT_SECONDS="${DEMO_STARTUP_WAIT_SECONDS:-5}"
elapsed=0
while [ "$elapsed" -lt "$STARTUP_WAIT_SECONDS" ]; do
  if ! all_running; then
    echo "[demo] Startup failed: one or more background processes exited early" >&2
    cleanup
    exit 1
  fi
  sleep 1
  elapsed=$((elapsed + 1))
done

NGINX_CONTAINER_URL="http://127.0.0.1:80/"
NGINX_HOST_URL="http://127.0.0.1:${DEMO_EXTERNAL_PORT:-8000}/"
echo "[demo] Startup successful: nginx=${NGINX_CONTAINER_URL} host=${NGINX_HOST_URL} admin=${NGINX_HOST_URL}admin-app/ docs=${NGINX_HOST_URL}docs"

while all_running; do
  sleep 1
done

cleanup
exit 1
