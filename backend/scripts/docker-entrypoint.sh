#!/bin/sh
set -eu

cd /app/backend

APP_HOST="${APP_HOST:-0.0.0.0}"
APP_PORT="${APP_PORT:-8140}"

python -m alembic upgrade head

exec uvicorn app.main:app --host "${APP_HOST}" --port "${APP_PORT}"

