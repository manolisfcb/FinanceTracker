#!/usr/bin/env bash
# Single entrypoint for both roles, so web and worker are the same image with
# a different argument — no chance of them drifting apart.
set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL no está seteada}"
: "${SECRET_KEY:?SECRET_KEY no está seteada}"
: "${JWT_SECRET_KEY:?JWT_SECRET_KEY no está seteada}"

export FLASK_APP=app.py

case "${1:-web}" in
  web)
    # Only the web role touches the schema, and only when asked. Two roles
    # racing to migrate the same database is how you get a half-applied
    # revision; MIGRATE_ON_START=false lets the deploy run it as a separate
    # step instead.
    if [[ "${MIGRATE_ON_START:-true}" == "true" ]]; then
      echo "==> Preparando el esquema"
      flask bootstrap-db
    fi
    echo "==> Arrancando gunicorn"
    exec gunicorn --config /app/docker/gunicorn.conf.py "app:app"
    ;;

  worker)
    # The scheduler process. RUN_SCHEDULER is forced on here and defaults to
    # off everywhere else, so the jobs have exactly one owner no matter how
    # many web replicas are running.
    echo "==> Arrancando el scheduler"
    export RUN_SCHEDULER=true
    exec flask run-scheduler
    ;;

  migrate)
    echo "==> Solo migraciones"
    exec flask bootstrap-db
    ;;

  shell)
    exec flask shell
    ;;

  *)
    exec "$@"
    ;;
esac
