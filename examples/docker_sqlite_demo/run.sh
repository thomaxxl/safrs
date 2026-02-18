#!/usr/bin/env bash
set -euo pipefail

# Run this from the `examples/docker_sqlite_demo` folder
compose="docker compose -f docker-compose.yml"

case "${1:-}" in
  up)
    shift
    ${compose} up --build "$@"
    ;;
  down)
    shift
    ${compose} down "$@"
    ;;
  logs)
    shift
    ${compose} logs -f --tail 200 "$@"
    ;;
  shell)
    shift
    ${compose} exec safrs-demo-sqlite sh "$@"
    ;;
  reset-db)
    shift
    # stops containers AND deletes the sqlite volume
    ${compose} down -v "$@"
    ;;
  *)
    cat <<'EOF'
Usage:
  ./run.sh up            # build + run the demo
  ./run.sh logs          # tail logs
  ./run.sh shell         # sh inside container
  ./run.sh down          # stop
  ./run.sh reset-db      # stop + delete sqlite volume (fresh seed on next start)
EOF
    exit 1
    ;;
esac
